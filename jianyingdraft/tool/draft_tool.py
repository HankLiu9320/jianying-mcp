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
创建轨道 → create_track 或 batch_create_tracks（分镜等多轨道场景优先用批量）
添加素材 → add_*_segment 或 batch_add_segments（多片段场景优先用批量；video/text 可在 segments 内联 animation_type/animation_name 自动挂动效）
查询特效 → find_effects_by_type（动效名称不确定时查找；batch_add_segments 已内联动效时可跳过单独 add_*_animation）
应用特效 → add_*_effect/animation（未使用 batch 内联动效时，或需补加特效/转场/滤镜时）
导出草稿 → export_draft

2.1 批量工具（分镜/多镜头必用，避免逐条 MCP 调用过慢）
- batch_create_tracks: 一次创建多条轨道，返回 track_map（track_name → track_id）
- batch_add_segments: 一次添加多条 video/audio/text 片段；video/text 可选 animation_type + animation_name 内联入场动效（对应分镜脚本动效列）
- batch_parse_media_durations: 一次解析多个音频/视频时长，规划时间轴前优先调用
- 典型分镜流程: create_draft → batch_create_tracks → batch_parse_media_durations → batch_add_segments（含 clip_settings 与 animation） → export_draft
- 禁止为批量添加素材而编写本地 Python 脚本绕过 MCP；应使用 batch_* 工具

3. ID管理规则
draft_id：创建草稿后获得，用于所有后续操作
track_id：创建轨道后获得，用于添加对应类型的素材
segment_id：添加素材后获得，用于添加特效和动画
严格保存和传递这些ID，它们是工具链的关键纽带

4.轨道规则
一般情况下同类型的轨道只需要一个就可以，除非需要画中画等复杂情况才会创建多个同类型的轨道

4.1 视频/图片素材（video_bg 背景与画面层通用）
add_video_segment / batch_add_segments 的 material 支持：本地绝对路径或 http(s) URL；图片（png/jpg/webp）与视频（mp4/mov 等）均可，无需将 png 转成 mp4。
video_bg 全屏背景：按分镜传入用户自定义背景路径或 URL；未指定时可使用 aidata/cankao/background.png。target_start_end 指定该段展示时长（图片由时长决定，视频可按 source_timerange 截取）。
画面层 PNG（img_prop_* / img_* 道具符号）：必须为 RGBA 真实透明背景（alpha 有效），禁止白底/灰底/场景底伪透明；上屏前若见底色块须先抠图或重生成。
PNG 须满画幅紧裁切：成图后调用 trim_png_alpha（保持原图宽高比、禁止拉伸）；可传 target_width/target_height 作 contain 上限，输出尺寸随比例（如 512×384）；margin_ok 为 true 后再上屏。
禁止仅因格式为 png 而自行 ffmpeg 转码；仅当 add_video_segment 明确报错时才考虑其他方案。

