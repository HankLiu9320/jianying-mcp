#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""剪映音频字幕识别 CLI（main 内已写固定测试参数，直接运行即可）。

  uv run python scripts/recognize_subtitles.py

无需 Cookie，使用设备签名（默认设备信息见 ~/.cursor/kb/work/docs/config/jianying-device-info.md）。
可通过 .env 覆盖 JIANYING_TDID、JIANYING_APP_VERSION 等参数。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from jianyingdraft.services.audio_subtitle_service import recognize_subtitles_service


def main() -> int:
    # ===== 固定测试参数（直接改这里即可调试） =====
    TEST_AUDIO = str(project_root / "/Users/liujianjia/2_tools/jianying/aidata/shebao-wuxian-yijin/S01_L01.mp3")
    TEST_SRT = "/tmp/test_short.srt"
    TEST_JSON = "/tmp/test_short_subtitles.json"
    TEST_MAX_LINES = 1
    TEST_WORDS_PER_LINE = 16
    TEST_TIMEOUT = 120.0
    # 若已有 TOS URI 可跳过 VOD 上传，仅测 submit/query
    TEST_AUDIO_URI = ""
    # =============================================

    result = recognize_subtitles_service(
        audio_path=TEST_AUDIO,
        audio_uri=TEST_AUDIO_URI or None,
        output_srt=TEST_SRT,
        output_json=TEST_JSON,
        max_lines=TEST_MAX_LINES,
        words_per_line=TEST_WORDS_PER_LINE,
        poll_timeout=TEST_TIMEOUT,
    )

    if result.success:
        print(result.message)
        if result.data:
            print("\n--- 识别文本 ---")
            print(result.data.get("full_text", ""))
            if result.data.get("output_srt"):
                print(f"\nSRT 已写入: {result.data['output_srt']}")
        return 0

    print(f"错误: {result.message}", file=sys.stderr)
    if result.data:
        print(json.dumps(result.data, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
