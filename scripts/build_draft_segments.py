#!/usr/bin/env python3
"""[已废弃 · 勿直接运行]

分镜旁白制作请通过 jianying-mcp MCP 工具 `build_narration_segments` 调用。
本文件仅保留作开发调试参考，Agent 不应执行。

正确流程（任意工作目录均可）:
  1. user-jianying-mcp → build_narration_segments(output_dir, subtitle_items, bg_material, ...)
  2. user-jianying-mcp → batch_add_segments(draft_id, segments=上一步返回的 data.segments)
"""
raise SystemExit(
    "请使用 MCP 工具 build_narration_segments，勿直接运行本脚本。"
    "参见 jianyingdraft/tool/batch_tool.py"
)
