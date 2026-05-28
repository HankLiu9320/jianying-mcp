# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name:video.py
"""
import json
import os
import uuid
from typing import Optional, Dict, Any, Literal, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')
from jianyingdraft.jianying.track import Track
from jianyingdraft.validators.overlap_validator import validate_overlap
from jianyingdraft.validators.material_validator import download_and_validate_material


class VideoSegment:
    """
    视频片段管理类
    负责视频片段的创建、特效添加和数据存储
    """

    def __init__(self, draft_id: str, video_segment_id: str = None, track_name: str = None):
        """
        初始化视频片段

        Args:
            draft_id: 草稿ID
            video_segment_id: 视频片段ID，在添加动画、特效等可用，创建视频时不用
            track_name: 指定的轨道名称（可选）
        """
        self.draft_id = draft_id
        self.video_segment_id = video_segment_id
        self.track_name = track_name

    def add_video_segment(self, material: str, target_timerange: str,
                          source_timerange: Optional[str] = None, speed: Optional[float] = None,
                          volume: float = 1.0, change_pitch: bool = False,
                          clip_settings: Optional[Dict[str, Any]] = None,
                          track_name: Optional[str] = None) -> Dict[str, Any]:
        """
        创建视频片段配置

        Args:
            material: 视频文件路径，包括文本文件路径或者url
            target_timerange: 片段在轨道上的目标时间范围，格式如 "0s-4.2s",表示在轨道上从0s开始，持续4.2s
            source_timerange: 从源视频文件中截取的时间范围，格式如 "1s-4.2s",表示从源视频的1s开始截取，持续4.2s，默认从开头根据`speed`截取与`target_timerange`等长的一部分
            speed: (`float`, optional): 播放速度, 默认为1.0，此项与`source_timerange`同时指定时, 将覆盖`target_timerange`中的时长
            volume: (`float`, optional): 音量, 默认为1.0
            change_pitch: (`bool`, optional): 是否跟随变速改变音调, 默认为否，一般不修改
            clip_settings: (`Dict`, optional)图像调节设置字典（可选），哪些需要修改就填哪些字段
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
            track_name: 指定的轨道名称（可选），如果不指定则使用实例的track_name

        Returns:
            Dict[str, Any]: 构造的参数字典
        """
        # if self.video_segment_id is None:
        #     raise ValueError("video_segment_id不能为空")
        video_segment_id = str(uuid.uuid4())
        # 解析target_timerange
        if not target_timerange or "-" not in target_timerange:
            raise ValueError(f"Invalid target_timerange format: {target_timerange}")

        start_str, duration_str = target_timerange.split("-", 1)
        target_timerange_data = {
            "start": start_str.strip(),
            "duration": duration_str.strip()
        }

        # 解析source_timerange（如果提供）
        source_timerange_data = None
        if source_timerange:
            if "-" not in source_timerange:
                raise ValueError(f"Invalid source_timerange format: {source_timerange}")
            source_start_str, source_duration_str = source_timerange.split("-", 1)
            source_timerange_data = {
                "start": source_start_str.strip(),
                "duration": source_duration_str.strip()
            }

        # 确定使用的轨道名称（参数优先，然后是实例属性）
        final_track_name = track_name or self.track_name

        # 下载并验证素材，获取本地化路径
        local_material_path = download_and_validate_material(
            self.draft_id,
            material,
            "visual",
            target_timerange_data
        )

        # 构建add_video_segment参数（使用本地化后的路径）
        add_video_segment_params = {
            "material": local_material_path,  # 使用本地化后的相对路径
            "target_timerange": target_timerange_data
        }
        # 只添加用户明确传入的可选参数
        if source_timerange is not None:
            add_video_segment_params["source_timerange"] = source_timerange_data
        if speed is not None:
            add_video_segment_params["speed"] = speed
        if volume != 1.0:  # 只有非默认值才保存
            add_video_segment_params["volume"] = volume
        if change_pitch:  # 只有True才保存
            add_video_segment_params["change_pitch"] = change_pitch
        if clip_settings:  # 只有非空才保存
            add_video_segment_params["clip_settings"] = clip_settings

        # 验证轨道
        if final_track_name:
            self._validate_track_for_video(final_track_name)

        # 验证片段重叠
        if final_track_name:
            validate_overlap(self.draft_id, "video", final_track_name, target_timerange_data)

        # 构建完整的片段数据
        segment_data = {
            "video_segment_id": video_segment_id,
            "operation": "add_video_segment",
            "add_video_segment": add_video_segment_params,
        }

        # 只在指定了轨道名称时才添加track_name字段
        if final_track_name:
            segment_data["track_name"] = final_track_name
        # 保存参数
        self.add_json_to_file(segment_data)
        self.video_segment_id = video_segment_id
        return add_video_segment_params

    def add_animation(self, animation_type: str, animation_name: str, duration: Optional[str] = None,
                      video_segment_id: Optional[str] = None) -> bool:
        """
        添加动画特效

        Args:
            animation_type: 动画类型名称，只能是 "IntroType(视频/图片入场动画类型)", "OutroType(视频/图片出场动画类型,出场动画不能与转场一起用)", 或 "GroupAnimationType(组合动画，该类型不能与其他两个同时存在)"
            animation_name: 动画名称
            duration: 动画持续时间，如 "1s"

        Returns:
            bool: 添加是否成功
        """
        # 验证 animation_type 是否符合要求
        if self.video_segment_id is None and video_segment_id is None:
            print("错误: video_segment_id不能为空")
            return False
        video_segment_id = video_segment_id or self.video_segment_id
        valid_types = {"IntroType", "OutroType", "GroupAnimationType"}
        if animation_type not in valid_types:
            raise ValueError(f"animation_type 必须是以下之一: {', '.join(valid_types)}")

        segment_data = {
            "video_segment_id": video_segment_id,
            "operation": "add_animation",
            "add_animation": {
                "animation_type": animation_type,
                "animation_name": animation_name,
                "duration": duration
            }
        }
        self.add_json_to_file(segment_data)
        return True

    def add_transition(self, transition_type: str, duration: Optional[str] = None,
                       video_segment_id: Optional[str] = None) -> bool:
        """
        添加转场特效

        Args:
            transition_type: 转场类型名称，如 "信号故障", "淡入淡出" 等
            duration: 转场持续时间，如 "1s"

        Returns:
            bool: 添加是否成功
        """
        if self.video_segment_id is None and video_segment_id is None:
            print("错误: video_segment_id不能为空")
            return False
        video_segment_id = video_segment_id or self.video_segment_id
        # 构建add_transition参数（只保存用户传入的参数）
        add_transition_params = {
            "transition_type": transition_type
        }

        # 只添加用户明确传入的可选参数
        if duration is not None:
            add_transition_params["duration"] = duration

        # 构建完整的转场数据
        transition_data = {
            "video_segment_id": video_segment_id,
            "operation": "add_transition",
            "add_transition": add_transition_params
        }

        # 保存参数
        self.add_json_to_file(transition_data)
        return True

    def add_keyframe(self, property_name: str, time_offset: str, value: float,
                     video_segment_id: Optional[str] = None) -> bool:
        """
        添加关键帧

        Args:
            property_name: 属性名称，可选参数如下：
                position_x：右移为正, 此处的数值应该为`剪映中显示的值` / `草稿宽度`, 也即单位是半个画布宽
                position_y：上移为正, 此处的数值应该为`剪映中显示的值` / `草稿高度`, 也即单位是半个画布高
                rotation：顺时针旋转的**角度**
                scale_x：单独控制X轴缩放比例(1.0为不缩放), 与`uniform_scale`互斥
                scale_y：单独控制Y轴缩放比例(1.0为不缩放), 与`uniform_scale`互斥
                uniform_scale：同时控制X轴及Y轴缩放比例(1.0为不缩放), 与`scale_x`和`scale_y`互斥
                alpha：不透明度, 1.0为完全不透明, 仅对`VideoSegment`有效
                saturation：饱和度, 0.0为原始饱和度, 范围为-1.0到1.0, 仅对`VideoSegment`有效
                contrast：对比度, 0.0为原始对比度, 范围为-1.0到1.0, 仅对`VideoSegment`有效
                brightness：亮度, 0.0为原始亮度, 范围为-1.0到1.0, 仅对`VideoSegment`有效
                volume：音量, 1.0为原始音量, 仅对`AudioSegment`和`VideoSegment`有效
            time_offset: 时间偏移量，如 "0.5s", "1s" 等
            value: 属性值

        Returns:
            bool: 添加是否成功
        """
        if self.video_segment_id is None and video_segment_id is None:
            print("错误: video_segment_id不能为空")
            return False
        video_segment_id = video_segment_id or self.video_segment_id
        # 验证属性名称是否有效
        valid_properties = {
            "position_x", "position_y", "rotation",
            "scale_x", "scale_y", "uniform_scale",
            "alpha", "saturation", "contrast", "brightness", "volume"
        }
        if property_name not in valid_properties:
            print(f"错误: 无效的属性名称 '{property_name}', 支持的属性: {', '.join(valid_properties)}")
            return False

        # 构建add_keyframe参数
        add_keyframe_params = {
            "property": property_name,
            "time_offset": time_offset,
            "value": value
        }

        # 构建完整的关键帧数据
        keyframe_data = {
            "video_segment_id": video_segment_id,
            "operation": "add_keyframe",
            "add_keyframe": add_keyframe_params
        }

        # 保存参数
        self.add_json_to_file(keyframe_data)
        return True

    def add_filter(self, filter_type: str, intensity: float = 100.0, video_segment_id: Optional[str] = None) -> bool:
        """
        添加滤镜特效

        Args:
            filter_type: 滤镜类型名称，如 "亮肤", "复古", "冰雪世界" 等
            intensity: 滤镜强度 (0-100)，默认100.0

        Returns:
            bool: 添加是否成功
        """
        if self.video_segment_id is None and video_segment_id is None:
            print("错误: video_segment_id不能为空")
            return False
        video_segment_id = video_segment_id or self.video_segment_id
        # 验证强度范围
        if not (0.0 <= intensity <= 100.0):
            print(f"错误: 滤镜强度必须在0-100范围内，当前值: {intensity}")
            return False

        # 构建add_filter参数
        add_filter_params = {
            "filter_type": filter_type,
            "intensity": intensity
        }

        # 构建完整的滤镜数据
        filter_data = {
            "video_segment_id": video_segment_id,
            "operation": "add_filter",
            "add_filter": add_filter_params
        }

        # 保存参数
        self.add_json_to_file(filter_data)
        return True

    def add_background_filling(self, fill_type: Literal["blur", "color"],
                               blur: float = 0.0625, color: str = "#00000000",video_segment_id: Optional[str] = None) -> bool:
        """
        添加背景填充特效

        Args:
            fill_type (`blur` or `color`): 填充类型, `blur`表示模糊, `color`表示颜色.
            blur (`float`, optional): 模糊程度, 0.0-1.0. 仅在`fill_type`为`blur`时有效. 剪映中的四档模糊数值分别为0.0625, 0.375, 0.75和1.0, 默认为0.0625.
            color (`str`, optional): 填充颜色, 格式为'#RRGGBBAA'. 仅在`fill_type`为`color`时有效.
        Returns:
            bool: 添加是否成功
        """
        if self.video_segment_id is None and video_segment_id is None:
            print("错误: video_segment_id不能为空")
            return False
        video_segment_id = video_segment_id or self.video_segment_id
        # 验证填充类型
        if fill_type not in ["blur", "color"]:
            print(f"错误: 无效的填充类型 '{fill_type}'，支持的类型: blur, color")
            return False

        # 验证模糊程度范围
        if not (0.0 <= blur <= 1.0):
            print(f"错误: 模糊程度必须在0.0-1.0范围内，当前值: {blur}")
            return False

        # 构建add_background_filling参数
        add_background_filling_params = {
            "fill_type": fill_type,
            "blur": blur,
            "color": color
        }

        # 构建完整的背景填充数据
        background_filling_data = {
            "video_segment_id": video_segment_id,
            "operation": "add_background_filling",
            "add_background_filling": add_background_filling_params
        }

        # 保存参数
        self.add_json_to_file(background_filling_data)
        return True

    def add_mask(self, mask_type: str, center_x: float = 0.0, center_y: float = 0.0,
                 size: float = 0.5, rotation: float = 0.0, feather: float = 0.0,
                 invert: bool = False, rect_width: Optional[float] = None,
                 round_corner: Optional[float] = None, video_segment_id: Optional[str] = None) -> bool:
        """
        添加蒙版特效

        Args:
            mask_type: 蒙版类型名称，如 "圆形", "矩形", "线性" 等
            center_x (`float`, optional): 蒙版中心点X坐标(以素材的像素为单位), 默认设置在素材中心
            center_y (`float`, optional): 蒙版中心点Y坐标(以素材的像素为单位), 默认设置在素材中心
            size (`float`, optional): 蒙版的"主要尺寸"(镜面的可视部分高度/圆形直径/爱心高度等), 以占素材高度的比例表示, 默认为0.5
            rotation (`float`, optional): 蒙版顺时针旋转的**角度**, 默认不旋转
            feather (`float`, optional): 蒙版的羽化参数, 取值范围0~100, 默认无羽化
            invert (`bool`, optional): 是否反转蒙版, 默认不反转
            rect_width (`float`, optional): 矩形蒙版的宽度, 仅在蒙版类型为矩形时允许设置, 以占素材宽度的比例表示, 默认与`size`相同
            round_corner (`float`, optional): 矩形蒙版的圆角参数, 仅在蒙版类型为矩形时允许设置, 取值范围0~100, 默认为0

        Returns:
            bool: 添加是否成功
        """
        if self.video_segment_id is None and video_segment_id is None:
            print("错误: video_segment_id不能为空")
            return False
        video_segment_id = video_segment_id or self.video_segment_id
        # 验证羽化参数范围
        if not (0.0 <= feather <= 100.0):
            print(f"错误: 羽化参数必须在0-100范围内，当前值: {feather}")
            return False

        # 验证圆角参数范围（如果提供）
        if round_corner is not None and not (0.0 <= round_corner <= 100.0):
            print(f"错误: 圆角参数必须在0-100范围内，当前值: {round_corner}")
            return False

        # 构建add_mask参数（只保存用户传入的参数）
        add_mask_params = {
            "mask_type": mask_type,
            "center_x": center_x,
            "center_y": center_y,
            "size": size,
            "rotation": rotation,
            "feather": feather,
            "invert": invert
        }

        # 只添加用户明确传入的可选参数
        if rect_width is not None:
            add_mask_params["rect_width"] = rect_width
        if round_corner is not None:
            add_mask_params["round_corner"] = round_corner

        # 构建完整的蒙版数据
        mask_data = {
            "video_segment_id": video_segment_id,
            "operation": "add_mask",
            "add_mask": add_mask_params
        }

        # 保存参数
        self.add_json_to_file(mask_data)
        return True

    def add_effect(self, effect_type: str, params: Optional[List[Optional[float]]] = None,
                   video_segment_id: Optional[str] = None) -> bool:
        """
        为视频片段添加特效

        Args:
            effect_type: 特效类型名称，如 "1998", "70s", "CCD闪光" 等
            params: 特效参数列表，参数范围0-100（可选）
            video_segment_id: 视频片段ID（可选），如果不提供则使用实例的video_segment_id

        Returns:
            bool: 操作是否成功
        """
        try:
            # 确定使用的video_segment_id
            segment_id = video_segment_id or self.video_segment_id

            # 验证video_segment_id
            if segment_id is None:
                print("错误: video_segment_id不能为空")
                return False

            # 验证参数
            if params is not None:
                for i, param in enumerate(params):
                    if param is not None and not (0.0 <= param <= 100.0):
                        print(f"错误: 参数{i+1}超出范围(0-100): {param}")
                        return False

            # 构建操作数据
            operation_data = {
                "video_segment_id": segment_id,
                "operation": "add_effect",
                "add_effect": {
                    "effect_type": effect_type,
                    "params": params
                }
            }

            # 保存操作到JSON文件
            self.add_json_to_file(operation_data)

            print(f"特效添加成功: {effect_type}")
            return True

        except Exception as e:
            print(f"特效添加失败: {e}")
            return False

    def add_json_to_file(self, new_data: Dict[str, Any]) -> bool:
        """
        向现有JSON文件中添加新的JSON数据，保持文件结构规范

        Args:
            new_data: 要添加的新数据

        Returns:
            bool: 添加是否成功
        """
        try:
            file_path = f"{SAVE_PATH}/{self.draft_id}/video.json"

            # 读取现有数据
            existing_data = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        # 如果不是列表，转换为列表
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                except (json.JSONDecodeError, FileNotFoundError):
                    # 如果文件不存在或格式错误，初始化为空列表
                    existing_data = []

            # 添加新数据
            existing_data.append(new_data)

            # 保存为规范的JSON数组格式
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"添加JSON数据失败: {e}")
            return False

    def _validate_track_for_video(self, track_name: str):
        """验证轨道是否适用于视频片段"""
        track_manager = Track(self.draft_id)

        # 检查轨道是否存在
        if not track_manager.validate_track_exists(track_name):
            raise NameError(f"轨道不存在: {track_name}")

        # 检查轨道类型是否为视频类型
        track_info = track_manager.get_track_by_name(track_name)
        if track_info:
            add_track_data = track_info.get("add_track", {})
            track_type = add_track_data.get("track_type")
            if track_type != "video":
                raise TypeError(f"轨道 '{track_name}' 的类型是 '{track_type}'，不能添加视频片段")


