# -*- coding: utf-8 -*-
"""批量 MCP 工具：减少分镜制作时的往返次数。"""
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from jianyingdraft.services.batch_service import batch_add_segments_service, batch_create_tracks_service
from jianyingdraft.utils.media_parser import get_media_duration
from jianyingdraft.utils.response import ToolResponse


def batch_tools(mcp: FastMCP):
    @mcp.tool()
    def batch_create_tracks(
        draft_id: str,
        tracks: List[Dict[str, str]],
        stop_on_error: bool = True,
    ) -> ToolResponse:
        """
        批量创建轨道（一次调用替代多次 create_track）。

        Args:
            draft_id: 草稿 ID
            tracks: 轨道列表，每项含 track_type、track_name。示例:
                [{"track_type": "video", "track_name": "video_bg"}, ...]
            stop_on_error: 遇到失败是否立即停止，默认 True

        Returns:
            含 track_map（track_name -> track_id）及每条创建结果
        """
        return batch_create_tracks_service(draft_id, tracks, stop_on_error)

    @mcp.tool()
    def batch_add_segments(
        draft_id: str,
        segments: List[Dict[str, Any]],
        stop_on_error: bool = True,
    ) -> ToolResponse:
        """
        批量添加 video/audio/text 片段（一次调用替代多次 add_*_segment）。

        Args:
            draft_id: 草稿 ID
            segments: 片段列表。每项必填:
                - type: "video" | "audio" | "text"
                - track_name 或 track_id
                - target_start_end: "开始s-结束s"（绝对结束时间）
              video/audio 还需 material；text 还需 text。
              可选字段与单条 add_*_segment 相同（clip_settings、style 等）。
              video/text 可选内联动效（分镜动效类型/动效名称列）:
                - animation_type: IntroType / TextIntro 等
                - animation_name: 渐显 / 放大 等（须与 animation_type 同时提供）
                - animation_duration: 可选，如 "0.5s"
            stop_on_error: 遇到失败是否立即停止，默认 True

        Examples:
            batch_add_segments("draft_id", [
              {"type": "video", "track_name": "video_bg", "material": "/path/bg.png", "target_start_end": "0s-3s"},
              {"type": "video", "track_name": "video_layer1", "material": "/path/role.png", "target_start_end": "0.3s-3s",
               "clip_settings": {"scale_x": 0.45, "scale_y": 0.45, "transform_x": -0.55, "transform_y": -0.45},
               "animation_type": "IntroType", "animation_name": "渐显"},
              {"type": "audio", "track_name": "audio_narration", "material": "/path/a.mp3", "target_start_end": "0s-1.2s"},
              {"type": "text", "track_name": "text_subtitle", "text": "字幕", "target_start_end": "0s-1.2s",
               "style": {"size": 8.0, "align": 1},
               "clip_settings": {"transform_y": -0.85},
               "animation_type": "TextIntro", "animation_name": "渐显"}
            ])
        """
        return batch_add_segments_service(draft_id, segments, stop_on_error)

    @mcp.tool()
    def batch_parse_media_durations(
        media_paths: List[str],
    ) -> ToolResponse:
        """
        批量解析媒体时长（一次调用替代多次 parse_media_info）。

        Args:
            media_paths: 媒体文件绝对路径列表

        Returns:
            每项含 path、duration（秒，解析失败为 null）
        """
        if not media_paths:
            return ToolResponse(success=False, message="media_paths 不能为空")

        items = []
        for path in media_paths:
            duration = get_media_duration(path)
            items.append({"path": path, "duration": duration})

        return ToolResponse(
            success=True,
            message=f"已解析 {len(items)} 个媒体文件",
            data={"items": items, "total": len(items)},
        )
