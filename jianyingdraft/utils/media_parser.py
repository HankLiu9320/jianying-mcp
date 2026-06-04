# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: media_parser.py
"""
import os
import tempfile
import requests
from urllib.parse import urlparse
from typing import Optional, Dict, Any
import pymediainfo

# 进程内复用解析器，避免重复创建
_shared_parser: Optional["MediaParser"] = None


class MediaParser:
    """媒体文件解析器"""

    def __init__(self):
        self.temp_files = []  # 记录临时文件，用于清理

    def parse_media_info(self, media_path: str) -> Optional[Dict[str, Any]]:
        try:
            if self._is_url(media_path):
                return self._parse_url_media(media_path)
            return self._parse_local_media(media_path)
        except Exception as e:
            print(f"解析媒体信息失败: {e}")
            return None

    def get_media_duration(self, media_path: str) -> Optional[float]:
        from jianyingdraft.utils.global_cache import GlobalBatchCache

        cached = GlobalBatchCache.get_media_duration(media_path)
        if cached is not None:
            return cached

        media_info = self.parse_media_info(media_path)
        duration = media_info.get("duration") if media_info else None
        GlobalBatchCache.set_media_duration(media_path, duration)
        return duration

    def _is_url(self, path: str) -> bool:
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _parse_local_media(self, file_path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        try:
            info = pymediainfo.MediaInfo.parse(
                file_path,
                mediainfo_options={"File_TestContinuousFileNames": "0"},
            )
            return self._extract_media_info(info)
        except Exception as e:
            print(f"解析本地文件失败: {file_path}, 错误: {e}")
            return None

    def _parse_url_media(self, url: str) -> Optional[Dict[str, Any]]:
        temp_file = None
        try:
            temp_file = self._download_to_temp(url)
            if not temp_file:
                return None
            return self._parse_local_media(temp_file)
        finally:
            if temp_file:
                self._cleanup_temp_file(temp_file)

    def _download_to_temp(self, url: str) -> Optional[str]:
        try:
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or ".tmp"

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
                temp_path = tmp_file.name
                print(f"正在下载: {url}")
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)

                self.temp_files.append(temp_path)
                print(f"下载完成: {temp_path}")
                return temp_path
        except Exception as e:
            print(f"下载失败: {url}, 错误: {e}")
            return None

    def _extract_media_info(self, media_info: pymediainfo.MediaInfo) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        try:
            general_track = None
            video_track = None
            audio_track = None

            for track in media_info.tracks:
                if track.track_type == "General":
                    general_track = track
                elif track.track_type == "Video":
                    video_track = track
                elif track.track_type == "Audio":
                    audio_track = track

            duration = None
            if general_track and general_track.duration:
                duration = float(general_track.duration) / 1000.0
            elif video_track and video_track.duration:
                duration = float(video_track.duration) / 1000.0
            elif audio_track and audio_track.duration:
                duration = float(audio_track.duration) / 1000.0

            if duration:
                result["duration"] = duration - 0.2

            if general_track:
                if general_track.file_size:
                    result["file_size"] = int(general_track.file_size)
                if general_track.format:
                    result["format"] = general_track.format

            if video_track:
                result["has_video"] = True
                if video_track.width:
                    result["width"] = int(video_track.width)
                if video_track.height:
                    result["height"] = int(video_track.height)
                if video_track.frame_rate:
                    result["frame_rate"] = float(video_track.frame_rate)

            if audio_track:
                result["has_audio"] = True
                if audio_track.sampling_rate:
                    result["sample_rate"] = int(audio_track.sampling_rate)
                if audio_track.channel_s:
                    result["channels"] = int(audio_track.channel_s)

        except Exception as e:
            print(f"提取媒体信息失败: {e}")

        return result

    def _cleanup_temp_file(self, temp_path: str) -> None:
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                if temp_path in self.temp_files:
                    self.temp_files.remove(temp_path)
        except Exception as e:
            print(f"清理临时文件失败: {temp_path}, 错误: {e}")

    def cleanup_all_temp_files(self) -> None:
        for temp_path in self.temp_files[:]:
            self._cleanup_temp_file(temp_path)

    def __del__(self):
        self.cleanup_all_temp_files()


def _get_shared_parser() -> MediaParser:
    global _shared_parser
    if _shared_parser is None:
        _shared_parser = MediaParser()
    return _shared_parser


def resolve_media_duration(media_path: str) -> Optional[float]:
    """解析媒体时长（优先缓存，其次 pymediainfo）。"""
    from jianyingdraft.utils.global_cache import GlobalBatchCache

    cached = GlobalBatchCache.get_media_duration(media_path)
    if cached is not None:
        return cached

    parser = _get_shared_parser()
    try:
        return parser.get_media_duration(media_path)
    finally:
        pass


def get_media_duration(media_path: str) -> Optional[float]:
    """
    获取媒体文件时长的便捷函数

    Args:
        media_path: 媒体文件路径或URL

    Returns:
        float: 时长（秒），获取失败返回None
    """
    return resolve_media_duration(media_path)


def parse_media_info(media_path: str) -> Optional[Dict[str, Any]]:
    """
    解析媒体文件信息的便捷函数

    Args:
        media_path: 媒体文件路径或URL

    Returns:
        Dict: 媒体信息，解析失败返回None
    """
    parser = _get_shared_parser()
    try:
        return parser.parse_media_info(media_path)
    finally:
        parser.cleanup_all_temp_files()
