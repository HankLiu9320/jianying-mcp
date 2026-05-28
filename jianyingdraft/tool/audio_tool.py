# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: audio_tool.py
"""
from typing import Optional, List
from mcp.server.fastmcp import FastMCP
from jianyingdraft.services.audio_service import add_audio_segment_service, add_audio_effect_service, \
    add_audio_fade_service, add_audio_keyframe_service, text_to_speech_service
from jianyingdraft.utils.response import ToolResponse
from jianyingdraft.utils.index_manager import index_manager
from jianyingdraft.utils.time_format import parse_start_end_format


def audio_tools(mcp: FastMCP):
    @mcp.tool()
    def add_audio_segment(
            track_id: str,
            material: str,
            target_start_end: str,
            source_start_end: Optional[str] = None,
            speed: Optional[float] = None,
            volume: float = 1.0,
            change_pitch: bool = False
    ) -> ToolResponse:
        """
        添加音频片段到指定轨道，须注意 target_start_end和 source_start_end 的使用规则

        Args:
            track_id: 轨道ID，通过create_track获得
            material: 音频文件路径，支持本地文件路径或URL
            target_start_end: 片段在轨道上的目标时间范围，格式如 "0s-4.2s",表示在轨道上从0s开始，持续4.2s，target_start_end参数描述的是轨道上的时间范围，同一轨道中不可有重复时间段，即0s-4.2s和4s-5s，第一段素材最后0.2s与第二段素材重叠了，只能是0s-4.2s和4.ss-5s
            source_start_end: 从源音频文件中截取的时间范围，格式如 "1s-4.2s"，表示从源音频的1s开始截取，到4.2s结束（可选），source_start_end参数描述的是素材本身取的时长，默认取全部时长，一般情况下不设置，除非用户说明，若素材时长为5s,用户需要取其中1s-5s的内容，才配置
            speed: 播放速度，默认为1.0。此项与source_timerange同时指定时，将覆盖target_timerange中的时长（可选）
            volume: 音量，默认为1.0
            change_pitch: 是否跟随变速改变音调，默认为False
        """
        try:
            target_timerange = parse_start_end_format(target_start_end)
        except ValueError as e:
            return ToolResponse(
                success=False,
                message=f"target_start_end格式错误: {str(e)}"
            )

        source_timerange = None
        if source_start_end is not None:
            try:
                source_timerange = parse_start_end_format(source_start_end)
            except ValueError as e:
                return ToolResponse(
                    success=False,
                    message=f"source_start_end格式错误: {str(e)}"
                )
        # 参数验证
        if speed is not None and speed <= 0:
            return ToolResponse(
                success=False,
                message=f"播放速度必须大于0，当前值: {speed}"
            )

        if volume < 0:
            return ToolResponse(
                success=False,
                message=f"音量不能为负数，当前值: {volume}"
            )

        # 通过track_id获取draft_id和track_name
        draft_id = index_manager.get_draft_id_by_track_id(track_id)
        track_name = index_manager.get_track_name_by_track_id(track_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到轨道ID对应的草稿: {track_id}"
            )

        if not track_name:
            return ToolResponse(
                success=False,
                message=f"未找到轨道ID对应的轨道名: {track_id}"
            )

        # 调用服务层处理业务逻辑
        result = add_audio_segment_service(
            draft_id=draft_id,
            material=material,
            target_timerange=target_timerange,
            source_timerange=source_timerange,
            speed=speed,
            volume=volume,
            change_pitch=change_pitch,
            track_name=track_name
        )

        # 如果音频片段添加成功，添加索引记录
        if result.success and result.data and "audio_segment_id" in result.data:
            audio_segment_id = result.data["audio_segment_id"]
            index_manager.add_audio_segment_mapping(audio_segment_id, track_id)

        return result

    @mcp.tool()
    def add_audio_effect(
            audio_segment_id: str,
            effect_type: str,
            effect_name: str,
            params: Optional[List[Optional[float]]] = None
    ) -> ToolResponse:
        """
        为音频片段添加特效

        Args:
            audio_segment_id: 音频片段ID，通过add_audio_segment获得
            effect_type: 特效类型，支持以下类型：
                - "AudioSceneEffectType": 场景音效（如雨声、风声等）
                - "ToneEffectType": 音调特效（如机器人、电音等）
                - "SpeechToSongType": 语音转歌声特效（如Lofi、流行等）
            effect_name: 特效名称，如 "雨声", "机器人", "Lofi", "电音", "回声" 等，可以使用find_effects_by_type工具，资源类型选择AudioSceneEffectType、ToneEffectType、SpeechToSongType，从而获取特效类型有哪些
            params: 特效参数列表（可选），参数范围0-100，具体参数数量和含义取决于特效类型，一般不做修改
        """
        # 参数验证
        valid_types = ["AudioSceneEffectType", "ToneEffectType", "SpeechToSongType"]
        if effect_type not in valid_types:
            return ToolResponse(
                success=False,
                message=f"无效的特效类型 '{effect_type}'，支持的类型: {', '.join(valid_types)}"
            )

        # 验证参数范围
        if params:
            for i, param in enumerate(params):
                if param is not None and not (0.0 <= param <= 100.0):
                    return ToolResponse(
                        success=False,
                        message=f"参数{i + 1}超出范围，必须在0-100之间，当前值: {param}"
                    )

        # 音频特效存在性验证（音频特效使用 name 字段）
        from jianyingdraft.utils.effect_manager import JianYingResourceManager
        manager = JianYingResourceManager()

        effects = manager.find_by_type(
            effect_type=effect_type,
            keyword=effect_name,
            limit=1
        )

        # 检查是否找到完全匹配的特效
        exact_match = False
        if effects:
            for effect in effects:
                if effect.get('name') == effect_name:
                    exact_match = True
                    break

        if not effects or not exact_match:
            # 获取建议特效
            effect_suggestions = manager.find_by_type(effect_type, keyword=effect_name)

            all_suggestions = []
            for effect in effect_suggestions:
                if effect.get('name'):
                    all_suggestions.append(effect.get('name'))

            return ToolResponse(
                success=False,
                message=f"在 {effect_type} 中未找到特效 '{effect_name}',请确认名称是否正确，或使用相关特效: {', '.join(all_suggestions)}",
                data={
                    "error_type": "effect_not_found",
                    "effect_type": effect_type,
                    "effect_name": effect_name,
                    "suggestions": all_suggestions
                }
            )

        # 通过audio_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_audio_segment_id(audio_segment_id)
        track_info = index_manager.get_track_info_by_audio_segment_id(audio_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到音频片段ID对应的草稿: {audio_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到音频片段ID对应的轨道信息: {audio_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_audio_effect_service(
            draft_id=draft_id,
            audio_segment_id=audio_segment_id,
            effect_type=effect_type,
            effect_name=effect_name,
            params=params,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_audio_fade(
            audio_segment_id: str,
            in_duration: str,
            out_duration: str
    ) -> ToolResponse:
        """
        为音频片段添加淡入淡出效果

        Args:
            audio_segment_id: 音频片段ID，通过add_audio_segment获得
            in_duration: 音频淡入时长，格式如 "1s", "500ms", "0.5s"
            out_duration: 音频淡出时长，格式如 "1s", "500ms", "0.5s"
        """
        # 参数验证
        if not in_duration or not out_duration:
            return ToolResponse(
                success=False,
                message="淡入时长和淡出时长不能为空"
            )

        # 简单的时间格式验证
        def validate_duration(duration: str) -> bool:
            """验证时间格式是否正确"""
            if not duration:
                return False
            # 检查是否以s或ms结尾
            if not (duration.endswith('s') or duration.endswith('ms')):
                return False
            # 检查数字部分
            try:
                if duration.endswith('ms'):
                    float(duration[:-2])
                else:
                    float(duration[:-1])
                return True
            except ValueError:
                return False

        if not validate_duration(in_duration):
            return ToolResponse(
                success=False,
                message=f"无效的淡入时长格式: {in_duration}，正确格式如 '1s', '500ms'"
            )

        if not validate_duration(out_duration):
            return ToolResponse(
                success=False,
                message=f"无效的淡出时长格式: {out_duration}，正确格式如 '1s', '500ms'"
            )

        # 通过audio_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_audio_segment_id(audio_segment_id)
        track_info = index_manager.get_track_info_by_audio_segment_id(audio_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到音频片段ID对应的草稿: {audio_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到音频片段ID对应的轨道信息: {audio_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_audio_fade_service(
            draft_id=draft_id,
            audio_segment_id=audio_segment_id,
            in_duration=in_duration,
            out_duration=out_duration,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_audio_keyframe(
            audio_segment_id: str,
            time_offset: str,
            volume: float
    ) -> ToolResponse:
        """
        为音频片段添加音量关键帧

        Args:
            audio_segment_id: 音频片段ID，通过add_audio_segment获得
            time_offset: 关键帧的时间偏移量，格式如 "0s", "1.5s", "500ms"
            volume: 音量在time_offset处的值，范围通常0.0-1.0，也可以大于1.0实现增益效果
        """
        # 参数验证
        if not time_offset:
            return ToolResponse(
                success=False,
                message="时间偏移量不能为空"
            )

        if volume < 0.0:
            return ToolResponse(
                success=False,
                message=f"音量值不能为负数，当前值: {volume}"
            )

        # 时间格式验证
        def validate_time_offset(time_offset: str) -> bool:
            """验证时间偏移量格式是否正确"""
            if not time_offset:
                return False
            # 检查是否以s或ms结尾
            if not (time_offset.endswith('s') or time_offset.endswith('ms')):
                return False
            # 检查数字部分
            try:
                if time_offset.endswith('ms'):
                    float(time_offset[:-2])
                else:
                    float(time_offset[:-1])
                return True
            except ValueError:
                return False

        if not validate_time_offset(time_offset):
            return ToolResponse(
                success=False,
                message=f"无效的时间偏移量格式: {time_offset}，正确格式如 '1.5s', '500ms'"
            )

        # 通过audio_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_audio_segment_id(audio_segment_id)
        track_info = index_manager.get_track_info_by_audio_segment_id(audio_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到音频片段ID对应的草稿: {audio_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到音频片段ID对应的轨道信息: {audio_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_audio_keyframe_service(
            draft_id=draft_id,
            audio_segment_id=audio_segment_id,
            time_offset=time_offset,
            volume=volume,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def text_to_speech(
            text: str,
            speaker: Optional[str] = None,
            voice: Optional[str] = None,
            output_name: Optional[str] = None
    ) -> ToolResponse:
        """
        文本转语音，基于 WebSocket 调用字节 TTS，输出 mp3 到 material 目录

        Args:
            text: 需要转语音的文本内容
            speaker: 发音人（可选），默认 BV411_streaming
            voice: speaker 的兼容别名（可选）
            output_name: 输出文件名（可选），默认自动生成，后缀为 .mp3
        """
        if not text or not text.strip():
            return ToolResponse(
                success=False,
                message="text 不能为空"
            )

        return text_to_speech_service(
            text=text,
            speaker=speaker or voice,
            output_name=output_name
        )


