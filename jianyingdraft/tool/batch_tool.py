# -*- coding: utf-8 -*-
"""批量 MCP 工具：减少分镜制作时的往返次数。"""
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from jianyingdraft.services.audio_service import DEFAULT_SPEAKER
from jianyingdraft.services.batch_service import batch_add_segments_service, batch_create_tracks_service
from jianyingdraft.services.segment_builder_service import build_narration_segments_service
from jianyingdraft.utils.media_parser import get_media_duration
from jianyingdraft.utils.response import ToolResponse
from jianyingdraft.utils.time_format import safe_media_duration_seconds


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
                - target_start_end: "开始s-结束s"（绝对结束时间；内部按毫秒计算，避免浮点误差）
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
            每项含 path、duration（秒，毫秒精度、最多 3 位小数，解析失败为 null）
        """
        if not media_paths:
            return ToolResponse(success=False, message="media_paths 不能为空")

        items = []
        for path in media_paths:
            # 毫秒取整后的安全可用时长（已含 0.2s 余量），避免 Agent 浮点累加越界
            duration = safe_media_duration_seconds(get_media_duration(path))
            items.append({"path": path, "duration": duration, "duration_unit": "seconds"})

        return ToolResponse(
            success=True,
            message=f"已解析 {len(items)} 个媒体文件",
            data={"items": items, "total": len(items)},
        )

    @mcp.tool()
    def build_narration_segments(
        output_dir: str,
        subtitle_items: List[Dict[str, Any]],
        bg_material: str,
        speaker: str = DEFAULT_SPEAKER,
        video_items: Optional[List[Dict[str, Any]]] = None,
        skip_asr: bool = False,
        force_tts: bool = False,
        write_segments_path: Optional[str] = None,
        sub_style: Optional[Dict[str, Any]] = None,
        sub_clip: Optional[Dict[str, Any]] = None,
    ) -> ToolResponse:
        """
        分镜旁白一键构建：句号级 TTS + ASR 字幕对齐 + 生成 batch_add_segments 片段列表。

        **Agent 必须通过本 MCP 工具完成旁白制作，禁止直接运行仓库内 scripts/*.py 或 aidata 工程脚本。**

        流程:
          1. 将 subtitle_items 按句号/问号/感叹号/分号合并 TTS（逗号不切，保证语音连贯）
          2. 每句生成一个 mp3 到 output_dir（如 S01_sent00.mp3）
          3. recognize_subtitles 识别句内字幕时间轴（skip_asr=true 时按字数比例分配）
          4. 返回 segments 可直接传入 batch_add_segments

        Args:
            output_dir: aidata 工程目录绝对路径（TTS mp3 输出目录）
            subtitle_items: 字幕规划列表，每项含:
                - filename: 规划文件名（如 S01_L01.mp3，仅用于提取镜头编号 S01）
                - display: 字幕显示文本（无标点，≤12 字）
                - tts_text: TTS 文本（可含标点；句号处切分合成）
                - skip_tts: 可选，true 表示仅显示字幕、TTS 已含于前一条
            bg_material: 全片背景绝对路径或 URL
            speaker: TTS 发音人，默认 BV009_streaming
            video_items: 可选，画面素材列表，每项含 track/material/shot_id/clip_settings 等；
                end=0 表示持续到镜头结束；start_subtitle 绑定镜头内字幕序号对齐入场
            skip_asr: 跳过 ASR，按字数比例分配字幕时间（离线调试用）
            force_tts: 强制重新生成句号级 mp3
            write_segments_path: 可选，将 segments 写入该 JSON 路径
            sub_style: 字幕样式，默认 size=8 align=1 color=[0.1,0.1,0.2]
            sub_clip: 字幕 clip_settings，默认 transform_y=-0.85

        Returns:
            data.segments — 可直接传给 batch_add_segments
            data.meta — 句号分组、对齐字幕、音频路径等元数据
            data.total_duration — 全片时长（秒）
        """
        default_style = {"size": 8.0, "align": 1, "color": [0.1, 0.1, 0.2]}
        default_clip = {"transform_y": -0.85}
        return build_narration_segments_service(
            output_dir=output_dir,
            subtitle_items=subtitle_items,
            speaker=speaker,
            bg_material=bg_material,
            video_items=video_items,
            skip_asr=skip_asr,
            force_tts=force_tts,
            write_segments_path=write_segments_path,
            sub_style=sub_style or default_style,
            sub_clip=sub_clip or default_clip,
        )
