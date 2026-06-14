# -*- coding: utf-8 -*-
"""剪映 PC 端音频字幕识别（ASR）服务。"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from jianyingdraft.utils.jianying_client import (
    JianyingApiClient,
    build_signed_api_headers,
)
from jianyingdraft.utils.media_parser import get_media_duration
from jianyingdraft.utils.response import ToolResponse
from jianyingdraft.utils.vod_uploader import VodUploadError, upload_audio_for_recognition


def _ms_to_srt_time(ms: int) -> str:
    ms = max(0, int(ms))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def utterances_to_srt(utterances: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for idx, item in enumerate(utterances, start=1):
        text = (item.get("text") or "").strip()
        if not text:
            continue
        start = item.get("start_time", 0)
        end = item.get("end_time", start)
        lines.append(str(idx))
        lines.append(f"{_ms_to_srt_time(start)} --> {_ms_to_srt_time(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _post_signed(client: JianyingApiClient, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    body_text = json.dumps(body, separators=(",", ":"))
    headers = build_signed_api_headers(path, body_text)
    return client.post_json_text(path, body_text, headers=headers)


def submit_subtitle_task(
    client: JianyingApiClient,
    *,
    audio_uri: str,
    duration_ms: float,
    max_lines: int = 1,
    words_per_line: int = 16,
    caption_type: int = 2,
    adjust_endtime: int = 200,
) -> str:
    body = {
        "adjust_endtime": adjust_endtime,
        "audio": audio_uri,
        "caption_type": caption_type,
        "client_request_id": str(uuid.uuid4()),
        "max_lines": max_lines,
        "songs_info": [{"end_time": duration_ms, "id": "", "start_time": 0}],
        "words_per_line": words_per_line,
    }
    resp = _post_signed(client, "/lv/v1/audio_subtitle/submit", body)
    if str(resp.get("ret")) != "0":
        raise RuntimeError(f"audio_subtitle/submit 失败: ret={resp.get('ret')} errmsg={resp.get('errmsg')}")
    task_id = (resp.get("data") or {}).get("id")
    if not task_id:
        raise RuntimeError(f"submit 未返回任务 ID: {resp}")
    return task_id


def query_subtitle_task(
    client: JianyingApiClient,
    task_id: str,
    *,
    timeout: float = 120,
    poll_interval: float = 1.0,
) -> Dict[str, Any]:
    body = {"id": task_id, "pack_options": {"need_attribute": True}}
    deadline = time.time() + timeout
    last_resp: Dict[str, Any] = {}
    while time.time() < deadline:
        last_resp = _post_signed(client, "/lv/v1/audio_subtitle/query", body)
        if str(last_resp.get("ret")) != "0":
            raise RuntimeError(f"audio_subtitle/query 失败: ret={last_resp.get('ret')} errmsg={last_resp.get('errmsg')}")
        data = last_resp.get("data") or {}
        utterances = data.get("utterances") or []
        if utterances:
            return data
        time.sleep(poll_interval)
    raise TimeoutError(f"字幕识别超时（{timeout}s），最后响应: {json.dumps(last_resp, ensure_ascii=False)[:500]}")


def recognize_subtitles_service(
    audio_path: str,
    *,
    audio_uri: Optional[str] = None,
    output_srt: Optional[str] = None,
    output_json: Optional[str] = None,
    max_lines: int = 1,
    words_per_line: int = 16,
    poll_timeout: float = 120,
) -> ToolResponse:
    """
    识别本地音频字幕（剪映 ASR 接口）。

    流程：upload_sign → VOD 上传 → audio_subtitle/submit → query
    """
    try:
        path = Path(audio_path).expanduser().resolve()
        if not audio_uri and not path.exists():
            return ToolResponse(success=False, message=f"音频文件不存在: {audio_path}")

        client = JianyingApiClient()
        tos_uri = audio_uri
        if not tos_uri:
            try:
                tos_uri = upload_audio_for_recognition(client, str(path))
            except VodUploadError as exc:
                return ToolResponse(
                    success=False,
                    message=str(exc),
                    data={"hint": "请确认设备信息（JIANYING_TDID 等）与剪映客户端一致"},
                )

        duration_sec = get_media_duration(str(path)) if path.exists() else None
        if duration_sec is None and not audio_uri:
            return ToolResponse(success=False, message="无法解析音频时长")
        if duration_sec is None:
            duration_sec = 60.0
        duration_ms = duration_sec * 1000.0

        task_id = submit_subtitle_task(
            client,
            audio_uri=tos_uri,
            duration_ms=duration_ms,
            max_lines=max_lines,
            words_per_line=words_per_line,
        )
        result = query_subtitle_task(client, task_id, timeout=poll_timeout)
        utterances = result.get("utterances") or []

        srt_text = utterances_to_srt(utterances)
        if output_srt:
            srt_path = Path(output_srt).expanduser()
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text(srt_text, encoding="utf-8")

        if output_json:
            json_path = Path(output_json).expanduser()
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        full_text = "".join(u.get("text", "") for u in utterances)
        return ToolResponse(
            success=True,
            message=f"识别完成，共 {len(utterances)} 句",
            data={
                "task_id": task_id,
                "audio_uri": tos_uri,
                "duration_ms": duration_ms,
                "language": ((result.get("attribute") or {}).get("extra") or {}).get("language"),
                "full_text": full_text,
                "utterances": utterances,
                "srt": srt_text,
                "output_srt": str(Path(output_srt).expanduser()) if output_srt else None,
                "output_json": str(Path(output_json).expanduser()) if output_json else None,
            },
        )
    except Exception as exc:
        return ToolResponse(success=False, message=f"字幕识别失败: {exc}")
