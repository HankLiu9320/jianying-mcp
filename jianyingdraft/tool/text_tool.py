# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: text_tool.py
"""
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from jianyingdraft.services.text_service import add_text_segment_service, add_text_animation_service
from jianyingdraft.utils.response import ToolResponse
from jianyingdraft.utils.index_manager import index_manager
from jianyingdraft.utils.time_format import parse_start_end_format


def text_tools(mcp: FastMCP):
    @mcp.tool()
    def add_text_segment(
            track_id: str,
            text: str,
            target_start_end: str,
            font: Optional[str] = None,
            style: Optional[Dict[str, Any]] = None,
            clip_settings: Optional[Dict[str, Any]] = None,
            border: Optional[Dict[str, Any]] = None,
            background: Optional[Dict[str, Any]] = None
    ) -> ToolResponse:
        """
        添加文本片段到指定轨道

        Args:
            track_id: 轨道ID，通过create_track获得
            text: 文本内容
            target_start_end: 片段在轨道上的目标时间范围，格式如 "1s-4.2s"，表示在轨道上从1s开始，到4.2s结束
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
                        "transform_y": 0.0  # 垂直位移, 单位为半个画布高. 默认为0.0.旁白字幕建议 transform_y=-0.85（底部偏下）
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
        
        Examples:
            # 基础文本
            add_text_segment("track_id", "Hello World", "0s-5s")
            
            # 带样式的文本
            add_text_segment("track_id", "标题文本", "0s-3s", 
                           style={"size": 12.0, "bold": True, "color": (1.0, 0.0, 0.0)})
            
            # 带描边的文本
            add_text_segment("track_id", "描边文本", "2s-7s",
                           border={"width": 20.0, "color": (0.0, 0.0, 0.0)})
            
            # 带背景的文本
            add_text_segment("track_id", "背景文本", "5s-10s",
                           background={"color": "#FF0000", "alpha": 0.8})
        """
        # 将新格式转换为原来的格式
        try:
            timerange = parse_start_end_format(target_start_end)
        except ValueError as e:
            return ToolResponse(
                success=False,
                message=f"target_start_end格式错误: {str(e)}"
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
        result = add_text_segment_service(
            draft_id=draft_id,
            text=text,
            timerange=timerange,
            font=font,
            style=style,
            clip_settings=clip_settings,
            border=border,
            background=background,
            track_name=track_name
        )

        # 如果文本片段添加成功，添加索引记录
        if result.success and result.data and "text_segment_id" in result.data:
            text_segment_id = result.data["text_segment_id"]
            index_manager.add_text_segment_mapping(text_segment_id, track_id)

        return result

    @mcp.tool()
    def add_text_animation(
            text_segment_id: str,
            animation_type: str,
            animation_name: str,
            duration: Optional[str] = None
    ) -> ToolResponse:
        """
        为文本片段添加动画效果

        Args:
            text_segment_id: 文本片段ID，通过add_text_segment获得
            animation_type: 动画类型，支持以下类型：
                - "TextIntro": 入场动画
                - "TextOutro": 出场动画
                - "TextLoopAnim": 循环动画
            animation_name: 动画名称，如 "复古打字机", "弹簧", "色差故障", "淡入", "淡出" 等，可以使用find_effects_by_type工具，资源类型选择TextIntro、TextOutro、TextLoopAnim，从而获取动画类型有哪些
            duration: 动画持续时间（可选），格式如 "1s", "500ms"
        """
        # 参数验证
        valid_types = ["TextIntro", "TextOutro", "TextLoopAnim"]
        if animation_type not in valid_types:
            return ToolResponse(
                success=False,
                message=f"无效的动画类型 '{animation_type}'，支持的类型: {', '.join(valid_types)}"
            )

        # 动画存在性验证（文本动画使用 title 字段）
        from jianyingdraft.utils.effect_manager import JianYingResourceManager
        manager = JianYingResourceManager()

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
                message=f"在 {animation_type} 中未找到动画 '{animation_name}'，请确认动画名称是否正确，或使用建议动画",
                data={
                    "error_type": "animation_not_found",
                    "animation_type": animation_type,
                    "animation_name": animation_name,
                    "suggestions": all_suggestions
                }
            )

        # 通过text_segment_id获取相关信息
        draft_id = index_manager.get_draft_id_by_text_segment_id(text_segment_id)
        track_info = index_manager.get_track_info_by_text_segment_id(text_segment_id)

        if not draft_id:
            return ToolResponse(
                success=False,
                message=f"未找到文本片段ID对应的草稿: {text_segment_id}"
            )

        if not track_info:
            return ToolResponse(
                success=False,
                message=f"未找到文本片段ID对应的轨道信息: {text_segment_id}"
            )

        track_name = track_info.get("track_name")

        # 调用服务层处理业务逻辑
        result = add_text_animation_service(
            draft_id=draft_id,
            text_segment_id=text_segment_id,
            animation_type=animation_type,
            animation_name=animation_name,
            duration=duration,
            track_name=track_name
        )

        return result
