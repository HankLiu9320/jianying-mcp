# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: audio_service.py
"""
import json
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Optional, Dict, Any, List
from websocket import WebSocketApp
from jianyingdraft.jianying.audio import AudioSegment
from jianyingdraft.utils.response import ToolResponse

WS_URL = "wss://sami.bytedance.com/internal/api/v2/ws?device_id=420445199538212&iid=420445199542308"
APP_KEY = "IZjhUeAYwP"
NAMESPACE = "TTS"
DEFAULT_SPEAKER = "BV411_streaming"
DEFAULT_FORMAT = "mp3"
BIT_RATE = 64000
SAMPLE_RATE = 24000
TASK_SUCCESS_CODE = 20000000


def _sanitize_output_name(output_name: Optional[str]) -> str:
    if output_name:
        safe_name = "".join(ch for ch in output_name if ch.isalnum() or ch in ("-", "_", ".")).strip(".")
        if not safe_name:
            raise ValueError("output_name 非法，请仅使用字母数字/._-")
        if not safe_name.lower().endswith(f".{DEFAULT_FORMAT}"):
            safe_name = f"{safe_name}.{DEFAULT_FORMAT}"
        return safe_name

    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"tts_{ts}.{DEFAULT_FORMAT}"


def _build_start_task_message(text: str, speaker: Optional[str]) -> str:
    payload = {
        "audio_config": {
            "bit_rate": BIT_RATE,
            "format": DEFAULT_FORMAT,
            "sample_rate": SAMPLE_RATE
        },
        "speaker": speaker.strip() if speaker and speaker.strip() else DEFAULT_SPEAKER,
        "text": text
    }
    start_task = {
        "appkey": APP_KEY,
        "event": "StartTask",
        "namespace": NAMESPACE,
        "payload": json.dumps(payload, ensure_ascii=False)
    }
    return json.dumps(start_task, ensure_ascii=False)


def text_to_speech_service(
    text: str,
    speaker: Optional[str] = None,
    output_name: Optional[str] = None
) -> ToolResponse:
    """
    文本转语音服务（字节 WebSocket TTS）

    Args:
        text: 要合成的文本
        speaker: 发音人（可选），默认 BV411_streaming
        output_name: 输出文件名（可选）

    Returns:
        ToolResponse: 返回生成音频路径
    """
    try:
        if not text or not text.strip():
            return ToolResponse(success=False, message="文本不能为空")

        root_dir = Path(__file__).resolve().parents[2]
        material_dir = root_dir / "material"
        material_dir.mkdir(parents=True, exist_ok=True)
        output_path = material_dir / _sanitize_output_name(output_name)

        audio_chunks: List[bytes] = []
        done_event = Event()
        state: Dict[str, Any] = {
            "status_code": None,
            "status_text": "",
            "error": None,
            "finished": False
        }

        def on_open(ws):
            try:
                ws.send(_build_start_task_message(text=text.strip(), speaker=speaker))
            except Exception as e:
                state["error"] = str(e)
                done_event.set()
                ws.close()

        def on_message(ws, message):
            try:
                if isinstance(message, (bytes, bytearray)):
                    audio_chunks.append(bytes(message))
                    return

                node = json.loads(message)
                event = node.get("event")
                if event == "TaskFinished":
                    state["status_code"] = int(node.get("status_code", 0))
                    state["status_text"] = node.get("status_text", "")
                    state["finished"] = True
                    done_event.set()
                    ws.close()
            except Exception as e:
                state["error"] = str(e)
                done_event.set()
                ws.close()

        def on_error(ws, error):
            state["error"] = str(error)
            done_event.set()

        ws_app = WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error
        )

        ws_thread = Thread(
            target=lambda: ws_app.run_forever(ping_interval=20, ping_timeout=10),
            daemon=True
        )
        ws_thread.start()

        if not done_event.wait(timeout=30):
            ws_app.close()
            return ToolResponse(success=False, message="文本转语音失败: TTS 调用超时")

        ws_thread.join(timeout=2)

        if state["error"]:
            return ToolResponse(success=False, message=f"文本转语音失败: {state['error']}")

        if not state["finished"]:
            return ToolResponse(success=False, message="文本转语音失败: 任务未正常完成")

        if state["status_code"] != TASK_SUCCESS_CODE:
            return ToolResponse(
                success=False,
                message=f"文本转语音失败: code={state['status_code']}, msg={state['status_text']}"
            )

        if not audio_chunks:
            return ToolResponse(success=False, message="文本转语音失败: 未收到音频数据")

        output_path.write_bytes(b"".join(audio_chunks))

        return ToolResponse(
            success=True,
            message="文本转语音成功",
            data={
                "audio_path": str(output_path),
                "format": DEFAULT_FORMAT,
                "speaker": speaker.strip() if speaker and speaker.strip() else DEFAULT_SPEAKER,
                "ws_url": WS_URL
            }
        )
    except ValueError as e:
        return ToolResponse(success=False, message=f"文本转语音失败: {str(e)}")
    except Exception as e:
        return ToolResponse(success=False, message=f"文本转语音失败: {str(e)}")


def add_audio_segment_service(
    draft_id: str,
    material: str,
    target_timerange: str,
    source_timerange: Optional[str] = None,
    speed: Optional[float] = None,
    volume: float = 1.0,
    change_pitch: bool = False,
    track_name: Optional[str] = None
) -> ToolResponse:
    """
    音频片段添加服务 - 创建音频片段
    
    Args:
        draft_id: 草稿ID
        material: 音频文件路径，包括本地路径或者URL
        target_timerange: 片段在轨道上的目标时间范围，格式如 "0s-4.2s"
        source_timerange: 从源音频文件中截取的时间范围，格式如 "1s-5.2s"（可选）
        speed: 播放速度，默认为1.0（可选）
        volume: 音量，默认1.0
        change_pitch: 是否跟随变速改变音调，默认False
        track_name: 指定的轨道名称（可选）
    
    Returns:
        ToolResponse: 包含操作结果的响应对象
    """
    try:
        # 创建AudioSegment实例
        audio_segment = AudioSegment(draft_id, track_name=track_name)
        
        # 调用音频片段添加方法
        result_data = audio_segment.add_audio_segment(
            material=material,
            target_timerange=target_timerange,
            source_timerange=source_timerange,
            speed=speed,
            volume=volume,
            change_pitch=change_pitch,
            track_name=track_name
        )
        
        # 构建返回数据
        response_data = {
            "audio_segment_id": audio_segment.audio_segment_id,
            "draft_id": draft_id,
            "material": material,
            "target_timerange": target_timerange,
            "volume": volume,
            "change_pitch": change_pitch,
            "add_audio_segment": result_data
        }
        
        # 添加可选参数到返回数据
        if source_timerange:
            response_data["source_timerange"] = source_timerange
        if speed is not None:
            response_data["speed"] = speed
        if track_name:
            response_data["track_name"] = track_name
        
        return ToolResponse(
            success=True,
            message=f"音频片段添加成功: {material}",
            data=response_data
        )
        
    except ValueError as e:
        # 处理参数错误
        return ToolResponse(
            success=False,
            message=f"参数错误: {str(e)}"
        )
        
    except NameError as e:
        # 处理轨道不存在错误
        return ToolResponse(
            success=False,
            message=f"轨道错误: {str(e)}"
        )
        
    except Exception as e:
        # 处理其他未预期的错误
        return ToolResponse(
            success=False,
            message=f"音频片段添加失败: {str(e)}"
        )


def add_audio_effect_service(
    draft_id: str,
    audio_segment_id: str,
    effect_type: str,
    effect_name: str,
    params: Optional[List[Optional[float]]] = None,
    track_name: Optional[str] = None
) -> ToolResponse:
    """
    音频特效添加服务 - 为音频片段添加特效

    Args:
        draft_id: 草稿ID
        audio_segment_id: 音频片段ID
        effect_type: 特效类型，"AudioSceneEffectType"、"ToneEffectType"、"SpeechToSongType"
        effect_name: 特效名称，如 "雨声"、"机器人"、"Lofi" 等
        params: 特效参数列表（可选），参数范围0-100
        track_name: 轨道名称（可选）

    Returns:
        ToolResponse: 包含操作结果的响应对象
    """
    try:
        # 创建AudioSegment实例，传入audio_segment_id
        audio_segment = AudioSegment(draft_id, audio_segment_id=audio_segment_id, track_name=track_name)

        # 调用音频特效添加方法
        result_data = audio_segment.add_effect(
            effect_type=effect_type,
            effect_name=effect_name,
            params=params
        )

        # 构建返回数据
        response_data = {
            "audio_segment_id": audio_segment_id,
            "draft_id": draft_id,
            "effect_type": effect_type,
            "effect_name": effect_name,
            "add_effect": result_data
        }

        # 添加可选参数到返回数据
        if params:
            response_data["params"] = params
        if track_name:
            response_data["track_name"] = track_name

        return ToolResponse(
            success=True,
            message=f"音频特效添加成功: {effect_type}.{effect_name}",
            data=response_data
        )

    except ValueError as e:
        # 处理参数错误
        return ToolResponse(
            success=False,
            message=f"参数错误: {str(e)}"
        )

    except NameError as e:
        # 处理轨道不存在错误
        return ToolResponse(
            success=False,
            message=f"轨道错误: {str(e)}"
        )

    except Exception as e:
        # 处理其他未预期的错误
        return ToolResponse(
            success=False,
            message=f"音频特效添加失败: {str(e)}"
        )


def add_audio_fade_service(
    draft_id: str,
    audio_segment_id: str,
    in_duration: str,
    out_duration: str,
    track_name: Optional[str] = None
) -> ToolResponse:
    """
    音频淡入淡出添加服务 - 为音频片段添加淡入淡出效果

    Args:
        draft_id: 草稿ID
        audio_segment_id: 音频片段ID
        in_duration: 音频淡入时长，格式如 "1s"、"500ms"
        out_duration: 音频淡出时长，格式如 "1s"、"500ms"
        track_name: 轨道名称（可选）

    Returns:
        ToolResponse: 包含操作结果的响应对象
    """
    try:
        # 创建AudioSegment实例，传入audio_segment_id
        audio_segment = AudioSegment(draft_id, audio_segment_id=audio_segment_id, track_name=track_name)

        # 调用音频淡入淡出添加方法
        result_data = audio_segment.add_fade(
            in_duration=in_duration,
            out_duration=out_duration
        )

        # 构建返回数据
        response_data = {
            "audio_segment_id": audio_segment_id,
            "draft_id": draft_id,
            "in_duration": in_duration,
            "out_duration": out_duration,
            "add_fade": result_data
        }

        # 添加可选参数到返回数据
        if track_name:
            response_data["track_name"] = track_name

        return ToolResponse(
            success=True,
            message=f"音频淡入淡出添加成功: 淡入{in_duration}, 淡出{out_duration}",
            data=response_data
        )

    except ValueError as e:
        # 处理参数错误
        return ToolResponse(
            success=False,
            message=f"参数错误: {str(e)}"
        )

    except NameError as e:
        # 处理轨道不存在错误
        return ToolResponse(
            success=False,
            message=f"轨道错误: {str(e)}"
        )

    except Exception as e:
        # 处理其他未预期的错误
        return ToolResponse(
            success=False,
            message=f"音频淡入淡出添加失败: {str(e)}"
        )


def add_audio_keyframe_service(
    draft_id: str,
    audio_segment_id: str,
    time_offset: str,
    volume: float,
    track_name: Optional[str] = None
) -> ToolResponse:
    """
    音频关键帧添加服务 - 为音频片段添加音量关键帧

    Args:
        draft_id: 草稿ID
        audio_segment_id: 音频片段ID
        time_offset: 关键帧的时间偏移量，格式如 "0s"、"1.5s"
        volume: 音量在time_offset处的值，范围通常0.0-1.0
        track_name: 轨道名称（可选）

    Returns:
        ToolResponse: 包含操作结果的响应对象
    """
    try:
        # 创建AudioSegment实例，传入audio_segment_id
        audio_segment = AudioSegment(draft_id, audio_segment_id=audio_segment_id, track_name=track_name)

        # 调用音频关键帧添加方法
        result_data = audio_segment.add_keyframe(
            time_offset=time_offset,
            volume=volume
        )

        # 构建返回数据
        response_data = {
            "audio_segment_id": audio_segment_id,
            "draft_id": draft_id,
            "time_offset": time_offset,
            "volume": volume,
            "add_keyframe": result_data
        }

        # 添加可选参数到返回数据
        if track_name:
            response_data["track_name"] = track_name

        return ToolResponse(
            success=True,
            message=f"音频关键帧添加成功: 时间{time_offset}, 音量{volume}",
            data=response_data
        )

    except ValueError as e:
        # 处理参数错误
        return ToolResponse(
            success=False,
            message=f"参数错误: {str(e)}"
        )

    except NameError as e:
        # 处理轨道不存在错误
        return ToolResponse(
            success=False,
            message=f"轨道错误: {str(e)}"
        )

    except Exception as e:
        # 处理其他未预期的错误
        return ToolResponse(
            success=False,
            message=f"音频关键帧添加失败: {str(e)}"
        )
