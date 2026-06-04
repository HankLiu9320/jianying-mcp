# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: overlap_validator.py
"""
import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from jianyingdraft.utils.time_format import parse_time_to_ms

# 加载环境变量
load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')


class TimeRange:
    """时间范围类，用于重叠计算"""

    def __init__(self, start_str: str, duration_str: str):
        """
        初始化时间范围
        
        Args:
            start_str: 开始时间字符串，如 "0s", "1.5s"
            duration_str: 持续时间字符串，如 "5s", "3.2s"
        """
        self.start_microseconds = self._parse_time(start_str)
        self.duration_microseconds = self._parse_time(duration_str)
        self.end_microseconds = self.start_microseconds + self.duration_microseconds

    def _parse_time(self, time_str: str) -> int:
        """
        解析时间字符串为微秒
        
        Args:
            time_str: 时间字符串，如 "1.5s"
            
        Returns:
            int: 微秒数
        """
        return parse_time_to_ms(time_str) * 1000  # 毫秒 -> 微秒，与 pyJianYingDraft tim() 取整一致

    def overlaps_with(self, other: 'TimeRange') -> bool:
        """
        检查与另一个时间范围是否重叠
        
        Args:
            other: 另一个时间范围
            
        Returns:
            bool: 是否重叠
        """
        # 重叠条件：两个时间段有交集
        # 不重叠的条件：A完全在B之前 OR A完全在B之后
        # 重叠 = NOT (A完全在B之前 OR A完全在B之后)
        return not (self.end_microseconds <= other.start_microseconds or
                    self.start_microseconds >= other.end_microseconds)

    def __str__(self):
        """返回时间范围的字符串表示"""
        start_sec = self.start_microseconds / 1_000_000
        end_sec = self.end_microseconds / 1_000_000
        return f"{start_sec}s-{end_sec}s"


class OverlapValidator:
    """片段重叠验证器"""

    def __init__(self, draft_id: str):
        """
        初始化验证器
        
        Args:
            draft_id: 草稿ID
        """
        self.draft_id = draft_id

    def validate_segment_overlap(self, segment_type: str, track_name: str,
                                 target_timerange: Dict[str, str]) -> None:
        """
        验证片段是否与同轨道现有片段重叠
        
        Args:
            segment_type: 片段类型 ("video", "audio", "text")
            track_name: 轨道名称
            target_timerange: 片段在轨道上的目标时间范围，格式 {"start": "0s", "duration": "5s"}，表示在轨道上从0s开始，持续5s
            
        Raises:
            ValueError: 片段重叠时抛出异常
        """
        if not track_name:
            # 如果没有指定轨道名称，跳过验证
            return

        # 解析新片段的时间范围
        new_range = TimeRange(
            target_timerange["start"],
            target_timerange["duration"]
        )

        # 获取同轨道的现有片段
        existing_segments = self._get_segments_by_track(segment_type, track_name)

        # 检查与每个现有片段的重叠
        for segment in existing_segments:
            existing_range = self._extract_timerange_from_segment(segment)
            if existing_range and new_range.overlaps_with(existing_range):
                raise ValueError(
                    f"片段时间重叠: 新片段 {new_range} 与轨道 '{track_name}' 中现有片段 {existing_range} 重叠"
                )

    def _get_segments_by_track(self, segment_type: str, track_name: str) -> List[Dict[str, Any]]:
        """
        获取指定轨道的所有片段
        
        Args:
            segment_type: 片段类型
            track_name: 轨道名称
            
        Returns:
            List[Dict]: 片段列表
        """
        try:
            from jianyingdraft.utils.global_cache import GlobalBatchCache
            file_path = f"{SAVE_PATH}/{self.draft_id}/{segment_type}.json"
            all_segments = GlobalBatchCache.get_json(file_path)

            # 筛选同轨道的片段
            track_segments = []
            for segment in all_segments:
                if segment.get("track_name") == track_name:
                    track_segments.append(segment)

            return track_segments

        except Exception as e:
            print(f"读取片段数据失败: {e}")
            return []

    def _extract_timerange_from_segment(self, segment: Dict[str, Any]) -> Optional[TimeRange]:
        """
        从片段数据中提取时间范围
        
        Args:
            segment: 片段数据
            
        Returns:
            TimeRange: 时间范围对象，如果提取失败返回None
        """
        try:
            # 根据操作类型提取时间范围
            operation = segment.get("operation")
            if operation == "add_video_segment":
                timerange_data = segment.get("add_video_segment", {}).get("target_timerange", {})
            elif operation == "add_audio_segment":
                timerange_data = segment.get("add_audio_segment", {}).get("target_timerange", {})
            elif operation == "add_text_segment":
                timerange_data = segment.get("add_text_segment", {}).get("timerange", {})
            else:
                return None

            if not timerange_data:
                return None

            start = timerange_data.get("start")
            duration = timerange_data.get("duration")

            if start and duration:
                return TimeRange(start, duration)

        except Exception as e:
            print(f"提取时间范围失败: {e}")

        return None


# 便捷函数
def validate_overlap(draft_id: str, segment_type: str, track_name: str,
                     target_timerange: Dict[str, str]) -> None:
    """
    便捷的重叠验证函数
    
    Args:
        draft_id: 草稿ID
        segment_type: 片段类型
        track_name: 轨道名称
        target_timerange: 片段在轨道上的目标时间范围，格式 {"start": "0s", "duration": "5s"}，表示在轨道上从0s开始，持续5s
    """
    validator = OverlapValidator(draft_id)
    validator.validate_segment_overlap(segment_type, track_name, target_timerange)
