# -*- coding: utf-8 -*-
"""批量操作服务：在单次 MCP 调用内完成多轨道/多片段添加。"""
from typing import Any, Dict, List, Optional

from jianyingdraft.services.audio_service import add_audio_segment_service
from jianyingdraft.services.text_service import add_text_segment_service, add_text_animation_service
from jianyingdraft.services.track_service import create_track_service
from jianyingdraft.services.video_service import add_video_segment_service, add_video_animation_service
from jianyingdraft.utils.index_manager import index_manager
from jianyingdraft.utils.response import ToolResponse
from jianyingdraft.utils.time_format import parse_start_end_format


def _resolve_track_name(draft_id: str, track_id: Optional[str], track_name: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """返回 (track_id, track_name, error_message)。"""
    if track_id:
        resolved_name = index_manager.get_track_name_by_track_id(track_id)
        resolved_draft = index_manager.get_draft_id_by_track_id(track_id)
        if not resolved_draft:
            return None, None, f"未找到轨道: {track_id}"
        if resolved_draft != draft_id:
            return None, None, f"轨道 {track_id} 不属于草稿 {draft_id}"
        return track_id, resolved_name, None

    if track_name:
        resolved_id = index_manager.get_track_id_by_draft_and_name(draft_id, track_name)
        if not resolved_id:
            return None, None, f"草稿 {draft_id} 中未找到轨道: {track_name}"
        return resolved_id, track_name, None

    return None, None, "必须提供 track_id 或 track_name"


def _get_animation_fields(item: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """从 segment 项解析动效字段，返回 (animation_type, animation_name, animation_duration)。"""
    animation_type = item.get("animation_type")
    animation_name = item.get("animation_name")
    animation_duration = item.get("animation_duration")
    if animation_duration is None:
        animation_duration = item.get("duration")
    if animation_type is not None:
        animation_type = str(animation_type).strip() or None
    if animation_name is not None:
        animation_name = str(animation_name).strip() or None
    if animation_duration is not None:
        animation_duration = str(animation_duration).strip() or None
    return animation_type, animation_name, animation_duration


def _apply_segment_animation(
    draft_id: str,
    item: Dict[str, Any],
    segment_type: str,
    segment_id: str,
    track_name: Optional[str],
) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    片段创建成功后应用可选动效。

    Returns:
        (success, error_message, animation_info)
    """
    animation_type, animation_name, animation_duration = _get_animation_fields(item)
    if not animation_type and not animation_name:
        return True, None, None
    if not animation_type or not animation_name:
        return False, "animation_type 与 animation_name 须同时提供", None

    if segment_type == "video":
        response = add_video_animation_service(
            draft_id=draft_id,
            video_segment_id=segment_id,
            animation_type=animation_type,
            animation_name=animation_name,
            duration=animation_duration,
            track_name=track_name,
        )
    elif segment_type == "text":
        response = add_text_animation_service(
            draft_id=draft_id,
            text_segment_id=segment_id,
            animation_type=animation_type,
            animation_name=animation_name,
            duration=animation_duration,
            track_name=track_name,
        )
    else:
        return False, f"片段类型 {segment_type} 不支持动效", None

    if not response.success:
        return False, response.message, None

    return True, None, {
        "animation_type": animation_type,
        "animation_name": animation_name,
        "animation_duration": animation_duration,
    }


def batch_create_tracks_service(
    draft_id: str,
    tracks: List[Dict[str, str]],
    stop_on_error: bool = True,
) -> ToolResponse:
    """
    批量创建轨道。

    tracks 示例: [{"track_type": "video", "track_name": "video_bg"}, ...]
    """
    if not tracks:
        return ToolResponse(success=False, message="tracks 不能为空")

    results: List[Dict[str, Any]] = []
    succeeded = 0
    failed = 0

    for index, item in enumerate(tracks):
        track_type = item.get("track_type")
        track_name = item.get("track_name")
        if not track_type:
            result_item = {"index": index, "success": False, "message": "缺少 track_type"}
            failed += 1
            results.append(result_item)
            if stop_on_error:
                break
            continue

        response = create_track_service(draft_id, track_type, track_name)
        if response.success and response.data and "track_id" in response.data:
            track_id = response.data["track_id"]
            index_manager.add_track_mapping(track_id, draft_id, track_name, track_type)
            succeeded += 1
            results.append({
                "index": index,
                "success": True,
                "track_id": track_id,
                "track_name": track_name,
                "track_type": track_type,
            })
        else:
            failed += 1
            results.append({
                "index": index,
                "success": False,
                "track_name": track_name,
                "track_type": track_type,
                "message": response.message,
            })
            if stop_on_error:
                break

    overall_success = failed == 0
    return ToolResponse(
        success=overall_success,
        message=f"批量创建轨道完成: 成功 {succeeded}，失败 {failed}",
        data={
            "draft_id": draft_id,
            "total": len(tracks),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "track_map": index_manager.list_track_ids_by_draft_id(draft_id),
        },
    )


def _add_single_segment(draft_id: str, item: Dict[str, Any], index: int) -> Dict[str, Any]:
    segment_type = item.get("type")
    track_id, track_name, track_error = _resolve_track_name(
        draft_id,
        item.get("track_id"),
        item.get("track_name"),
    )
    if track_error:
        return {"index": index, "type": segment_type, "success": False, "message": track_error}

    target_start_end = item.get("target_start_end")
    if not target_start_end:
        return {"index": index, "type": segment_type, "success": False, "message": "缺少 target_start_end"}

    try:
        target_timerange = parse_start_end_format(target_start_end)
    except ValueError as exc:
        return {"index": index, "type": segment_type, "success": False, "message": f"target_start_end 格式错误: {exc}"}

    source_timerange = None
    source_start_end = item.get("source_start_end")
    if source_start_end:
        try:
            source_timerange = parse_start_end_format(source_start_end)
        except ValueError as exc:
            return {"index": index, "type": segment_type, "success": False, "message": f"source_start_end 格式错误: {exc}"}

    if segment_type == "video":
        response = add_video_segment_service(
            draft_id=draft_id,
            material=item.get("material", ""),
            target_timerange=target_timerange,
            source_timerange=source_timerange,
            speed=item.get("speed"),
            volume=item.get("volume", 1.0),
            change_pitch=item.get("change_pitch", False),
            clip_settings=item.get("clip_settings"),
            track_name=track_name,
        )
        if response.success and response.data:
            video_segment_id = response.data.get("video_segment_id")
            if video_segment_id and track_id:
                index_manager.add_video_segment_mapping(video_segment_id, track_id)
            result = {
                "index": index,
                "type": "video",
                "success": True,
                "track_name": track_name,
                "video_segment_id": video_segment_id,
            }
            if video_segment_id:
                anim_ok, anim_err, anim_info = _apply_segment_animation(
                    draft_id, item, "video", video_segment_id, track_name
                )
                if anim_info:
                    result["animation"] = anim_info
                if not anim_ok:
                    result["success"] = False
                    result["message"] = f"片段已添加但动效失败: {anim_err}"
            return result
        return {"index": index, "type": "video", "success": False, "message": response.message}

    if segment_type == "audio":
        material = item.get("material")
        if not material:
            return {"index": index, "type": "audio", "success": False, "message": "缺少 material"}
        response = add_audio_segment_service(
            draft_id=draft_id,
            material=material,
            target_timerange=target_timerange,
            source_timerange=source_timerange,
            speed=item.get("speed"),
            volume=item.get("volume", 1.0),
            change_pitch=item.get("change_pitch", False),
            track_name=track_name,
        )
        if response.success and response.data:
            audio_segment_id = response.data.get("audio_segment_id")
            if audio_segment_id and track_id:
                index_manager.add_audio_segment_mapping(audio_segment_id, track_id)
            return {
                "index": index,
                "type": "audio",
                "success": True,
                "track_name": track_name,
                "audio_segment_id": audio_segment_id,
            }
        return {"index": index, "type": "audio", "success": False, "message": response.message}

    if segment_type == "text":
        text = item.get("text")
        if not text:
            return {"index": index, "type": "text", "success": False, "message": "缺少 text"}
        response = add_text_segment_service(
            draft_id=draft_id,
            text=text,
            timerange=target_timerange,
            font=item.get("font"),
            style=item.get("style"),
            clip_settings=item.get("clip_settings"),
            border=item.get("border"),
            background=item.get("background"),
            track_name=track_name,
        )
        if response.success and response.data:
            text_segment_id = response.data.get("text_segment_id")
            if text_segment_id and track_id:
                index_manager.add_text_segment_mapping(text_segment_id, track_id)
            result = {
                "index": index,
                "type": "text",
                "success": True,
                "track_name": track_name,
                "text_segment_id": text_segment_id,
            }
            if text_segment_id:
                anim_ok, anim_err, anim_info = _apply_segment_animation(
                    draft_id, item, "text", text_segment_id, track_name
                )
                if anim_info:
                    result["animation"] = anim_info
                if not anim_ok:
                    result["success"] = False
                    result["message"] = f"片段已添加但动效失败: {anim_err}"
            return result
        return {"index": index, "type": "text", "success": False, "message": response.message}

    return {"index": index, "success": False, "message": f"不支持的片段类型: {segment_type}"}


def batch_add_segments_service(
    draft_id: str,
    segments: List[Dict[str, Any]],
    stop_on_error: bool = True,
) -> ToolResponse:
    """
    批量添加 video/audio/text 片段；video/text 可选内联入场动效。

    每个 segment 需包含:
    - type: "video" | "audio" | "text"
    - track_name 或 track_id
    - target_start_end: "开始s-结束s"（绝对结束时间，与单条 add_*_segment 一致）
    - 其余字段同对应单条工具

    video/text 可选动效字段（分镜 02 动效类型/动效名称列）:
    - animation_type: 如 IntroType、TextIntro、OutroType、GroupAnimationType、TextOutro、TextLoopAnim
    - animation_name: 如 渐显、放大、向右滑动（须与 animation_type 同时提供）
    - animation_duration: 可选，如 "0.5s"
    """
    if not segments:
        return ToolResponse(success=False, message="segments 不能为空")

    results: List[Dict[str, Any]] = []
    succeeded = 0
    failed = 0

    for index, item in enumerate(segments):
        result_item = _add_single_segment(draft_id, item, index)
        results.append(result_item)
        if result_item.get("success"):
            succeeded += 1
        else:
            failed += 1
            if stop_on_error:
                break

    overall_success = failed == 0
    return ToolResponse(
        success=overall_success,
        message=f"批量添加片段完成: 成功 {succeeded}，失败 {failed}",
        data={
            "draft_id": draft_id,
            "total": len(segments),
            "processed": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        },
    )
