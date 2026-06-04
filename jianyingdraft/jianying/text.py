# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name:text.py
"""
import json
import os
import uuid
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')
from jianyingdraft.jianying.track import Track
from jianyingdraft.validators.overlap_validator import validate_overlap


class TextSegment:
    """
    文本片段管理类
    负责文本片段的创建和数据存储
    """

    def __init__(self, draft_id: str, track_name: str = None,text_segment_id= None):
        """
        初始化文本片段

        Args:
            draft_id: 草稿ID
            track_name: 指定的轨道名称（可选）
            text_segment_id:文本id，在添加动画、特效等可用，创建文本时不用
        """
        self.draft_id = draft_id
        self.track_name = track_name
        self.text_segment_id = text_segment_id

    def add_text_segment(self, text: str, timerange: str,
                         font: Optional[str] = None,
                         style: Optional[Dict[str, Any]] = None,
                         clip_settings: Optional[Dict[str, Any]] = None,
                         border: Optional[Dict[str, Any]] = None,
                         background: Optional[Dict[str, Any]] = None,
                         track_name: Optional[str] = None) -> Dict[str, Any]:
        """
        创建文本片段配置，可选的参数用户没要求可不填

        Args:
            text: 文本内容
            timerange: 时间范围，格式如 "0s-4.2s",表示在轨道上从0s开始，持续4.2s
            font: 字体类型名称（可选）
            style: 字体样式字典（可选），哪些需要修改就填哪些字段
                默认style = {
                        "size": 6.0,# 字体大小, 默认为6.0
                        "bold": False,# 是否加粗, 默认为否
                        "italic": False,# 是否斜体, 默认为否
                        "underline": False,#  是否加下划线, 默认为否
                        "color": (1.0, 1.0, 1.0),  # 字体颜色, RGB三元组, 取值范围为[0, 1], 默认为白色
                        "alpha": 1.0,# 字体不透明度, 取值范围[0, 1], 默认不透明
                        "align": 0,  # 对齐方式, 0: 左对齐, 1: 居中, 2: 右对齐, 默 认为左对齐
                        "vertical": False,#是否为竖排文本, 默认为否
                        "letter_spacing": 0,# 字符间距, 定义与剪映中一致, 默认为0
                        "line_spacing": 0,# 行间距, 定义与剪映中一致, 默认为0
                        "auto_wrapping": False,# 是否自动换行, 默认关闭
                        "max_line_width": 0.82 # 每行最大行宽占屏幕宽度比例, 取值范围为[0, 1], 默认为0.82
                        }
            clip_settings: 图像调节设置字典（可选），哪些需要修改就填哪些字段
                默认 clip_settings = {
                        "alpha": 1.0,  # 图像不透明度, 0-1. 默认为1.0.
                        "flip_horizontal": False,  # 是否水平翻转. 默认为False.
                        "flip_vertical": False,  # 是否垂直翻转. 默认为False.
                        "rotation": 0.0,  # 顺时针旋转的**角度**, 可正可负. 默认为0.0.
                        "scale_x": 1.0,  # 水平缩放比例. 默认为1.0.
                        "scale_y": 1.0,  # 垂直缩放比例. 默认为1.0.
                        "transform_x": 0.0,  # 水平位移, 单位为半个画布宽. 默认为0.0.
                        "transform_y": 0.0  # 垂直位移, 单位为半个画布高. 默认为0.0.
                        }
            border: 文本描边参数字典（可选），哪些需要修改就填哪些字段
                stroke_style = {
                        "alpha": 1.0,  # 描边不透明度, 取值范围[0, 1], 默认为1.0
                        "color": (0.0, 0.0, 0.0),  # 描边颜色, RGB三元组, 取值范围为[0, 1], 默认为黑色
                        "width": 40.0  # 描边宽度, 与剪映中一致, 取值范围为[0, 100], 默认为40.0
                        }
            background: 文本背景参数字典（可选），哪些需要修改就填哪些字段
            默认 background = {
                        "color": "#000000",  # 背景颜色, 格式为'#RRGGBB' (默认为黑色)
                        "style": 1,          # 背景样式, 1和2分别对应剪映中的两种样式, 默认为1
                        "alpha": 1.0,        # 背景不透明度, 与剪映中一致, 取值范围[0, 1], 默认为1.0
                        "round_radius": 0.0, # 背景圆角半径, 与剪映中一致, 取值范围[0, 1], 默认为0.0
                        "height": 0.                    14,      # 背景高度, 与剪映中一致, 取值范围为[0, 1], 默认为0.14
                        "width": 0.14,       # 背景宽度, 与剪映中一致, 取值范围为[0, 1], 默认为0.14
                        "horizontal_offset": 0.5,  # 背景水平偏移, 与剪映中一致, 取值范围为[0, 1], 默认为0.5
                        "vertical_offset": 0.5     # 背景竖直偏移, 与剪映中一致, 取值范围为[0, 1], 默认为0.5
                    }
            track_name: 指定的轨道名称（可选），如果不指定则使用实例的track_name

        Returns:
            Dict[str, Any]: 构造的参数字典
        """
        self.text_segment_id = str(uuid.uuid4())

        # 解析timerange
        if not timerange or "-" not in timerange:
            raise ValueError(f"Invalid timerange format: {timerange}")

        start_str, duration_str = timerange.split("-", 1)
        timerange_data = {
            "start": start_str.strip(),
            "duration": duration_str.strip()
        }

        # 构建add_text_segment参数（只保存用户传入的参数）
        add_text_segment_params = {
            "text": text,
            "timerange": timerange_data
        }

        # 只添加用户明确传入的可选参数
        if font is not None:
            add_text_segment_params["font"] = font
        if style is not None:
            add_text_segment_params["style"] = style
        if clip_settings is not None:
            add_text_segment_params["clip_settings"] = clip_settings
        if border is not None:
            add_text_segment_params["border"] = border
        if background is not None:
            add_text_segment_params["background"] = background

        # 确定使用的轨道名称（参数优先，然后是实例属性）
        final_track_name = track_name or self.track_name

        # 验证轨道
        if final_track_name:
            self._validate_track_for_text(final_track_name)

        # 验证片段重叠
        if final_track_name:
            validate_overlap(self.draft_id, "text", final_track_name, timerange_data)

        # 构建完整的文本片段数据
        text_segment_data = {
            "text_segment_id": self.text_segment_id,
            "operation": "add_text_segment",
            "add_text_segment": add_text_segment_params
        }

        # 只在指定了轨道名称时才添加track_name字段
        if final_track_name:
            text_segment_data["track_name"] = final_track_name

        # 保存到文件
        self.add_json_to_file(text_segment_data)

        return add_text_segment_params

    def add_animation(self, animation_type: str, animation_name: str,
                      duration: Optional[str] = None,text_segment_id:Optional[str]=None) -> bool:
        """
        添加文本动画

        Args:
            animation_type: 动画类型，"TextIntro"、"TextOutro"、"TextLoopAnim"
            animation_name: 动画名称，如 "复古打字机"、"弹簧"、"色差故障" 等
            duration: 动画持续时间（可选），格式如 "1s"、"500ms"

        Returns:
            bool: 添加是否成功
        """
        if self.text_segment_id is None and text_segment_id is None:
            print("错误: text_segment_id不能为空")
            return False
        text_segment_id = text_segment_id or self.text_segment_id
        # 验证动画类型
        valid_types = ["TextIntro", "TextOutro", "TextLoopAnim"]
        if animation_type not in valid_types:
            print(f"错误: 无效的动画类型 '{animation_type}'，支持的类型: {valid_types}")
            return False

        # 构建add_animation参数
        add_animation_params = {
            "animation_type": animation_type,
            "animation_name": animation_name
        }

        # 只添加用户明确传入的可选参数
        if duration is not None:
            add_animation_params["duration"] = duration

        # 构建完整的动画数据
        animation_data = {
            "text_segment_id": text_segment_id,
            "operation": "add_animation",
            "add_animation": add_animation_params
        }

        # 保存参数
        self.add_json_to_file(animation_data)
        return True

    def add_bubble(self, effect_id: str, resource_id: str) -> bool:
        # 没有该效果，可不加这个方法
        """
        添加文本气泡效果

        Args:
            effect_id: 气泡效果的effect_id
            resource_id: 气泡效果的resource_id

        Returns:
            bool: 添加是否成功
        """
        if self.text_segment_id is None:
            print("错误: text_segment_id不能为空")
            return False

        # 验证参数
        if not effect_id or not resource_id:
            print("错误: effect_id和resource_id不能为空")
            return False

        # 构建add_bubble参数
        add_bubble_params = {
            "effect_id": effect_id,
            "resource_id": resource_id
        }

        # 构建完整的气泡数据
        bubble_data = {
            "text_segment_id": self.text_segment_id,
            "operation": "add_bubble",
            "add_bubble": add_bubble_params
        }

        # 保存参数
        self.add_json_to_file(bubble_data)
        return True

    def add_effect(self, effect_id: str) -> bool:
        # 没有该效果，可不加这个方法
        """
        添加文本花字效果

        Args:
            effect_id: 花字效果的effect_id，也同时是其resource_id

        Returns:
            bool: 添加是否成功
        """
        if self.text_segment_id is None:
            print("错误: text_segment_id不能为空")
            return False

        # 验证参数
        if not effect_id:
            print("错误: effect_id不能为空")
            return False

        # 构建add_effect参数
        add_effect_params = {
            "effect_id": effect_id
        }

        # 构建完整的花字效果数据
        effect_data = {
            "text_segment_id": self.text_segment_id,
            "operation": "add_effect",
            "add_effect": add_effect_params
        }

        # 保存参数
        self.add_json_to_file(effect_data)
        return True

    def add_json_to_file(self, new_data: Dict[str, Any]) -> bool:
        """
        向现有JSON文件中添加新的JSON数据，保持文件结构规范

        Args:
            new_data: 要添加的新数据

        Returns:
            bool: 添加是否成功
        """
        try:
            from jianyingdraft.utils.global_cache import GlobalBatchCache
            file_path = f"{SAVE_PATH}/{self.draft_id}/text.json"
            return GlobalBatchCache.append_json(file_path, new_data)
        except Exception as e:
            print(f"添加JSON数据失败: {e}")
            return False

    def get_text_segments(self) -> list:
        """
        获取所有文本片段记录

        Returns:
            List: 文本片段记录列表
        """
        try:
            from jianyingdraft.utils.global_cache import GlobalBatchCache
            file_path = f"{SAVE_PATH}/{self.draft_id}/text.json"
            return GlobalBatchCache.get_json(file_path)
        except Exception as e:
            print(f"读取文本片段数据失败: {e}")
            return []

    def get_text_segment_by_id(self, text_segment_id: str) -> Optional[Dict[str, Any]]:
        """
        根据文本片段ID获取文本片段信息

        Args:
            text_segment_id: 文本片段ID

        Returns:
            Dict: 文本片段信息，如果不存在返回None
        """
        text_segments = self.get_text_segments()
        for segment in text_segments:
            if segment.get("text_segment_id") == text_segment_id:
                return segment
        return None

    def _validate_track_for_text(self, track_name: str):
        """验证轨道是否适用于文本片段"""
        from jianyingdraft.utils.global_cache import GlobalBatchCache

        if GlobalBatchCache.is_track_validated(self.draft_id, track_name, "text"):
            return

        track_info = GlobalBatchCache.get_track_by_name(self.draft_id, track_name)
        if not track_info:
            track_manager = Track(self.draft_id)
            if not track_manager.validate_track_exists(track_name):
                raise NameError(f"轨道不存在: {track_name}")
            track_info = track_manager.get_track_by_name(track_name)

        if track_info:
            add_track_data = track_info.get("add_track", {})
            track_type = add_track_data.get("track_type")
            if track_type != "text":
                raise TypeError(f"轨道 '{track_name}' 的类型是 '{track_type}'，不能添加文本片段")

        GlobalBatchCache.mark_track_validated(self.draft_id, track_name, "text")



