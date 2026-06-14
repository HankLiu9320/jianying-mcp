# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: utility_tool.py
"""
from typing import Optional, List, Dict, Any
from mcp.server.fastmcp import FastMCP
from jianyingdraft.utils.response import ToolResponse


def utility_tools(mcp: FastMCP):
    @mcp.tool()
    def find_effects_by_type(
            effect_type: str,
            is_vip: Optional[bool] = None,
            limit: Optional[int] = None,
            keyword: Optional[str] = None
    ) -> ToolResponse:
        """
        根据类型查找剪映特效资源
        
        Args:
            effect_type: 特效类型，支持以下类型：
                - "VIDEO_SCENE": 视频画面特效
                - "ToneEffectType": 音频音色特效
                - "AudioSceneEffectType": 音频场景特效
                - "filter_type": 滤镜特效
                - "SpeechToSongType": 语音转歌曲特效
                - "mask_type": 蒙版特效
                - "TransitionType": 转场特效
                - "Font": 字体
                - "TextIntro": 文字入场动画
                - "TextOutro": 文字出场动画
                - "TextLoopAnim": 文字循环动画
                - "GroupAnimationType": 组合动画
                - "VIDEO_CHARACTER": 视频人物特效
                - "IntroType": 视频/图片入场动画
                - "OutroType": 视频/图片出场动画
            is_vip: 是否只获取VIP资源，None表示获取所有
            limit: 返回数量限制，None表示返回全部
            keyword: 模糊匹配关键词，用于搜索特效名称
        """
        try:
            from jianyingdraft.utils.effect_manager import JianYingResourceManager
            
            # 创建资源管理器实例
            manager = JianYingResourceManager()
            
            # 调用查找方法
            effects = manager.find_by_type(
                effect_type=effect_type,
                is_vip=is_vip,
                limit=limit,
                keyword=keyword
            )
            
            # 构建返回数据
            response_data = {
                "effect_type": effect_type,
                "total_count": len(effects),
                "effects": effects
            }
            
            # 添加过滤条件到返回数据
            if is_vip is not None:
                response_data["is_vip_filter"] = is_vip
            if limit is not None:
                response_data["limit"] = limit
            if keyword:
                response_data["keyword"] = keyword
            
            return ToolResponse(
                success=True,
                message=f"找到 {len(effects)} 个 {effect_type} 特效",
                data=response_data
            )
            
        except ValueError as e:
            return ToolResponse(
                success=False,
                message=f"参数错误: {str(e)}"
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                message=f"查找特效失败: {str(e)}"
            )

    @mcp.tool()
    def parse_media_info(media_path: str) -> ToolResponse:
        """
        解析媒体文件信息
        
        Args:
            media_path: 媒体文件路径或URL，支持本地文件和网络URL,不论任何类型的文件都可以，视频可返回时长、分辨率，图片可返回尺寸
        """
        try:
            from jianyingdraft.utils.media_parser import parse_media_info as parse_func
            
            # 调用解析函数
            media_info = parse_func(media_path)
            
            if media_info is None:
                return ToolResponse(
                    success=False,
                    message=f"无法解析媒体文件: {media_path}"
                )
            
            # 构建返回数据
            response_data = {
                "media_path": media_path,
                "media_info": media_info
            }
            
            # 提取关键信息用于消息
            media_type = media_info.get("type", "未知")
            duration = media_info.get("duration")
            resolution = media_info.get("resolution")
            
            message_parts = [f"成功解析 {media_type} 文件"]
            if duration:
                message_parts.append(f"时长: {duration}")
            if resolution:
                message_parts.append(f"分辨率: {resolution}")
            
            return ToolResponse(
                success=True,
                message=", ".join(message_parts),
                data=response_data
            )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                message=f"解析媒体文件失败: {str(e)}"
            )

    @mcp.tool()
    def trim_png_alpha(
            input_path: str,
            output_path: Optional[str] = None,
            target_width: Optional[int] = None,
            target_height: Optional[int] = None,
            alpha_threshold: int = 128,
            max_margin_ratio: float = 0.02,
            validate_only: bool = False,
    ) -> ToolResponse:
        """
        PNG alpha 满画幅紧裁切：裁至内容包围盒，**保持原有宽高比**等比缩放（禁止拉伸），输出紧贴内容尺寸。

        Args:
            input_path: 输入 PNG 绝对路径（须 RGBA 或可调为 RGBA）
            output_path: 输出路径；省略则覆盖 input_path
            target_width: 目标宽度上限/固定宽（与 target_height 组合时为 contain 框宽）；省略且 target_height 也省略则仅裁切
            target_height: 目标高度上限/固定高；省略且 target_width 也省略则仅裁切
            alpha_threshold: alpha 判定阈值（0-255），默认 128
            max_margin_ratio: 边距上限（相对画布比例），默认 0.02（2%）
            validate_only: True 时仅分析边距，不写文件

        Returns:
            aspect_ratio_preserved、output_size（可能为 512×384 等非方形）、margins_after、margin_ok 等
        """
        try:
            from jianyingdraft.utils.png_alpha import trim_png_alpha as trim_func

            result = trim_func(
                input_path=input_path,
                output_path=output_path,
                target_width=target_width,
                target_height=target_height,
                alpha_threshold=alpha_threshold,
                max_margin_ratio=max_margin_ratio,
                validate_only=validate_only,
            )
            data = result.to_dict()

            if validate_only:
                msg = (
                    f"校验完成：max_margin={result.margins_after['max_margin']:.4f}，"
                    f"margin_ok={result.margin_ok}，alpha_corners_ok={result.alpha_corners_ok}"
                )
            elif result.margin_ok and result.alpha_corners_ok:
                msg = f"紧裁切完成并已保存: {result.output_path}"
            else:
                parts = [f"已保存: {result.output_path}"]
                if not result.margin_ok:
                    parts.append(
                        f"边距未达标(max={result.margins_after['max_margin']:.4f} > {max_margin_ratio})"
                    )
                if not result.alpha_corners_ok:
                    parts.append("四角 alpha 校验未通过")
                msg = "；".join(parts)

            return ToolResponse(
                success=result.margin_ok and result.alpha_corners_ok and result.aspect_ratio_preserved,
                message=msg,
                data=data,
            )
        except Exception as e:
            return ToolResponse(
                success=False,
                message=f"trim_png_alpha 失败: {str(e)}",
            )
