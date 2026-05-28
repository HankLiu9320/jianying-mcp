# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: video_tool.py
"""
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP
from jianyingdraft.services.video_service import add_video_segment_service, add_video_animation_service, \
    add_video_transition_service, add_video_keyframe_service, add_video_filter_service, \
    add_video_background_filling_service, \
    add_video_mask_service, add_video_effect_service
from jianyingdraft.utils.response import ToolResponse
from jianyingdraft.utils.index_manager import index_manager
from jianyingdraft.utils.time_format import parse_start_end_format

from jianyingdraft.utils.effect_manager import JianYingResourceManager

manager = JianYingResourceManager()


def video_tools(mcp: FastMCP):
    @mcp.tool()
    def add_video_segment(
            track_id: str,
            material: str,
            target_start_end: str,
            source_start_end: Optional[str] = None,
            speed: Optional[float] = None,
            volume: float = 1.0,
            change_pitch: bool = False,
            clip_settings: Optional[Dict[str, Any]] = None
    ) -> ToolResponse:
        """
        添加视频片段到指定轨道，须注意target_timerange和source_timerange的使用规则

        Args:
            track_id: 轨道ID，通过create_track获得
            material: 视频或图片文件路径（含 mp4、png、jpg 等）或 url
            target_start_end: 片段在轨道上的目标时间范围，格式如 "1s-4.2s"，表示在轨道上从1s开始，到4.2s结束，target_start_end参数描述的是轨道上的时间范围，同一轨道中不可有重复时间段，即0s-4.2s和4s-5s，第一段素材最后0.2s与第二段素材重叠了，只能是0s-4.2s和4.ss-5s
            source_start_end: 从源视频文件中截取的时间范围，格式如 "1s-4.2s"，表示从源视频的1s开始截取，到4.2s结束（可选），source_start_end参数描述的是素材本身取的时长，默认取全部时长，一般情况下不设置，除非用户说明，若素材时长为5s,用户需要取其中1s-5s的内容，才配置
            speed: (`float`, optional): 播放速度, 默认为1.0，此项与`source_timerange`同时指定时, 将覆盖`target_timerange`中的时长
            volume: (`float`, optional): 音量, 默认为1.0
            change_pitch: (`bool`, optional): 是否跟随变速改变音调, 默认为否
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

        
        Returns:
            ToolResponse: 包含操作结果的响应，格式为 {"success": bool, "message": str, "data": dict, "video_segment_id": str}
        
        Examples:
            # 基本用法
            add_video_segment("track_id", "/path/to/video.mp4", "0s-5s")

            # 图片素材（png/jpg 等，无需转 mp4）
            add_video_segment("track_id", "/path/to/image.png", "0s-5s")

            # 指定源时间范围
            add_video_segment("track_id", "/path/to/video.mp4", "0s-3s", source_timerange="10s-3s")

            # 设置播放速度和音量
            add_video_segment("track_id", "/path/to/video.mp4", "0s-5s", speed=2.0, volume=0.8)

            # 设置图像调节
            add_video_segment("track_id", "/path/to/video.mp4", "0s-5s",
                            clip_settings={"alpha": 0.8, "scale_x": 1.2, "rotation": 45})
        """
        # 将新格式转换为原来的格式
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
        result = add_video_segment_service(
            draft_id=draft_id,
            material=material,
            target_timerange=target_timerange,
            source_timerange=source_timerange,
            speed=speed,
            volume=volume,
            change_pitch=change_pitch,
            clip_settings=clip_settings,
            track_name=track_name
        )

        # 如果视频片段添加成功，添加索引记录
        if result.success and result.data and "video_segment_id" in result.data:
            video_segment_id = result.data["video_segment_id"]
            index_manager.add_video_segment_mapping(video_segment_id, track_id)

        return result

    @mcp.tool()
    def add_video_animation(
            video_segment_id: str,
            animation_type: str,
            animation_name: str,
            duration: Optional[str] = ''
    ) -> ToolResponse:
        """
        为视频片段添加动画效果

        Args:
            video_segment_id: 视频片段ID，通过add_video_segment获得
            animation_type: 动画类型，支持 "IntroType", "OutroType", "GroupAnimationType"
            animation_name: 动画名称，如 "上下抖动", "向上滑动" 等，可以使用find_effects_by_type工具，资源类型选择IntroType、OutroType、GroupAnimationType，从而获取动画类型有哪些
            duration: 动画持续时间，格式如 "1s"（可选）
        """
        # 动画类型验证
        valid_animation_types = ["IntroType", "OutroType", "GroupAnimationType"]
        if animation_type not in valid_animation_types:
            return ToolResponse(
                success=False,
                message=f"无效的动画类型 '{animation_type}'，支持的类型: {', '.join(valid_animation_types)}"
            )

        # 动画存在性验证
        effects = manager.find_by_type(
            effect_type=animation_type,
            keyword=animation_name,
            limit=1
        )

        # 检查是否找到完全匹配的动画
        exact_match = False
        if effects:
            for effect in effects:
                if effect.get('title') == animation_name:
                    exact_match = True
                    break

        if not effects or not exact_match:
            # 获取建议动画
            animation_suggestions = manager.find_by_type(animation_type, keyword=animation_name)

            all_suggestions = []
            for effect in animation_suggestions:
                if effect.get('title'):
                    all_suggestions.append(effect.get('title'))

            return ToolResponse(
                success=False,
                message=f"在 {animation_type} 中未找到动画 '{animation_name}'",
                data={
                    "error_type": "animation_not_found",
                    "animation_type": animation_type,
                    "animation_name": animation_name,
                    "suggestions": all_suggestions
                }
            )

        # 通过video_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_video_segment_id(video_segment_id)
        track_info = index_manager.get_track_info_by_video_segment_id(video_segment_id)
        print(duration, type(duration))
        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的草稿: {video_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的轨道信息: {video_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_video_animation_service(
            draft_id=draft_id,
            video_segment_id=video_segment_id,
            animation_type=animation_type,
            animation_name=animation_name,
            duration=duration,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_video_transition(
            video_segment_id: str,
            transition_type: str,
            duration: Optional[str] = None
    ) -> ToolResponse:
        """
        为视频片段添加转场效果，注意两视频间添加转场应该在前一个添加转场，即video_segment_id使用前一个视频

        Args:
            video_segment_id: 视频片段ID，通过add_video_segment获得
            transition_type: 转场类型名称，可以使用find_effects_by_type工具，资源类型选择TransitionType，从而获取转场类型有哪些
            duration: 转场持续时间，格式如 "1s"（可选）
        """
        # 转场存在性验证
        effects = manager.find_by_type(
            effect_type="TransitionType",
            keyword=transition_type,
            limit=1
        )

        # 检查是否找到完全匹配的转场
        exact_match = False
        if effects:
            for effect in effects:
                if effect.get('name') == transition_type:
                    exact_match = True
                    break

        if not effects or not exact_match:
            # 获取建议转场
            transition_suggestions = manager.find_by_type("TransitionType", keyword=transition_type)

            all_suggestions = []
            for effect in transition_suggestions:
                if effect.get('name'):
                    all_suggestions.append(effect.get('name'))

            return ToolResponse(
                success=False,
                message=f"未找到转场 '{transition_type}',请确认转场名称是否正确，或尝试使用以下建议: {', '.join(all_suggestions)}",
                data={
                    "error_type": "transition_not_found",
                    "transition_name": transition_type,
                    "suggestions": all_suggestions
                }
            )

        # 通过video_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_video_segment_id(video_segment_id)
        track_info = index_manager.get_track_info_by_video_segment_id(video_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的草稿: {video_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的轨道信息: {video_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_video_transition_service(
            draft_id=draft_id,
            video_segment_id=video_segment_id,
            transition_type=transition_type,
            duration=duration,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_video_keyframe(
            video_segment_id: str,
            property_name: str,
            time_offset: str,
            value: float
    ) -> ToolResponse:
        """
        为视频片段添加关键帧

        Args:
            video_segment_id: 视频片段ID，通过add_video_segment获得
            property_name: 属性名称，可选参数如下：
                position_x：右移为正, 此处的数值应该为`剪映中显示的值` / `草稿宽度`, 也即单位是半个画布宽
                position_y：上移为正, 此处的数值应该为`剪映中显示的值` / `草稿高度`, 也即单位是半个画布高
                rotation：顺时针旋转的**角度**
                scale_x：单独控制X轴缩放比例(1.0为不缩放), 与`uniform_scale`互斥
                scale_y：单独控制Y轴缩放比例(1.0为不缩放), 与`uniform_scale`互斥
                uniform_scale：同时控制X轴及Y轴缩放比例(1.0为不缩放), 与`scale_x`和`scale_y`互斥
                alpha：不透明度, 1.0为完全不透明, 仅对`VideoSegment`有效
                saturation：饱和度, 0.0为原始饱和度, 范围为-1.0到1.0
                contrast：对比度, 0.0为原始对比度, 范围为-1.0到1.0
                brightness：亮度, 0.0为原始亮度, 范围为-1.0到1.0
                volume：音量, 1.0为原始音量
            time_offset: 时间偏移量，格式如 "0.5s", "1s" 等
            value: 属性值
        Examples:
            # 在0.5秒时设置水平位置
            add_video_keyframe("video_segment_id", "position_x", "0.5s", 0.2)

            # 在1秒时设置旋转角度
            add_video_keyframe("video_segment_id", "rotation", "1s", 45.0)

            # 在2秒时设置透明度
            add_video_keyframe("video_segment_id", "alpha", "2s", 0.5)
        """
        # 通过video_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_video_segment_id(video_segment_id)
        track_info = index_manager.get_track_info_by_video_segment_id(video_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的草稿: {video_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的轨道信息: {video_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_video_keyframe_service(
            draft_id=draft_id,
            video_segment_id=video_segment_id,
            property_name=property_name,
            time_offset=time_offset,
            value=value,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_video_filter(
            video_segment_id: str,
            filter_type: str,
            intensity: float = 100.0
    ) -> ToolResponse:
        """
        为视频片段添加滤镜效果

        Args:
            video_segment_id: 视频片段ID，通过add_video_segment获得
            filter_type: 滤镜类型名称，可以使用find_effects_by_type工具，资源类型选择filter_type，从而获取滤镜类型有哪些
            intensity: 滤镜强度，范围0-100，默认100.0
        """
        # 参数验证
        if not (0.0 <= intensity <= 100.0):
            return ToolResponse(
                success=False,
                message=f"滤镜强度必须在0-100范围内，当前值: {intensity}"
            )

        # 滤镜存在性验证
        effects = manager.find_by_type(
            effect_type="filter_type",
            keyword=filter_type,
            limit=1
        )

        # 检查是否找到完全匹配的滤镜
        exact_match = False
        if effects:
            for effect in effects:
                if effect.get('name') == filter_type:
                    exact_match = True
                    break

        if not effects or not exact_match:
            # 获取建议滤镜
            filter_suggestions = manager.find_by_type("filter_type", keyword=filter_type)

            all_suggestions = []
            for effect in filter_suggestions:
                if effect.get('name'):
                    all_suggestions.append(effect.get('name'))

            return ToolResponse(
                success=False,
                message=f"未找到滤镜 '{filter_type}'，请确认滤镜名称是否正确，或使用建议的滤镜名称。",
                data={
                    "error_type": "filter_not_found",
                    "filter_name": filter_type,
                    "suggestions": all_suggestions
                }
            )

        # 通过video_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_video_segment_id(video_segment_id)
        track_info = index_manager.get_track_info_by_video_segment_id(video_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的草稿: {video_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的轨道信息: {video_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_video_filter_service(
            draft_id=draft_id,
            video_segment_id=video_segment_id,
            filter_type=filter_type,
            intensity=intensity,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_video_background_filling(
            video_segment_id: str,
            fill_type: str,
            blur: float = 0.0625,
            color: str = "#00000000"
    ) -> ToolResponse:
        """
        为视频片段添加背景填充效果

        Args:
            video_segment_id: 视频片段ID，通过add_video_segment获得
            fill_type: 填充类型，"blur"表示模糊，"color"表示颜色
            blur: 模糊程度，范围0.0-1.0，仅在fill_type为"blur"时有效，默认0.0625
                  剪映中的四档模糊数值分别为0.0625, 0.375, 0.75和1.0
            color: 填充颜色，格式为'#RRGGBBAA'，仅在fill_type为"color"时有效，默认"#00000000"
        """
        # 参数验证
        if fill_type not in ["blur", "color"]:
            return ToolResponse(
                success=False,
                message=f"无效的填充类型 '{fill_type}'，支持的类型: blur, color"
            )

        if not (0.0 <= blur <= 1.0):
            return ToolResponse(
                success=False,
                message=f"模糊程度必须在0.0-1.0范围内，当前值: {blur}"
            )

        # 通过video_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_video_segment_id(video_segment_id)
        track_info = index_manager.get_track_info_by_video_segment_id(video_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的草稿: {video_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的轨道信息: {video_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_video_background_filling_service(
            draft_id=draft_id,
            video_segment_id=video_segment_id,
            fill_type=fill_type,
            blur=blur,
            color=color,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_video_mask(
            video_segment_id: str,
            mask_type: str,
            center_x: float = 0.0,
            center_y: float = 0.0,
            size: float = 0.5,
            rotation: float = 0.0,
            feather: float = 0.0,
            invert: bool = False,
            rect_width: Optional[float] = None,
            round_corner: Optional[float] = None
    ) -> ToolResponse:
        """
        为视频片段添加蒙版效果

        Args:
            video_segment_id: 视频片段ID，通过add_video_segment获得
            mask_type: 蒙版类型名称，可以使用find_effects_by_type工具，资源类型选择mask_type，从而获取蒙版类型有哪些
            center_x: 蒙版中心点X坐标(以素材的像素为单位)，默认0.0（素材中心）
            center_y: 蒙版中心点Y坐标(以素材的像素为单位)，默认0.0（素材中心）
            size: 蒙版的主要尺寸，以占素材高度的比例表示，默认0.5
            rotation: 蒙版顺时针旋转的角度，默认0.0
            feather: 蒙版的羽化参数，取值范围0~100，默认0.0
            invert: 是否反转蒙版，默认False
            rect_width: 矩形蒙版的宽度，仅在蒙版类型为矩形时有效，以占素材宽度的比例表示
            round_corner: 矩形蒙版的圆角参数，仅在蒙版类型为矩形时有效，取值范围0~100
        """
        # 参数验证
        if not (0.0 <= feather <= 100.0):
            return ToolResponse(
                success=False,
                message=f"羽化参数必须在0-100范围内，当前值: {feather}"
            )

        if round_corner is not None and not (0.0 <= round_corner <= 100.0):
            return ToolResponse(
                success=False,
                message=f"圆角参数必须在0-100范围内，当前值: {round_corner}"
            )

        # 蒙版存在性验证
        effects = manager.find_by_type(
            effect_type="mask_type",
            keyword=mask_type,
            limit=1
        )

        # 检查是否找到完全匹配的蒙版
        exact_match = False
        if effects:
            for effect in effects:
                if effect.get('name') == mask_type:
                    exact_match = True
                    break

        if not effects or not exact_match:
            # 获取建议蒙版
            mask_suggestions = manager.find_by_type("mask_type", keyword=mask_type)

            all_suggestions = []
            for effect in mask_suggestions:
                if effect.get('name'):
                    all_suggestions.append(effect.get('name'))

            return ToolResponse(
                success=False,
                message=f"未找到蒙版 '{mask_type}'，请确认名称是否正确，或使用建议名称",
                data={
                    "error_type": "mask_not_found",
                    "mask_name": mask_type,
                    "suggestions": all_suggestions
                }
            )

        # 通过video_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_video_segment_id(video_segment_id)
        track_info = index_manager.get_track_info_by_video_segment_id(video_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的草稿: {video_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的轨道信息: {video_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_video_mask_service(
            draft_id=draft_id,
            video_segment_id=video_segment_id,
            mask_type=mask_type,
            center_x=center_x,
            center_y=center_y,
            size=size,
            rotation=rotation,
            feather=feather,
            invert=invert,
            rect_width=rect_width,
            round_corner=round_corner,
            track_name=track_name
        )

        return result

    @mcp.tool()
    def add_video_effect(
            video_segment_id: str,
            effect_type: str,
            params: Optional[List[Optional[float]]] = None
    ) -> ToolResponse:
        """
        为视频片段添加特效

        Args:
            video_segment_id: 视频片段ID，通过add_video_segment获得
            effect_type: 特效类型名称，可以使用find_effects_by_type工具，资源类型选择VIDEO_SCENE、VIDEO_CHARACTER，从而获取特效类型有哪些
            params: 特效参数列表（可选），参数范围0-100，具体参数数量和含义取决于特效类型
        """
        # 参数验证
        if params:
            for i, param in enumerate(params):
                if param is not None and not (0.0 <= param <= 100.0):
                    return ToolResponse(
                        success=False,
                        message=f"参数{i + 1}超出范围，必须在0-100之间，当前值: {param}"
                    )

        # 特效存在性验证 - 先在 VIDEO_SCENE 中查找
        effects = manager.find_by_type(
            effect_type="VIDEO_SCENE",
            keyword=effect_type,
            limit=1
        )

        # 如果在 VIDEO_SCENE 中没找到，再在 VIDEO_CHARACTER 中查找
        if not effects:
            effects = manager.find_by_type(
                effect_type="VIDEO_CHARACTER",
                keyword=effect_type,
                limit=1
            )

        # 检查是否找到完全匹配的特效
        exact_match = False
        if effects:
            for effect in effects:
                if effect.get('name') == effect_type:
                    exact_match = True
                    break

        if not effects or not exact_match:
            # 获取建议特效
            scene_suggestions = manager.find_by_type("VIDEO_SCENE", keyword=effect_type)
            char_suggestions = manager.find_by_type("VIDEO_CHARACTER", keyword=effect_type)

            all_suggestions = []
            for effect in scene_suggestions + char_suggestions:
                if effect.get('name'):
                    all_suggestions.append(effect.get('name'))

            return ToolResponse(
                success=False,
                message=f"未找到特效 '{effect_type}'，请确认名称是否正确，或使用建议名称",
                data={
                    "error_type": "effect_not_found",
                    "effect_name": effect_type,
                    "suggestions": all_suggestions
                }
            )

        # 通过video_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_video_segment_id(video_segment_id)
        track_info = index_manager.get_track_info_by_video_segment_id(video_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的草稿: {video_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到视频片段ID对应的轨道信息: {video_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_video_effect_service(
            draft_id=draft_id,
            video_segment_id=video_segment_id,
            effect_type=effect_type,
            params=params,
            track_name=track_name
        )

        return result
