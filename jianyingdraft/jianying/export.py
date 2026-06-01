# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: export.py
"""
import json
import os
import sys
import shutil
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dotenv import load_dotenv
from pyJianYingDraft import (
    VideoSegment, VideoMaterial, Timerange, ClipSettings, DraftFolder,
    FilterType, TransitionType, IntroType, OutroType, GroupAnimationType,
    MaskType, KeyframeProperty, tim, trange, TrackType
)

# 加载环境变量
load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')
OUTPUT_PATH = os.getenv('OUTPUT_PATH')


class ExportDraft:
    """
    草稿导出类
    负责读取JSON数据并生成完整的剪映草稿
    """

    def __init__(self, output_path: str = None, export_zip: bool = False):
        """
        初始化导出器

        Args:
            output_path: 导出路径，如果不指定则使用config中的OUTPUT_PATH
        """
        self.output_path = output_path or OUTPUT_PATH
        # 确保导出目录存在
        os.makedirs(self.output_path, exist_ok=True)
        self.export_zip = export_zip
        self.draft_folder = DraftFolder(self.output_path)
        # 初始化日志收集器
        self.export_logs = []

    def _log(self, message: str, level: str = "info"):
        """
        记录日志信息

        Args:
            message: 日志消息
            level: 日志级别 (info, warning, error)
        """
        log_entry = {
            "level": level,
            "message": message
        }
        self.export_logs.append(log_entry)
        # MCP 使用 stdio JSON-RPC，stdout 只能用于协议通信；日志写入 stderr
        print(message, file=sys.stderr, flush=True)

    @staticmethod
    def _build_clip_settings(clip_data: Dict[str, Any]) -> ClipSettings:
        """从 JSON 中的 clip_settings 字典构建 ClipSettings。"""
        return ClipSettings(
            alpha=clip_data.get("alpha", 1.0),
            flip_horizontal=clip_data.get("flip_horizontal", False),
            flip_vertical=clip_data.get("flip_vertical", False),
            rotation=clip_data.get("rotation", 0.0),
            scale_x=clip_data.get("scale_x", 1.0),
            scale_y=clip_data.get("scale_y", 1.0),
            transform_x=clip_data.get("transform_x", 0.0),
            transform_y=clip_data.get("transform_y", 0.0),
        )

    def export(self, draft_id: str) -> dict:
        """
        导出草稿
        
        Args:
            draft_id: 草稿ID
            
        Returns:
            bool: 导出是否成功
        """
        try:
            self._log(f"开始导出草稿: {draft_id}")

            # 验证草稿数据是否存在
            draft_data_path = f"{SAVE_PATH}/{draft_id}"
            if not os.path.exists(draft_data_path):
                raise FileNotFoundError(f"草稿数据不存在: {draft_data_path}")

            # 验证导出路径是否存在
            if not os.path.exists(self.output_path):
                raise FileNotFoundError(f"导出路径不存在: {self.output_path}")

            # 1. 读取所有数据
            draft_info = self._load_draft_data(draft_id)
            track_data = self._load_track_data(draft_id)
            video_data = self._load_video_data(draft_id)
            text_data = self._load_text_data(draft_id)
            audio_data = self._load_audio_data(draft_id)

            if not draft_info:
                raise FileNotFoundError(f"未找到草稿信息文件: {draft_id}/draft.json")

            # 2. 验证目标草稿是否已存在
            draft_name = draft_info.get("draft_name", f"Draft_{draft_id}")
            # 3. 创建草稿
            width = draft_info.get("width", 1920)
            height = draft_info.get("height", 1080)
            if os.path.exists(os.path.join(self.output_path, draft_name)):
                # 删除文件夹
                shutil.rmtree(os.path.join(self.output_path, draft_name))
            script = self.draft_folder.create_draft(draft_name, width, height)

            # 3. 复制素材文件
            self._copy_material_files(draft_id, draft_name)

            # 4. 添加轨道
            self._create_tracks(script, track_data)

            # 5. 处理视频片段
            video_segments = self._process_video_segments(video_data, draft_name)

            # 6. 处理文本片段
            text_segments = self._process_text_segments(text_data)

            # 7. 处理音频片段
            audio_segments = self._process_audio_segments(audio_data, draft_name)

            # 8. 添加视频片段到轨道
            self._add_video_segments_to_tracks(script, video_segments)

            # 为文本片段分配轨道
            self._add_text_segments_to_tracks(script, text_segments)

            # 为音频片段分配轨道
            self._add_audio_segments_to_tracks(script, audio_segments)

            # 9. 保存草稿
            script.save()

            data = {
                "output": self.output_path,
                "draft_name": draft_name,
                "export_logs": self.export_logs,
                "summary": {
                    "total_logs": len(self.export_logs),
                    "info_count": len([log for log in self.export_logs if log["level"] == "info"]),
                    "warning_count": len([log for log in self.export_logs if log["level"] == "warning"]),
                    "error_count": len([log for log in self.export_logs if log["level"] == "error"])
                }
            }
            return data

        except Exception as e:
            self._log(f"导出草稿失败: {e}", "error")
            import traceback
            traceback.print_exc()
            return {
                "output": self.output_path,
                "draft_name": draft_name,
                "export_logs": self.export_logs,
                "summary": {
                    "total_logs": len(self.export_logs),
                    "info_count": len([log for log in self.export_logs if log["level"] == "info"]),
                    "warning_count": len([log for log in self.export_logs if log["level"] == "warning"]),
                    "error_count": len([])
                }
            }

    def _copy_material_files(self, draft_id: str, draft_name: str):
        """
        复制素材文件到导出目录

        Args:
            draft_id: 草稿ID
            draft_name: 草稿名称
        """
        try:
            # 源素材目录
            source_material_dir = os.path.join(SAVE_PATH, draft_id, "material")

            # 目标素材目录
            target_material_dir = os.path.join(self.output_path, draft_name, "material")

            # 检查源目录是否存在
            if not os.path.exists(source_material_dir):
                self._log(f"素材目录不存在，跳过复制: {source_material_dir}", "warning")
                return

            # 创建目标目录
            os.makedirs(target_material_dir, exist_ok=True)

            # 复制所有素材文件
            copied_count = 0
            for filename in os.listdir(source_material_dir):
                source_file = os.path.join(source_material_dir, filename)
                target_file = os.path.join(target_material_dir, filename)

                if os.path.isfile(source_file):
                    shutil.copy2(source_file, target_file)
                    copied_count += 1
                    self._log(f"复制素材文件: {filename}")

            self._log(f"素材文件复制完成，共复制 {copied_count} 个文件")

        except Exception as e:
            self._log(f"复制素材文件失败: {e}", "error")
            # 不抛出异常，允许导出继续进行

    def _resolve_material_path(self, material_path: str, draft_name: str) -> str:
        """
        解析素材路径，确保返回相对于导出草稿根目录的相对路径

        Args:
            material_path: 素材路径（可能是绝对路径或相对路径）
            draft_name: 草稿名称

        Returns:
            str: 解析后的绝对路径
        """
        # 如果已经是绝对路径，直接返回
        if os.path.isabs(material_path):
            return material_path

        # 如果是相对路径，转换为导出目录下的绝对路径
        if material_path.startswith('material/'):
            # 相对于导出目录的路径
            export_material_path = os.path.join(self.output_path, draft_name, material_path)
            return os.path.abspath(export_material_path)
        else:
            # 其他情况，假设是相对于导出目录的路径
            export_material_path = os.path.join(self.output_path, draft_name, "material", material_path)
            return os.path.abspath(export_material_path)

    def _load_draft_data(self, draft_id: str) -> Dict[str, Any]:
        """加载草稿基本信息"""
        try:
            file_path = f"{SAVE_PATH}/{draft_id}/draft.json"
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 如果是列表，取第一个元素
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                    elif isinstance(data, dict):
                        return data
            return {}
        except Exception as e:
            self._log(f"加载草稿数据失败: {e}", "error")
            return {}

    def _load_track_data(self, draft_id: str) -> List[Dict[str, Any]]:
        """加载轨道数据"""
        try:
            file_path = f"{SAVE_PATH}/{draft_id}/track.json"
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            self._log(f"加载轨道数据失败: {e}", "error")
            return []

    def _load_video_data(self, draft_id: str) -> List[Dict[str, Any]]:
        """加载视频数据"""
        try:
            file_path = f"{SAVE_PATH}/{draft_id}/video.json"
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            self._log(f"加载视频数据失败: {e}", "error")
            return []

    def _load_text_data(self, draft_id: str) -> List[Dict[str, Any]]:
        """加载文本数据"""
        try:
            file_path = f"{SAVE_PATH}/{draft_id}/text.json"
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            self._log(f"加载文本数据失败: {e}", "error")
            return []

    def _load_audio_data(self, draft_id: str) -> List[Dict[str, Any]]:
        """加载音频数据"""
        try:
            file_path = f"{SAVE_PATH}/{draft_id}/audio.json"
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            self._log(f"加载音频数据失败: {e}", "error")
            return []

    def _create_tracks(self, script, track_data: List[Dict[str, Any]]):
        """创建轨道"""
        for track_info in track_data:
            if track_info.get("operation") == "add_track":
                track_params = track_info.get("add_track", {})
                track_type = track_params.get("track_type")
                track_name = track_params.get("track_name")  # 获取轨道名称

                if track_type == "video":
                    if track_name:
                        script.add_track(TrackType.video, track_name)
                    else:
                        script.add_track(TrackType.video)
                elif track_type == "audio":
                    if track_name:
                        script.add_track(TrackType.audio, track_name)
                    else:
                        script.add_track(TrackType.audio)
                elif track_type == "text":
                    if track_name:
                        script.add_track(TrackType.text, track_name)
                    else:
                        script.add_track(TrackType.text)

                display_name = track_name if track_name else track_type
                self._log(f"添加轨道: {display_name}")

    def _add_video_segments_to_tracks(self, script, video_segments):
        """将视频片段添加到对应的轨道上"""
        if not video_segments:
            return

        # 为每个视频片段找到对应的轨道
        for segment_info in video_segments:
            segment = segment_info['segment']
            track_name = segment_info.get('track_name')  # 从JSON数据中获取轨道名称

            # 添加视频片段到轨道
            try:
                if track_name:
                    script.add_segment(segment, track_name=track_name)
                    self._log(f"视频片段添加到轨道 '{track_name}'")
                else:
                    script.add_segment(segment)
                    self._log(f"视频片段添加到默认轨道")
            except Exception as e:
                self._log(f"添加视频片段失败: {e}", "error")
                continue

    def _add_text_segments_to_tracks(self, script, text_segments):
        """将文本片段添加到对应的轨道上"""
        if not text_segments:
            return

        # 为每个文本片段找到对应的轨道
        for segment_info in text_segments:
            segment = segment_info['segment']
            track_name = segment_info.get('track_name')  # 从JSON数据中获取轨道名称

            # 添加文本片段到轨道
            try:
                if track_name:
                    script.add_segment(segment, track_name=track_name)
                    self._log(f"文本片段 '{segment.text[:20]}...' 添加到轨道 '{track_name}'")
                else:
                    script.add_segment(segment)
                    self._log(f"文本片段 '{segment.text[:20]}...' 添加到默认轨道", "warning")
            except Exception as e:
                self._log(f"添加文本片段失败: {e}", "error")
                continue

    def _process_video_segments(self, video_data: List[Dict[str, Any]], draft_name: str) -> List[VideoSegment]:
        """处理视频片段数据"""
        # 按video_segment_id分组
        segments_by_id = defaultdict(list)
        for item in video_data:
            segment_id = item.get("video_segment_id")
            if segment_id:
                segments_by_id[segment_id].append(item)

        video_segments = []

        for segment_id, operations in segments_by_id.items():
            self._log(f"处理视频片段: {segment_id}")

            # 找到add_video_segment操作
            create_operation = None
            other_operations = []

            for op in operations:
                if op.get("operation") == "add_video_segment":
                    create_operation = op
                else:
                    other_operations.append(op)

            if not create_operation:
                self._log(f"未找到创建操作: {segment_id}", "warning")
                continue

            # 创建VideoSegment实例
            video_segment = self._create_video_segment(create_operation, draft_name)
            if not video_segment:
                continue

            # 应用其他操作
            for op in other_operations:
                self._apply_operation(video_segment, op)

            # 获取轨道名称
            track_name = create_operation.get("track_name")

            # 构建包含轨道信息的数据结构
            segment_info = {
                'segment': video_segment,
                'track_name': track_name
            }

            video_segments.append(segment_info)

        return video_segments

    def _process_audio_segments(self, audio_data: List[Dict[str, Any]], draft_name: str) -> List:
        """处理音频片段数据"""
        # 按audio_segment_id分组
        segments_by_id = defaultdict(list)
        for item in audio_data:
            segment_id = item.get("audio_segment_id")
            if segment_id:
                segments_by_id[segment_id].append(item)

        audio_segments = []

        for segment_id, operations in segments_by_id.items():
            self._log(f"处理音频片段: {segment_id}")

            # 找到add_audio_segment操作
            create_operation = None
            other_operations = []

            for op in operations:
                if op.get("operation") == "add_audio_segment":
                    create_operation = op
                else:
                    other_operations.append(op)

            if not create_operation:
                self._log(f"未找到创建操作: {segment_id}")
                continue

            # 创建AudioSegment实例
            audio_segment = self._create_audio_segment(create_operation, draft_name)
            if not audio_segment:
                continue

            # 应用其他操作
            for op in other_operations:
                self._apply_audio_operation(audio_segment, op)

            # 获取轨道名称
            track_name = create_operation.get("track_name")

            # 构建包含轨道信息的数据结构
            segment_info = {
                'segment': audio_segment,
                'track_name': track_name
            }

            audio_segments.append(segment_info)

        return audio_segments

    def _add_audio_segments_to_tracks(self, script, audio_segments):
        """将音频片段添加到对应的轨道上"""
        if not audio_segments:
            return

        # 为每个音频片段找到对应的轨道
        for segment_info in audio_segments:
            segment = segment_info['segment']
            track_name = segment_info.get('track_name')  # 从JSON数据中获取轨道名称

            # 添加音频片段到轨道
            try:
                if track_name:
                    script.add_segment(segment, track_name=track_name)
                    self._log(f"音频片段添加到轨道 '{track_name}'")
                else:
                    script.add_segment(segment)
                    self._log(f"音频片段添加到默认轨道", "warning")
            except Exception as e:
                self._log(f"添加音频片段失败: {e}", "error")
                continue

    def _process_text_segments(self, text_data: List[Dict[str, Any]]) -> List:
        """处理文本片段数据"""
        # 按text_segment_id分组
        segments_by_id = defaultdict(list)
        for item in text_data:
            segment_id = item.get("text_segment_id")
            if segment_id:
                segments_by_id[segment_id].append(item)

        text_segments = []

        for segment_id, operations in segments_by_id.items():
            self._log(f"处理文本片段: {segment_id}", )

            # 找到add_text_segment操作
            create_operation = None
            other_operations = []

            for op in operations:
                if op.get("operation") == "add_text_segment":
                    create_operation = op
                else:
                    other_operations.append(op)

            if not create_operation:
                self._log(f"未找到创建操作: {segment_id}")
                continue

            # 创建TextSegment实例
            text_segment = self._create_text_segment(create_operation)
            if not text_segment:
                continue

            # 应用其他操作
            for op in other_operations:
                self._apply_text_operation(text_segment, op)

            # 获取轨道名称
            track_name = create_operation.get("track_name")

            # 构建包含轨道信息的数据结构
            segment_info = {
                'segment': text_segment,
                'track_name': track_name
            }

            text_segments.append(segment_info)

        return text_segments

    def _apply_text_operation(self, text_segment, operation: Dict[str, Any]):
        """应用文本操作到TextSegment"""
        try:
            op_type = operation.get("operation")

            if op_type == "add_animation":
                self._apply_text_animation(text_segment, operation.get("add_animation", {}))
            elif op_type == "add_bubble":
                self._apply_text_bubble(text_segment, operation.get("add_bubble", {}))
            elif op_type == "add_effect":
                self._apply_text_effect(text_segment, operation.get("add_effect", {}))
            else:
                self._log(f"未知文本操作类型: {op_type}", "warning")

        except Exception as e:
            self._log(f"应用文本操作失败 {op_type}: {e}", "error")

    def _apply_text_animation(self, text_segment, params: Dict[str, Any]):
        """应用文本动画"""
        from pyJianYingDraft import TextIntro, TextOutro, TextLoopAnim

        animation_type_str = params.get("animation_type")
        animation_name = params.get("animation_name")
        duration = params.get("duration")

        # 根据动画类型字符串获取对应的枚举
        animation_enum = None
        if animation_type_str == "TextIntro":
            animation_enum = self._find_enum_by_name(TextIntro, animation_name)
        elif animation_type_str == "TextOutro":
            animation_enum = self._find_enum_by_name(TextOutro, animation_name)
        elif animation_type_str == "TextLoopAnim":
            animation_enum = self._find_enum_by_name(TextLoopAnim, animation_name)

        if animation_enum:
            if duration:
                text_segment.add_animation(animation_enum, duration)
            else:
                text_segment.add_animation(animation_enum)
            self._log(f"添加文本动画: {animation_type_str}.{animation_name}")
        else:
            self._log(f"未找到文本动画: {animation_type_str}.{animation_name}", "warning")

    def _apply_text_bubble(self, text_segment, params: Dict[str, Any]):
        """应用文本气泡"""
        effect_id = params.get("effect_id")
        resource_id = params.get("resource_id")

        if effect_id and resource_id:
            text_segment.add_bubble(effect_id, resource_id)
            self._log(f"添加文本气泡: effect_id={effect_id}, resource_id={resource_id}")
        else:
            self._log(f"气泡参数不完整: effect_id={effect_id}, resource_id={resource_id}", "warning")

    def _apply_text_effect(self, text_segment, params: Dict[str, Any]):
        """应用文本花字效果"""
        effect_id = params.get("effect_id")

        if effect_id:
            text_segment.add_effect(effect_id)
            self._log(f"添加文本花字效果: effect_id={effect_id}")
        else:
            self._log(f"花字效果参数不完整: effect_id={effect_id}", "warning")

    def _create_audio_segment(self, create_operation: Dict[str, Any], draft_name: str):
        """创建AudioSegment实例"""
        try:
            from pyJianYingDraft import AudioSegment, AudioMaterial, trange

            params = create_operation.get("add_audio_segment", {})

            # 获取音频文件路径
            material = params.get("material")
            if not material:
                self._log("缺少material参数", "warning")
                return None

            # 转换相对路径为导出目录的绝对路径
            absolute_material_path = self._resolve_material_path(material, draft_name)

            # 解析时间范围
            target_timerange_data = params.get("target_timerange", {})
            target_start_str = target_timerange_data.get("start", "0s")
            target_duration_str = target_timerange_data.get("duration", "1s")

            target_timerange = trange(target_start_str, target_duration_str)

            # 处理源时间范围
            source_timerange = None
            if "source_timerange" in params:
                source_timerange_data = params["source_timerange"]
                source_start_str = source_timerange_data.get("start", "0s")
                source_duration_str = source_timerange_data.get("duration", "1s")
                source_timerange = trange(source_start_str, source_duration_str)

            # 获取其他参数
            speed = params.get("speed")
            volume = params.get("volume", 1.0)
            change_pitch = params.get("change_pitch", False)

            # 创建AudioSegment
            audio_segment = AudioSegment(
                material=absolute_material_path,  # 使用绝对路径
                target_timerange=target_timerange,
                source_timerange=source_timerange,
                speed=speed,
                volume=volume,
                change_pitch=change_pitch
            )

            self._log(f"创建AudioSegment成功: {material}")
            return audio_segment

        except Exception as e:
            self._log(f"创建AudioSegment失败: {e}", "error")
            return None

    def _apply_audio_operation(self, audio_segment, operation: Dict[str, Any]):
        """应用音频操作到AudioSegment"""
        try:
            op_type = operation.get("operation")

            if op_type == "add_effect":
                self._apply_audio_effect(audio_segment, operation.get("add_effect", {}))
            elif op_type == "add_fade":
                self._apply_audio_fade(audio_segment, operation.get("add_fade", {}))
            elif op_type == "add_keyframe":
                self._apply_audio_keyframe(audio_segment, operation.get("add_keyframe", {}))
            else:
                self._log(f"未知音频操作类型: {op_type}", "warning")

        except Exception as e:
            self._log(f"应用音频操作失败 {op_type}: {e}", "error")

    def _apply_audio_effect(self, audio_segment, params: Dict[str, Any]):
        """应用音频特效"""
        from pyJianYingDraft import AudioSceneEffectType
        from pyJianYingDraft.metadata import ToneEffectType, SpeechToSongType
        effect_type_str = params.get("effect_type")
        effect_name = params.get("effect_name")
        effect_params = params.get("params")

        # 根据特效类型字符串获取对应的枚举
        effect_enum = None
        if effect_type_str == "AudioSceneEffectType":
            effect_enum = self._find_enum_by_name(AudioSceneEffectType, effect_name)
        elif effect_type_str == "ToneEffectType":
            effect_enum = self._find_enum_by_name(ToneEffectType, effect_name)
        elif effect_type_str == "SpeechToSongType":
            effect_enum = self._find_enum_by_name(SpeechToSongType, effect_name)

        if effect_enum:
            if effect_params:
                audio_segment.add_effect(effect_enum, effect_params)
            else:
                audio_segment.add_effect(effect_enum)
            self._log(f"添加音频特效: {effect_type_str}.{effect_name}")
        else:
            self._log(f"未找到音频特效: {effect_type_str}.{effect_name}", "warning")

    def _apply_audio_fade(self, audio_segment, params: Dict[str, Any]):
        """应用音频淡入淡出"""
        in_duration = params.get("in_duration")
        out_duration = params.get("out_duration")

        if in_duration and out_duration:
            audio_segment.add_fade(in_duration, out_duration)
            self._log(f"添加音频淡入淡出: in={in_duration}, out={out_duration}")
        else:
            self._log(f"淡入淡出参数不完整: in_duration={in_duration}, out_duration={out_duration}", "warning")

    def _apply_audio_keyframe(self, audio_segment, params: Dict[str, Any]):
        """应用音频关键帧"""
        from pyJianYingDraft import tim

        time_offset_str = params.get("time_offset")
        volume = params.get("volume")

        if time_offset_str and volume is not None:
            # 将时间字符串转换为微秒
            time_offset_microseconds = tim(time_offset_str)
            audio_segment.add_keyframe(time_offset_microseconds, volume)
            self._log(f"添加音频关键帧: time_offset={time_offset_str}, volume={volume}")
        else:
            self._log(f"关键帧参数不完整: time_offset={time_offset_str}, volume={volume}", "warning")

    def _create_text_segment(self, create_operation: Dict[str, Any]):
        """创建TextSegment实例"""
        try:
            from pyJianYingDraft import TextSegment, TextStyle, TextBorder, TextBackground, FontType, Timerange, trange

            params = create_operation.get("add_text_segment", {})

            # 获取文本内容
            text = params.get("text")
            if not text:
                self._log("缺少text参数", "warning")
                return None

            # 解析时间范围
            timerange_data = params.get("timerange", {})
            start_str = timerange_data.get("start", "0s")
            duration_str = timerange_data.get("duration", "1s")

            timerange = trange(start_str, duration_str)

            # 处理字体
            font = None
            if "font" in params:
                font_name = params["font"]
                # 这里需要根据字体名称找到对应的FontType枚举
                font = self._find_enum_by_name(FontType, font_name) if font_name else None

            # 处理样式
            style = None
            if "style" in params:
                style_data = params["style"]
                # 确保color是三元组格式
                color_list = style_data.get("color", [1.0, 1.0, 1.0])
                if len(color_list) >= 3:
                    color_tuple = (float(color_list[0]), float(color_list[1]), float(color_list[2]))
                else:
                    color_tuple = (1.0, 1.0, 1.0)  # 默认白色

                style = TextStyle(
                    size=style_data.get("size", 8.0),
                    bold=style_data.get("bold", False),
                    italic=style_data.get("italic", False),
                    underline=style_data.get("underline", False),
                    color=color_tuple,
                    alpha=style_data.get("alpha", 1.0),
                    align=style_data.get("align", 0),
                    vertical=style_data.get("vertical", False),
                    letter_spacing=style_data.get("letter_spacing", 0),
                    line_spacing=style_data.get("line_spacing", 0),
                    auto_wrapping=style_data.get("auto_wrapping", False),
                    max_line_width=style_data.get("max_line_width", 0.82)
                )

            # 处理描边
            border = None
            if "border" in params:
                border_data = params["border"]
                # 确保color是三元组格式
                color_list = border_data.get("color", [0.0, 0.0, 0.0])
                if len(color_list) >= 3:
                    color_tuple = (float(color_list[0]), float(color_list[1]), float(color_list[2]))
                else:
                    color_tuple = (0.0, 0.0, 0.0)  # 默认黑色

                border = TextBorder(
                    alpha=border_data.get("alpha", 1.0),
                    color=color_tuple,
                    width=border_data.get("width", 40.0)
                )

            # 处理背景
            background = None
            if "background" in params:
                bg_data = params["background"]
                background = TextBackground(
                    color=bg_data.get("color", "#000000"),
                    style=bg_data.get("style", 1),
                    alpha=bg_data.get("alpha", 1.0),
                    round_radius=bg_data.get("round_radius", 0.0),
                    height=bg_data.get("height", 0.14),
                    width=bg_data.get("width", 0.14),
                    horizontal_offset=bg_data.get("horizontal_offset", 0.5),
                    vertical_offset=bg_data.get("vertical_offset", 0.5)
                )

            clip_settings = None
            if "clip_settings" in params:
                clip_settings = self._build_clip_settings(params["clip_settings"])

            # 创建TextSegment
            text_segment = TextSegment(
                text=text,
                timerange=timerange,
                font=font,
                style=style,
                clip_settings=clip_settings,
                border=border,
                background=background
            )

            self._log(f"创建TextSegment成功: {text}")
            return text_segment

        except Exception as e:
            self._log(f"创建TextSegment失败: {e}", "error")
            return None

    def _create_video_segment(self, create_operation: Dict[str, Any], draft_name: str) -> Optional[VideoSegment]:
        """创建VideoSegment实例"""
        try:
            params = create_operation.get("add_video_segment", {})

            # 获取材料路径
            material_path = params.get("material")
            if not material_path:
                self._log("缺少material参数", "warning")
                return None

            # 转换相对路径为导出目录的绝对路径
            absolute_material_path = self._resolve_material_path(material_path, draft_name)

            # 创建VideoMaterial
            material = VideoMaterial(absolute_material_path)

            # 解析时间范围
            target_timerange_data = params.get("target_timerange", {})
            start_str = target_timerange_data.get("start", "0s")
            duration_str = target_timerange_data.get("duration", "1s")

            target_timerange = trange(start_str, duration_str)

            # 解析source_timerange（如果有）
            source_timerange = None
            if "source_timerange" in params:
                source_data = params["source_timerange"]
                if source_data:
                    source_start = source_data.get("start", "0s")
                    source_duration = source_data.get("duration", "1s")
                    source_timerange = trange(source_start, source_duration)

            clip_settings = None
            if "clip_settings" in params:
                clip_settings = self._build_clip_settings(params["clip_settings"])

            video_segment = VideoSegment(
                material=material,
                target_timerange=target_timerange,
                source_timerange=source_timerange,
                speed=params.get("speed"),
                volume=params.get("volume", 1.0),
                change_pitch=params.get("change_pitch", False),
                clip_settings=clip_settings,
            )

            self._log(f"创建VideoSegment成功: {material_path}")
            return video_segment

        except Exception as e:
            self._log(f"创建VideoSegment失败: {e}", "error")
            return None

    def _apply_operation(self, video_segment: VideoSegment, operation: Dict[str, Any]):
        """应用操作到VideoSegment"""
        try:
            op_type = operation.get("operation")

            if op_type == "add_animation":
                self._apply_animation(video_segment, operation.get("add_animation", {}))
            elif op_type == "add_filter":
                self._apply_filter(video_segment, operation.get("add_filter", {}))
            elif op_type == "add_mask":
                self._apply_mask(video_segment, operation.get("add_mask", {}))
            elif op_type == "add_transition":
                self._apply_transition(video_segment, operation.get("add_transition", {}))
            elif op_type == "add_background_filling":
                self._apply_background_filling(video_segment, operation.get("add_background_filling", {}))
            elif op_type == "add_keyframe":
                self._apply_keyframe(video_segment, operation.get("add_keyframe", {}))
            elif op_type == "add_effect":
                self._apply_effect(video_segment, operation.get("add_effect", {}))
            else:
                self._log(f"未知操作类型: {op_type}", "warning")

        except Exception as e:
            self._log(f"应用操作失败 {op_type}: {e}", "error")

    def _apply_animation(self, video_segment: VideoSegment, params: Dict[str, Any]):
        """应用动画"""
        animation_type_str = params.get("animation_type")
        animation_name = params.get("animation_name")
        duration = params.get("duration")

        # 根据类型字符串找到对应的枚举类
        animation_enum = None
        if animation_type_str == "IntroType":
            animation_enum = self._find_enum_by_name(IntroType, animation_name)
        elif animation_type_str == "OutroType":
            animation_enum = self._find_enum_by_name(OutroType, animation_name)
        elif animation_type_str == "GroupAnimationType":
            animation_enum = self._find_enum_by_name(GroupAnimationType, animation_name)

        if animation_enum:
            video_segment.add_animation(animation_enum, duration)
            self._log(f"添加动画: {animation_name}")
        else:
            self._log(f"未找到动画: {animation_type_str}.{animation_name}", "warning")

    def _apply_transition(self, video_segment: VideoSegment, params: Dict[str, Any]):
        """应用转场"""
        transition_name = params.get("transition_type")
        duration = params.get("duration")

        transition_enum = self._find_enum_by_name(TransitionType, transition_name)
        if transition_enum:
            video_segment.add_transition(transition_type=transition_enum, duration=duration)
            self._log(f"添加转场: {transition_name}")
        else:
            self._log(f"未找到转场: {transition_name}", "warning")

    def _apply_keyframe(self, video_segment: VideoSegment, params: Dict[str, Any]):
        """应用关键帧"""
        property_name = params.get("property")
        time_offset = params.get("time_offset")
        value = params.get("value")

        property_enum = self._find_enum_by_name(KeyframeProperty, property_name)
        if property_enum:
            video_segment.add_keyframe(property_enum, time_offset, value)
            self._log(f"添加关键帧: {property_name}")
        else:
            self._log(f"未找到属性: {property_name}", "warning")

    def _apply_filter(self, video_segment: VideoSegment, params: Dict[str, Any]):
        """应用滤镜"""
        filter_name = params.get("filter_type")
        intensity = params.get("intensity", 100.0)

        filter_enum = self._find_enum_by_name(FilterType, filter_name)
        if filter_enum:
            video_segment.add_filter(filter_enum, intensity)
            self._log(f"添加滤镜: {filter_name}")
        else:
            self._log(f"未找到滤镜: {filter_name}", "warning")

    def _apply_background_filling(self, video_segment: VideoSegment, params: Dict[str, Any]):
        """应用背景填充"""
        fill_type = params.get("fill_type", "blur")
        blur = params.get("blur", 0.0625)
        color = params.get("color", "#00000000")

        video_segment.add_background_filling(fill_type, blur, color)
        self._log(f"添加背景填充: {fill_type}")

    def _apply_mask(self, video_segment: VideoSegment, params: Dict[str, Any]):
        """应用蒙版"""
        mask_name = params.get("mask_type")
        center_x = params.get("center_x", 0.0)
        center_y = params.get("center_y", 0.0)
        size = params.get("size", 0.5)
        rotation = params.get("rotation", 0.0)
        feather = params.get("feather", 0.0)
        invert = params.get("invert", False)
        rect_width = params.get("rect_width")
        round_corner = params.get("round_corner")

        mask_enum = self._find_enum_by_name(MaskType, mask_name)
        if mask_enum:
            video_segment.add_mask(
                mask_enum,
                center_x=center_x,
                center_y=center_y,
                size=size,
                rotation=rotation,
                feather=feather,
                invert=invert,
                rect_width=rect_width,
                round_corner=round_corner
            )
            self._log(f"添加蒙版: {mask_name}")
        else:
            self._log(f"未找到蒙版: {mask_name}", "warning")

    def _apply_effect(self, video_segment: VideoSegment, params: Dict[str, Any]):
        """应用视频特效"""
        try:
            # 导入特效元数据
            from pyJianYingDraft.metadata import VideoSceneEffectType, VideoCharacterEffectType

            effect_type = params.get("effect_type")
            effect_params = params.get("params")

            if not effect_type:
                self._log("特效类型不能为空", "error")
                return

            # 根据特效名称查找对应的枚举
            effect_enum = None

            # 先在画面特效中查找
            effect_enum = self._find_enum_by_name(VideoSceneEffectType, effect_type)

            # 如果没找到，在人物特效中查找
            if effect_enum is None:
                effect_enum = self._find_enum_by_name(VideoCharacterEffectType, effect_type)

            if effect_enum:
                # 调用video_segment的add_effect方法
                if effect_params:
                    video_segment.add_effect(effect_enum, effect_params)
                else:
                    video_segment.add_effect(effect_enum)
                self._log(f"添加视频特效: {effect_type}")
            else:
                self._log(f"未找到视频特效: {effect_type}", "warning")

        except Exception as e:
            self._log(f"应用视频特效失败: {e}", "error")

    def _find_enum_by_name(self, enum_class, name: str):
        """通过名称查找枚举值"""
        if not name:
            return None

        # 对于特效类型，使用 EffectEnum 基类的 from_name 方法
        if hasattr(enum_class, 'from_name'):
            try:
                return enum_class.from_name(name)
            except ValueError:
                return None

        # 对于其他枚举类型，先尝试比较 value.name（如果存在）
        for enum_item in enum_class:
            if hasattr(enum_item.value, 'name') and enum_item.value.name == name:
                return enum_item

        # 最后尝试比较枚举项名称
        for enum_item in enum_class:
            if enum_item.name == name:
                return enum_item

        return None


