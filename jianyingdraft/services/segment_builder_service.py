# -*- coding: utf-8 -*-
"""分镜片段构建：句号级 TTS + ASR 字幕对齐 + 画面时间轴。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from jianyingdraft.services.audio_service import text_to_speech_service
from jianyingdraft.services.audio_subtitle_service import recognize_subtitles_service
from jianyingdraft.utils.media_parser import get_media_duration

SENTENCE_END = re.compile(r"[。！？；]$")
PUNCT_RE = re.compile("[，。！？；、：\"\"''（）()《》【】\\[\\]…—·]")


@dataclass
class SubtitleLine:
    display: str
    tts_fragment: str = ""
    skip_tts: bool = False


@dataclass
class SentenceGroup:
    shot_id: str
    index: int
    tts_text: str
    audio_name: str
    lines: List[SubtitleLine] = field(default_factory=list)


@dataclass
class TimedSubtitle:
    display: str
    start: float
    end: float
    shot_id: str
    sentence_index: int
    line_index: int


@dataclass
class VideoItem:
    track: str
    material: str
    end: float
    clip_settings: Optional[dict]
    anim_type: Optional[str] = None
    anim_name: Optional[str] = None
    start: Optional[float] = None
    start_subtitle: Optional[int] = None
    start_offset: float = 0.0
    shot_id: Optional[str] = None


def fmt_time(seconds: float) -> str:
    if abs(seconds - round(seconds)) < 0.001:
        return f"{int(round(seconds))}s"
    text = f"{seconds:.3f}".rstrip("0").rstrip(".")
    return f"{text}s"


def clean_subtitle_display(text: str, max_chars: int = 12) -> str:
    s = PUNCT_RE.sub("", text.strip())
    if len(s) > max_chars:
        return s[:max_chars]
    return s


def ends_sentence(text: str) -> bool:
    t = text.strip()
    return bool(t and SENTENCE_END.search(t))


def group_subtitles_by_sentence(
    items: Sequence[Tuple[str, str, str, float, float, bool]],
) -> List[SentenceGroup]:
    """
    将 (fname, display, tts, plan_start, plan_end, skip_tts) 按句号分组。

    TTS 只在句号/问号/感叹号/分号处切分，逗号不切，保证语音连贯。
    """
    groups: List[SentenceGroup] = []
    current_lines: List[SubtitleLine] = []
    current_tts_parts: List[str] = []
    shot_id = ""
    sent_index = 0

    def flush() -> None:
        nonlocal sent_index, current_lines, current_tts_parts, shot_id
        if not current_lines:
            return
        tts_text = "".join(current_tts_parts).strip()
        if not tts_text:
            tts_text = current_lines[-1].display
        audio_name = f"{shot_id}_sent{sent_index:02d}.mp3"
        groups.append(
            SentenceGroup(
                shot_id=shot_id,
                index=sent_index,
                tts_text=tts_text,
                audio_name=audio_name,
                lines=list(current_lines),
            )
        )
        sent_index += 1
        current_lines = []
        current_tts_parts = []

    for fname, display, tts, _start, _end, skip_tts in items:
        sid = fname.split("_")[0]
        if shot_id and sid != shot_id:
            flush()
            shot_id = sid
            sent_index = 0
        elif not shot_id:
            shot_id = sid

        current_lines.append(
            SubtitleLine(display=display, tts_fragment=tts or "", skip_tts=skip_tts)
        )
        if not skip_tts and tts:
            current_tts_parts.append(tts)
            if ends_sentence(tts):
                flush()

    if current_lines:
        flush()
    return groups


def _char_weight(text: str) -> int:
    return max(1, len(re.sub(r"\s+", "", text)))


def align_subtitles_proportional(
    lines: Sequence[SubtitleLine],
    duration: float,
    offset: float = 0.0,
) -> List[Tuple[float, float]]:
    weights = [_char_weight(line.display) for line in lines]
    total = sum(weights)
    timings: List[Tuple[float, float]] = []
    cursor = offset
    for weight in weights:
        seg = duration * weight / total
        timings.append((cursor, cursor + seg))
        cursor += seg
    return timings


def align_subtitles_with_asr(
    lines: Sequence[SubtitleLine],
    utterances: Sequence[Dict[str, Any]],
    audio_duration: float,
    offset: float = 0.0,
) -> List[Tuple[float, float]]:
    if not utterances:
        return align_subtitles_proportional(lines, audio_duration, offset)

    asr_times = [
        (int(u.get("start_time", 0)) / 1000.0, int(u.get("end_time", 0)) / 1000.0)
        for u in utterances
        if (u.get("text") or "").strip()
    ]
    if not asr_times:
        return align_subtitles_proportional(lines, audio_duration, offset)

    n_lines = len(lines)
    n_asr = len(asr_times)

    if n_lines == n_asr:
        return [(offset + s, offset + e) for s, e in asr_times]

    if n_lines < n_asr:
        merged: List[Tuple[float, float]] = []
        ratio = n_asr / n_lines
        for i in range(n_lines):
            start_idx = int(i * ratio)
            end_idx = int((i + 1) * ratio) - 1
            end_idx = max(start_idx, min(end_idx, n_asr - 1))
            merged.append((asr_times[start_idx][0], asr_times[end_idx][1]))
        return [(offset + s, offset + e) for s, e in merged]

    # n_lines > n_asr：按字数比例在 ASR 时间窗内切分
    window_start = asr_times[0][0]
    window_end = asr_times[-1][1]
    window_dur = max(window_end - window_start, 0.01)
    prop = align_subtitles_proportional(lines, window_dur, offset + window_start)
    if prop[-1][1] < offset + audio_duration - 0.05:
        prop[-1] = (prop[-1][0], offset + audio_duration)
    return prop


def generate_sentence_tts(
    groups: Sequence[SentenceGroup],
    output_dir: Path,
    speaker: str,
    *,
    force: bool = False,
) -> Dict[str, float]:
    durations: Dict[str, float] = {}
    for group in groups:
        path = output_dir / group.audio_name
        if path.exists() and not force:
            duration = get_media_duration(str(path))
            if duration:
                durations[group.audio_name] = duration
                continue
        resp = text_to_speech_service(
            text=group.tts_text,
            output_dir=str(output_dir),
            speaker=speaker,
            output_name=group.audio_name,
        )
        if not resp.success:
            raise RuntimeError(f"TTS 失败 {group.audio_name}: {resp.message}")
        duration = get_media_duration(str(path))
        if not duration:
            raise RuntimeError(f"无法解析音频时长: {path}")
        durations[group.audio_name] = duration
    return durations


def recognize_sentence_timings(
    groups: Sequence[SentenceGroup],
    output_dir: Path,
    *,
    words_per_line: int = 12,
    poll_timeout: float = 120.0,
    skip_asr: bool = False,
    cache_dir: Optional[Path] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    cache_dir = cache_dir or (output_dir / "_asr_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, List[Dict[str, Any]]] = {}

    for group in groups:
        cache_path = cache_dir / f"{Path(group.audio_name).stem}.json"
        if cache_path.exists() and not skip_asr:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            results[group.audio_name] = data.get("utterances") or []
            continue
        if skip_asr:
            results[group.audio_name] = []
            continue

        audio_path = output_dir / group.audio_name
        resp = recognize_subtitles_service(
            audio_path=str(audio_path),
            output_json=str(cache_path),
            words_per_line=words_per_line,
            poll_timeout=poll_timeout,
        )
        if not resp.success:
            raise RuntimeError(f"ASR 失败 {group.audio_name}: {resp.message}")
        results[group.audio_name] = (resp.data or {}).get("utterances") or []
    return results


def build_timed_subtitles(
    groups: Sequence[SentenceGroup],
    durations: Dict[str, float],
    asr_map: Dict[str, List[Dict[str, Any]]],
) -> List[TimedSubtitle]:
    timed: List[TimedSubtitle] = []
    global_offset = 0.0

    for group in groups:
        duration = durations[group.audio_name]
        utterances = asr_map.get(group.audio_name) or []
        pairs = align_subtitles_with_asr(group.lines, utterances, duration, global_offset)
        for idx, (line, (start, end)) in enumerate(zip(group.lines, pairs)):
            timed.append(
                TimedSubtitle(
                    display=clean_subtitle_display(line.display),
                    start=start,
                    end=end,
                    shot_id=group.shot_id,
                    sentence_index=group.index,
                    line_index=idx,
                )
            )
        global_offset += duration
    return timed


def resolve_video_start(
    item: VideoItem,
    shot_subtitles: Dict[str, List[TimedSubtitle]],
    shot_start: float,
    shot_end: float,
) -> float:
    if item.start_subtitle is not None and item.shot_id:
        subs = shot_subtitles.get(item.shot_id, [])
        if 0 <= item.start_subtitle < len(subs):
            return subs[item.start_subtitle].start + item.start_offset
    if item.start is not None:
        return item.start
    return shot_start + item.start_offset


def build_segments(
    groups: Sequence[SentenceGroup],
    durations: Dict[str, float],
    timed_subtitles: Sequence[TimedSubtitle],
    video_items: Sequence[VideoItem],
    *,
    bg_material: str,
    sub_style: Optional[dict] = None,
    sub_clip: Optional[dict] = None,
    aidata_dir: Optional[Path] = None,
) -> Tuple[List[dict], float]:
    sub_style = sub_style or {"size": 8.0, "align": 1, "color": [0.1, 0.1, 0.2]}
    sub_clip = sub_clip or {"transform_y": -0.85}
    aidata_dir = aidata_dir or Path(".")

    total = sum(durations[g.audio_name] for g in groups)
    segments: List[dict] = []

    segments.append({
        "type": "video",
        "track_name": "video_bg",
        "material": bg_material,
        "target_start_end": f"0s-{fmt_time(total)}",
        "clip_settings": {"scale_x": 1.0, "scale_y": 1.0, "transform_x": 0.0, "transform_y": 0.0},
    })

    shot_subtitles: Dict[str, List[TimedSubtitle]] = {}
    for sub in timed_subtitles:
        shot_subtitles.setdefault(sub.shot_id, []).append(sub)

    shot_bounds: Dict[str, Tuple[float, float]] = {}
    for sid, subs in shot_subtitles.items():
        shot_bounds[sid] = (subs[0].start, subs[-1].end)

    global_offset = 0.0
    for group in groups:
        path = aidata_dir / group.audio_name
        duration = durations[group.audio_name]
        segments.append({
            "type": "audio",
            "track_name": "audio_narration",
            "material": str(path),
            "target_start_end": f"{fmt_time(global_offset)}-{fmt_time(global_offset + duration)}",
        })
        global_offset += duration

    for sub in timed_subtitles:
        segments.append({
            "type": "text",
            "track_name": "text_subtitle",
            "text": sub.display,
            "target_start_end": f"{fmt_time(sub.start)}-{fmt_time(sub.end)}",
            "style": sub_style,
            "clip_settings": sub_clip,
            "animation_type": "TextIntro",
            "animation_name": "渐显",
        })

    for item in video_items:
        material = item.material if item.material.startswith("/") else str(aidata_dir / item.material)
        sid = item.shot_id or ""
        if sid in shot_bounds:
            shot_start, shot_end = shot_bounds[sid]
            start = resolve_video_start(item, shot_subtitles, shot_start, shot_end)
            end = shot_end if item.end <= 0 else max(start + 0.1, item.end)
            if item.end > 0 and item.end > shot_end:
                end = item.end
        else:
            start = item.start or 0.0
            end = item.end

        seg: dict = {
            "type": "video",
            "track_name": item.track,
            "material": material,
            "target_start_end": f"{fmt_time(start)}-{fmt_time(end)}",
        }
        if item.track != "video_bg":
            seg["clip_settings"] = item.clip_settings or {}
        if item.anim_type and item.anim_name:
            seg["animation_type"] = item.anim_type
            seg["animation_name"] = item.anim_name
        segments.append(seg)

    return segments, total


def shot_sentence_summary(groups: Sequence[SentenceGroup]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for g in groups:
        summary[g.shot_id] = summary.get(g.shot_id, 0) + 1
    return summary


def _parse_subtitle_items(items: Sequence[Dict[str, Any]]) -> List[Tuple[str, str, str, float, float, bool]]:
    parsed: List[Tuple[str, str, str, float, float, bool]] = []
    for item in items:
        parsed.append((
            str(item.get("filename") or item.get("file") or ""),
            str(item.get("display") or item.get("subtitle") or ""),
            str(item.get("tts_text") or item.get("tts") or ""),
            float(item.get("plan_start", 0)),
            float(item.get("plan_end", 0)),
            bool(item.get("skip_tts", False)),
        ))
    return parsed


def _parse_video_items(items: Sequence[Dict[str, Any]]) -> List[VideoItem]:
    result: List[VideoItem] = []
    for item in items:
        result.append(VideoItem(
            track=str(item["track"]),
            material=str(item["material"]),
            end=float(item.get("end", 0)),
            clip_settings=item.get("clip_settings"),
            anim_type=item.get("animation_type") or item.get("anim_type"),
            anim_name=item.get("animation_name") or item.get("anim_name"),
            start=item.get("start"),
            start_subtitle=item.get("start_subtitle"),
            start_offset=float(item.get("start_offset", 0)),
            shot_id=item.get("shot_id"),
        ))
    return result


def build_narration_segments_service(
    output_dir: str,
    subtitle_items: Sequence[Dict[str, Any]],
    *,
    speaker: str = "BV411_streaming",
    bg_material: str = "",
    video_items: Optional[Sequence[Dict[str, Any]]] = None,
    skip_asr: bool = False,
    force_tts: bool = False,
    words_per_line: int = 12,
    poll_timeout: float = 120.0,
    write_segments_path: Optional[str] = None,
    sub_style: Optional[dict] = None,
    sub_clip: Optional[dict] = None,
) -> "ToolResponse":
    """
    句号级 TTS + ASR 字幕对齐 + 生成 batch_add_segments 片段列表。

    供 MCP build_narration_segments 调用；Agent 应通过 MCP 使用，勿直接运行本地脚本。
    """
    from jianyingdraft.utils.response import ToolResponse

    try:
        out = Path(output_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)

        if not subtitle_items:
            return ToolResponse(success=False, message="subtitle_items 不能为空")

        tuples = _parse_subtitle_items(subtitle_items)
        groups = group_subtitles_by_sentence(tuples)
        if not groups:
            return ToolResponse(success=False, message="无法从 subtitle_items 分组出句号 TTS")

        durations = generate_sentence_tts(groups, out, speaker, force=force_tts)
        asr_map = recognize_sentence_timings(
            groups, out,
            words_per_line=words_per_line,
            poll_timeout=poll_timeout,
            skip_asr=skip_asr,
        )
        timed = build_timed_subtitles(groups, durations, asr_map)
        vitems = _parse_video_items(video_items or [])
        segments, total = build_segments(
            groups, durations, timed, vitems,
            bg_material=bg_material,
            sub_style=sub_style,
            sub_clip=sub_clip,
            aidata_dir=out,
        )

        meta = {
            "mode": "sentence_tts_with_asr" if not skip_asr else "sentence_tts_proportional",
            "output_dir": str(out),
            "sentence_count": len(groups),
            "subtitle_count": len(timed),
            "total_duration": total,
            "shot_sentences": shot_sentence_summary(groups),
            "sentences": [
                {
                    "audio": g.audio_name,
                    "audio_path": str(out / g.audio_name),
                    "shot_id": g.shot_id,
                    "tts_text": g.tts_text,
                    "duration": durations[g.audio_name],
                    "display_lines": [line.display for line in g.lines],
                }
                for g in groups
            ],
            "timed_subtitles": [
                {
                    "display": t.display,
                    "start": round(t.start, 3),
                    "end": round(t.end, 3),
                    "target_start_end": f"{fmt_time(t.start)}-{fmt_time(t.end)}",
                    "shot_id": t.shot_id,
                }
                for t in timed
            ],
        }

        if write_segments_path:
            seg_path = Path(write_segments_path).expanduser()
            seg_path.parent.mkdir(parents=True, exist_ok=True)
            seg_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
            meta["segments_path"] = str(seg_path)

        return ToolResponse(
            success=True,
            message=(
                f"已生成 {len(groups)} 段句号 TTS、{len(timed)} 条对齐字幕，"
                f"总时长 {total:.2f}s，segments {len(segments)} 条"
            ),
            data={
                "segments": segments,
                "meta": meta,
                "total_duration": total,
            },
        )
    except Exception as exc:
        return ToolResponse(success=False, message=f"构建旁白片段失败: {exc}")
