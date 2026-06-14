#!/usr/bin/env python3
"""[已废弃 · 勿直接运行] 请使用 MCP build_narration_segments。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

from jianyingdraft.services.segment_builder_service import (  # noqa: E402
    SubtitleLine,
    SentenceGroup,
    build_segments,
    build_timed_subtitles,
    clean_subtitle_display,
    generate_sentence_tts,
    recognize_sentence_timings,
)

OUT_DIR = Path(__file__).resolve().parent
BG = PROJECT / "material" / "bg_black_1920x1080.png"
SPEAKER = "BV411_streaming"

LONG_TEXT = (
    "你有没有想过，工资条上那一行五险一金，到底是在扣你钱，还是在帮你存钱？"
    "说白了，社保就是国家牵头、大家一块交、专门用来扛人生大风险的公共存钱罐。"
    "平时看起来是少拿一点，真遇到事儿，它像一张人生安全网，兜住你最怕的那几类意外。"
    "咱们常说的五险，就是养老、医疗、失业、工伤、生育这五样。"
    "你、公司各交一份，钱汇进国家管的大池子里，谁需要谁用。"
    "第一个，爸妈退休。社保里的养老保险，就是在给未来的自己发工资。"
    "第二个，感冒进医院。有医疗保险，国家帮你跟医院砍价，该报销的报销。"
    "第三个，公司裁员。失业保险在这时候顶上，帮你撑过最难的过渡期。"
    "第四个，外卖员路上摔伤。工伤保险专门管这个，医疗费、误工补偿有章可循。"
    "第五个，生宝宝。生育保险能报销一部分，还能领生育津贴。"
    "五险一金，五险就是上面这五样，一金是住房公积金，专门帮你贷款买房。"
    "缴费基数，简单说就是按哪档工资算你要交多少，但有上限和下限。"
    "统筹账户像一口大锅饭，大家钱放一起谁需要谁用；个人账户记在你名下的小账本。"
    "断缴就是中间没交上，有些待遇会暂停或受影响，所以换工作要盯紧衔接。"
    "社保不是额外负担，是防大风险的互助账本；平时交一点，关键时刻能救命。"
    "下次入职，记得问一句：社保按什么基数交？给未来的自己，存一份安心。"
)

SUB_STYLE = {"size": 8.0, "align": 1}
SUB_CLIP = {"transform_y": -0.85}

SPLIT_PARTICLES = re.compile(
    r"(?<=[的了吗呢吧和与或就也都还而]|所以|因为|如果|可以|已经|正在|一个|这种|那些)"
)


def split_display_lines(sentence: str, max_chars: int = 12) -> list[str]:
    """将一句旁白拆成 ≤12 字的显示字幕（仅用于上屏，不影响 TTS）。"""
    cleaned = clean_subtitle_display(sentence, max_chars=9999)
    if len(cleaned) <= max_chars:
        return [cleaned]
    parts = SPLIT_PARTICLES.split(cleaned)
    lines: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        if len(buf) + len(part) <= max_chars:
            buf += part
        else:
            if buf:
                lines.append(buf)
            buf = part if len(part) <= max_chars else part[:max_chars]
    if buf:
        lines.append(buf)
    return lines or [cleaned[:max_chars]]


def sentences_to_groups(sentences: list[str]) -> list[SentenceGroup]:
    groups: list[SentenceGroup] = []
    for i, sent in enumerate(sentences, 1):
        displays = split_display_lines(sent)
        lines = [SubtitleLine(display=d) for d in displays]
        groups.append(
            SentenceGroup(
                shot_id=f"L{i:02d}",
                index=1,
                tts_text=sent,
                audio_name=f"L{i:02d}.mp3",
                lines=lines,
            )
        )
    return groups


def legacy_items_from_sentences(sentences: list[str]) -> list[tuple]:
    """保留：展示旧 comma 切分与句号切分差异（调试用）。"""
    items = []
    for i, sent in enumerate(sentences, 1):
        displays = split_display_lines(sent)
        parts = re.split(r"(?<=[，、])", sent)
        parts = [p for p in parts if p.strip()]
        for j, display in enumerate(displays):
            tts = parts[j] if j < len(parts) else (sent if j == len(displays) - 1 else "")
            skip = not tts
            items.append((f"L{i:02d}_L{j+1:02d}.mp3", display, tts, 0.0, 0.0, skip))
    return items


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-asr", action="store_true")
    parser.add_argument("--force-tts", action="store_true")
    args = parser.parse_args()

    sentences = [s.strip() for s in re.split(r"(?<=[。！？；])", LONG_TEXT.strip()) if s.strip()]
    print(f"=== 超长文本测试 ===")
    print(f"总字符数: {len(LONG_TEXT)}")
    print(f"句号分句: {len(sentences)}（TTS 按句号合成，不按逗号切）")

    groups = sentences_to_groups(sentences)
    print(f"\n=== 生成 {len(groups)} 段句号 TTS ===")
    durations = generate_sentence_tts(groups, OUT_DIR, SPEAKER, force=args.force_tts)

    print(f"\n=== ASR 字幕对齐 ===")
    asr_map = recognize_sentence_timings(groups, OUT_DIR, skip_asr=args.skip_asr)
    timed = build_timed_subtitles(groups, durations, asr_map)

    segments, total = build_segments(
        groups,
        durations,
        timed,
        video_items=[],
        bg_material=str(BG),
        sub_style=SUB_STYLE,
        sub_clip=SUB_CLIP,
        aidata_dir=OUT_DIR,
    )

    meta = {
        "text_length": len(LONG_TEXT),
        "sentence_count": len(sentences),
        "total_duration": total,
        "timed_subtitles": [{"display": t.display, "start": t.start, "end": t.end} for t in timed],
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "segments.json").write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 segments.json ({len(segments)} 条)，总时长 {total:.2f}s")


if __name__ == "__main__":
    main()
