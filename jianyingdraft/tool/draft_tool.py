# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name:draft_tool.py
"""
from mcp.server.fastmcp import FastMCP
from jianyingdraft.jianying.export import ExportDraft
from jianyingdraft.utils.response import ToolResponse
from jianyingdraft.utils.index_manager import index_manager
import uuid
import json
import os
from dotenv import load_dotenv
import datetime

load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')
OUTPUT_PATH = os.getenv('OUTPUT_PATH')


def draft_tools(mcp: FastMCP):
    @mcp.tool()
    def rules():
        """制作视频的规范，这一步必须执行，方便了解如何规范的使用工具制作视频"""
        prompt = """
核心工作原则
1.询问用户应当怎么制作视频，有什么建议，你可以使用parse_media_info（了解素材信息），然后不断地向用户询问制作视频的细节，在制作前，你应该向用户说明你准备怎么制作视频，用户没有意见后才开始制作视频

2. 严格遵循操作流程
必须按照以下顺序执行，不可跳步骤：
创建草稿 → create_draft
创建轨道 → create_track（根据需要创建video、audio、text轨道）
添加素材 → add_*_segment（添加视频、音频、文本片段）
查询特效 → find_effects_by_type（查找可用特效）
应用特效 → add_*_effect/animation（添加各种特效和动画）
导出草稿 → export_draft

3. ID管理规则
draft_id：创建草稿后获得，用于所有后续操作
track_id：创建轨道后获得，用于添加对应类型的素材
segment_id：添加素材后获得，用于添加特效和动画
严格保存和传递这些ID，它们是工具链的关键纽带

4.轨道规则
一般情况下同类型的轨道只需要一个就可以，除非需要画中画等复杂情况才会创建多个同类型的轨道

4.1 图片素材（png/jpg/webp 等）
add_video_segment 已支持直接导入图片，无需将 png 转成 mp4。
在 video 轨道上调用 add_video_segment，material 传入图片本地绝对路径或 url，target_start_end 指定轨道上展示时长（如 "0s-5s" 表示展示 5 秒）。
禁止仅因格式为 png 而自行 ffmpeg 转码；仅当 add_video_segment 明确报错时才考虑其他方案。

5.时长规则
在规划视频、音频时长时，必须从素材本身时长出发，使用本身的时长，切记不能超出素材本身时长（图片素材无固定时长，由 target_start_end 决定展示多久，不受此条「素材本身时长」限制）
注意素材的总时长，在传入target_timerange参数时，所占的轨道时长不能超过素材总时长，不能因为其他原因使得轨道时长超过素材时长，例如当视频总时长5s，音频时长为4.2s，不能因为视频比音频时间长，就改变音频轨道时长，即音频可传入的最大时长为4.2s
添加素材的add_audio_segment和add_video_segment工具中，target_timerange参数描述的是轨道上的时间范围，同一轨道中不可有重复时间段，即0s-4.2s和4s-5s，第一段素材最后0.2s与第二段素材重叠了，只能是0s-4.2s和4.ss-5s
添加素材的add_audio_segment和add_video_segment工具中，source_timerange参数描述的是素材本身取的时长，默认取全部时长，一般情况下不设置，除非用户说明，若素材时长为5s,用户需要取其中1s-5s的内容，才配置

6.其他
add_text_segment工具其中的参数clip_settings的transform_y，强烈建议修改为-0.7(这样字幕是在正下方，不影响视频观感)
特效不存在：查看建议列表，选择相似特效
时间冲突：调整时间范围，查看素材时间以及工具参数
添加转场：若三个视频间需要添加转场，那转场应该添加在第一个和第二个视频后添加转场，而非第二个和第三个视频里


     """
        return ToolResponse(
            success=True,
            message="获取成功",
            data={"rules": prompt}
        )

    @mcp.tool()
    def create_draft(draft_name: str, width: int = 1920, height: int = 1080, fps: int = 30):
        """
        创建草稿

        Args:
            draft_name:  str 草稿名称
            width: int,视频宽度,默认1920
            height: int，视频高度，默认1080
            fps: int，帧率，默认30
        """
        # 验证SAVE_PATH是否存在
        if not os.path.exists(SAVE_PATH):
            raise FileNotFoundError(f"草稿存储路径不存在: {SAVE_PATH}")
        # 生成草稿ID
        draft_id = str(uuid.uuid4())
        # 构建完整的草稿路径
        draft_path = os.path.join(SAVE_PATH, draft_id)
        # 创建草稿数据
        draft_data = {
            "draft_id": draft_id,
            "draft_name": draft_name,
            "width": width,
            "height": height,
            "fps": fps
        }
        # 在SAVE_PATH下创建以草稿ID命名的文件夹
        os.makedirs(draft_path, exist_ok=True)

        # 保存draft.json文件
        draft_json_path = os.path.join(draft_path, "draft.json")
        with open(draft_json_path, "w", encoding="utf-8") as f:
            json.dump(draft_data, f, ensure_ascii=False, indent=4)

        # 添加草稿索引记录

        draft_info = {
            "draft_name": draft_name,
            "created_time": datetime.datetime.now().isoformat(),
            "width": width,
            "height": height,
            "fps": fps
        }
        index_manager.add_draft_mapping(draft_id, draft_info)

        return draft_data

    @mcp.tool()
    def export_draft(draft_id: str, jianying_draft_path: str = OUTPUT_PATH) -> ToolResponse:
        """
        导出草稿为剪映项目，导出到本地剪映的草稿路径下

        Args:
            draft_id: 草稿ID，必须是已存在的草稿
            jianying_draft_path: 导出路径
        """
        try:
            # 验证草稿是否存在
            draft_data_path = os.path.join(SAVE_PATH, draft_id)
            if not os.path.exists(draft_data_path):
                return ToolResponse(
                    success=False,
                    message=f"草稿不存在: {draft_id}"
                )

            # 验证草稿数据文件是否存在
            draft_json_path = os.path.join(draft_data_path, "draft.json")
            if not os.path.exists(draft_json_path):
                return ToolResponse(
                    success=False,
                    message=f"草稿数据文件不存在: {draft_id}/draft.json"
                )

            # 创建导出器
            exporter = ExportDraft(jianying_draft_path)

            # 执行导出
            export_result = exporter.export(draft_id)

            if export_result and isinstance(export_result, dict):
                return ToolResponse(
                    success=True,
                    message="草稿导出成功",
                    data={
                        "draft_id": draft_id,
                        "output_path": export_result.get("output") + f"/{export_result.get("draft_name")}",
                        "draft_name": export_result.get("draft_name"),
                        "export_logs": export_result.get("export_logs", []),
                        "summary": export_result.get("summary", {}),
                        "processing_details": {
                            "total_operations": len(export_result.get("export_logs", [])),
                            "successful_operations": len(
                                [log for log in export_result.get("export_logs", []) if log.get("level") == "info"]),
                            "warnings": len(
                                [log for log in export_result.get("export_logs", []) if log.get("level") == "warning"]),
                            "errors": len(
                                [log for log in export_result.get("export_logs", []) if log.get("level") == "error"])
                        }
                    }
                )
            else:
                return ToolResponse(
                    success=False,
                    message="草稿导出失败，请检查草稿数据完整性"
                )

        except FileNotFoundError as e:
            return ToolResponse(
                success=False,
                message=f"文件不存在: {str(e)}"
            )
        except Exception as e:
            return ToolResponse(
                success=False,
                message=f"导出失败: {str(e)}"
            )