4.2 图片布局 clip_settings（分镜必用；数值以 aidata 分镜 02 或 知识点分镜.md 为准）
- 每张 PNG（除全屏背景外）必须传入 clip_settings（scale_x/y + transform_x/y）。
- 坐标：transform 单位为半个画布宽/高；负 x 左、正 x 右；正 y 上、负 y 下。
- 全片默认不上讲解角色；画面以素材为主视觉，旁白靠 TTS+字幕。
- 尺寸阶梯：L1 主视觉 scale 0.62–0.72；L2 复合辅视觉 0.42–0.55；单一符号 0.24–0.32（主辅比 2.5–3.0）；L3 标签 0.26–0.34；同镜 L1 scale 必须 > L2。
- 16:9 垂直锚点：L1 默认 transform_y=+0.12（画面垂直居中偏上）；禁止 L1 transform_y<+0.06 导致整体偏下；辅图 y=L1.y+Δy，整组平移时相对位置不变。
- 默认模板 A（单主视觉居中，约70%镜头）：L1 主视觉 layer1 {"scale_x":0.68,"scale_y":0.68,"transform_x":0.0,"transform_y":0.12}；标签 overlay {"scale_x":0.30,"scale_y":0.30,"transform_x":0.36,"transform_y":0.36}（贴主视觉右上外侧，禁止压顶）。
- 模板 B 主+辅：L1 {"scale_x":0.65,"transform_x":-0.08,"transform_y":0.12} + L2 {"scale_x":0.46,"transform_x":0.32,"transform_y":0.20}；模板 C 双物对比左右各 {"scale_x":0.55,"transform_x":±0.24,"transform_y":0.12}；模板 E 左主右辅：L1 {"transform_x":-0.22,"transform_y":0.12}，上符号 {"transform_x":0.24,"transform_y":0.40,"scale_x":0.26}，下符号 {"transform_x":0.24,"transform_y":-0.16,"scale_x":0.26}。
- 一镜一重点：每镜 PNG≤4（1主+0~2辅+0~1标签）；禁止把前后句无关道具堆同屏；禁止 L1 scale < 0.58。
- 主体与字幕分离：PNG 主体最下缘 transform_y ≥ -0.40；字幕 transform_y=-0.85。
- 分镜表 clip_settings 须原样写入 batch_add_segments，禁止制作阶段擅自改坐标；无分镜时可参考模板 A/B/C/D/E（见知识点分镜.md「通用布局方案」）。
- batch_add_segments 示例：{"type":"video","track_name":"video_layer1","material":"/path/prop.png","target_start_end":"0s-5s","clip_settings":{"scale_x":0.68,"scale_y":0.68,"transform_x":0.0,"transform_y":0.12},"animation_type":"IntroType","animation_name":"放大"}
- 分镜动效列须映射为 animation_type、animation_name；全屏背景及标注「—」的元素不加动效

5.时长规则
在规划视频、音频时长时，必须从素材本身时长出发，使用本身的时长，切记不能超出素材本身时长（图片素材无固定时长，由 target_start_end 决定展示多久，不受此条「素材本身时长」限制）
注意素材的总时长，在传入target_timerange参数时，所占的轨道时长不能超过素材总时长，不能因为其他原因使得轨道时长超过素材时长，例如当视频总时长5s，音频时长为4.2s，不能因为视频比音频时间长，就改变音频轨道时长，即音频可传入的最大时长为4.2s
添加素材的add_audio_segment和add_video_segment工具中，target_timerange参数描述的是轨道上的时间范围，同一轨道中不可有重复时间段，即0s-4.2s和4s-5s，第一段素材最后0.2s与第二段素材重叠了，只能是0s-4.2s和4.ss-5s
添加素材的add_audio_segment和add_video_segment工具中，source_timerange参数描述的是素材本身取的时长，默认取全部时长，一般情况下不设置，除非用户说明，若素材时长为5s,用户需要取其中1s-5s的内容，才配置

6.字幕与旁白规则
旁白字幕（text_subtitle）须全片统一：style={"size":8.0,"align":1}，clip_settings={"transform_y":-0.85}（字号8、底部偏下，不遮挡画面主体）
add_text_segment / batch_add_segments 添加字幕时必须传入上述 style 与 clip_settings，勿用默认字号6或 transform_y=0
旁白制作须通过 MCP build_narration_segments 完成（禁止直接运行仓库 scripts/*.py 或 aidata 工程内 _build_*.py）:
  - 输入: output_dir（aidata 工程目录）、subtitle_items（02 分镜字幕规划）、bg_material、video_items（可选）
  - 句号级 TTS: 按 tts_text 的句号/问号/感叹号/分号合并合成（逗号不切，保证语音连贯）
  - ASR 对齐: 每句 mp3 调用 recognize_subtitles 获取句内时间轴，再写入 text 轨道
  - 输出: data.segments 直接传给 batch_add_segments
也可分步: text_to_speech（句号级）→ recognize_subtitles → 手动 batch_add_segments

7.其他
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
                export_logs = export_result.get("export_logs", [])
                summary = export_result.get("summary", {})
                issues = [
                    log["message"]
                    for log in export_logs
                    if log.get("level") in ("warning", "error")
                ][-10:]
                return ToolResponse(
                    success=True,
                    message="草稿导出成功",
                    data={
                        "draft_id": draft_id,
                        "output_path": export_result.get("output") + f"/{export_result.get('draft_name')}",
                        "draft_name": export_result.get("draft_name"),
                        "summary": summary,
                        "issues": issues,
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
