# -*- coding: utf-8 -*-
"""
时间字符串解析与格式化：内部统一用毫秒整数计算，避免浮点累加误差。
"""
from __future__ import annotations

from typing import Tuple

MS_PER_SEC = 1000
# 素材时长校验容差（毫秒），覆盖 float 累加与微秒取整差异
DURATION_TOLERANCE_MS = 5


def parse_time_to_ms(time_str: str) -> int:
    """
    将时间字符串解析为毫秒整数。

    支持: "1.5s", "500ms", "0s"；不支持 h/m 复合（与 pyJianYingDraft tim 的复合格式区分）。
    """
    if not time_str:
        raise ValueError(f"无效的时间格式: {time_str}")

    text = time_str.strip().lower()
    if text.endswith("ms"):
        try:
            return int(round(float(text[:-2])))
        except ValueError as exc:
            raise ValueError(f"无效的时间格式: {time_str}") from exc

    if not text.endswith("s"):
        raise ValueError(f"时间格式须以 s 或 ms 结尾: {time_str}")

    try:
        seconds = float(text[:-1])
    except ValueError as exc:
        raise ValueError(f"无效的时间格式: {time_str}") from exc

    return int(round(seconds * MS_PER_SEC))


def format_ms_as_seconds_str(ms: int) -> str:
    """将毫秒格式化为秒字符串，最多 3 位小数，去掉尾随零。"""
    if ms < 0:
        raise ValueError(f"时间不能为负: {ms}ms")
    if ms % MS_PER_SEC == 0:
        return f"{ms // MS_PER_SEC}s"
    seconds = ms / MS_PER_SEC
    formatted = f"{seconds:.3f}".rstrip("0").rstrip(".")
    return f"{formatted}s"


def parse_start_end_to_ms(time_range_str: str) -> Tuple[int, int]:
    """
    解析「开始-结束」绝对时间范围为 (start_ms, end_ms)。
    """
    if not time_range_str or "-" not in time_range_str:
        raise ValueError(f"Invalid time range format: {time_range_str}")

    start_str, end_str = time_range_str.split("-", 1)
    start_ms = parse_time_to_ms(start_str.strip())
    end_ms = parse_time_to_ms(end_str.strip())

    if end_ms <= start_ms:
        raise ValueError(f"End time must be greater than start time: {time_range_str}")

    return start_ms, end_ms


def parse_start_end_format(time_range_str: str) -> str:
    """
    将 "开始时间-结束时间" 转为 "开始时间-持续时间"（毫秒整数差，避免浮点误差）。

    Args:
        time_range_str: 如 "1s-4.2s"

    Returns:
        如 "1s-3.2s"
    """
    start_ms, end_ms = parse_start_end_to_ms(time_range_str)
    duration_ms = end_ms - start_ms
    return f"{format_ms_as_seconds_str(start_ms)}-{format_ms_as_seconds_str(duration_ms)}"


def normalize_start_duration_timerange(timerange_str: str) -> str:
    """
    规范化「开始-持续」时间字符串（重新以毫秒解析并格式化）。
    """
    if not timerange_str or "-" not in timerange_str:
        raise ValueError(f"Invalid time range format: {timerange_str}")

    start_str, duration_str = timerange_str.split("-", 1)
    start_ms = parse_time_to_ms(start_str.strip())
    duration_ms = parse_time_to_ms(duration_str.strip())
    return f"{format_ms_as_seconds_str(start_ms)}-{format_ms_as_seconds_str(duration_ms)}"


def duration_ms_from_timerange_dict(timerange: dict) -> int:
    """从 {start, duration} 字典取持续时长（毫秒）。"""
    return parse_time_to_ms(timerange["duration"])


def clamp_timerange_dict_to_max_duration(
    timerange: dict,
    max_duration_ms: int,
    tolerance_ms: int = DURATION_TOLERANCE_MS,
) -> bool:
    """
    若持续时长略超素材上限，在容差内自动截断到 max_duration_ms。

    Returns:
        是否发生了截断
    """
    duration_ms = duration_ms_from_timerange_dict(timerange)
    if duration_ms <= max_duration_ms:
        return False

    if duration_ms > max_duration_ms + tolerance_ms:
        return False

    timerange["duration"] = format_ms_as_seconds_str(max_duration_ms)
    return True


def safe_media_duration_seconds(duration_seconds: Optional[float]) -> Optional[float]:
    """
    将媒体时长（秒）规范为最多 3 位小数的可用值，供 batch_parse 等返回给调用方。
    """
    if duration_seconds is None:
        return None
    ms = int(round(duration_seconds * MS_PER_SEC))
    return ms / MS_PER_SEC


def format_error_duration_exceeded(
    requested_ms: int,
    max_ms: int,
    material_path: str,
) -> str:
    max_sec = max_ms / MS_PER_SEC
    req_sec = requested_ms / MS_PER_SEC
    return (
        f"素材所占的轨道时长 {req_sec}s 超出素材可用时长 {max_sec}s"
        f"（路径: {material_path}），请缩短轨道所占时间或使用 batch_parse_media_durations 获取安全时长"
    )
