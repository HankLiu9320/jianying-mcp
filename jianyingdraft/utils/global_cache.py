# -*- coding: utf-8 -*-
"""批量操作内存缓存：合并 JSON 写入、复用媒体时长与轨道数据。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

# 跨 MCP 调用的进程级时长缓存（同一路径只解析一次）
_PERSISTENT_MEDIA_DURATION: Dict[str, Optional[float]] = {}


class GlobalBatchCache:
    _active = False
    _json_cache: Dict[str, List[Any]] = {}
    _media_duration_cache: Dict[str, Optional[float]] = {}
    _material_copy_cache: Dict[str, str] = {}
    _validated_tracks: Set[Tuple[str, str, str]] = set()  # (draft_id, track_name, segment_type)

    @classmethod
    def start_batch(cls) -> None:
        cls._active = True
        cls._json_cache.clear()
        cls._media_duration_cache.clear()
        cls._material_copy_cache.clear()
        cls._validated_tracks.clear()

    @classmethod
    def end_batch(cls) -> None:
        if not cls._active:
            return

        for file_path, data in cls._json_cache.items():
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        cls._active = False
        cls._json_cache.clear()
        cls._media_duration_cache.clear()
        cls._material_copy_cache.clear()
        cls._validated_tracks.clear()

    @classmethod
    def is_active(cls) -> bool:
        return cls._active

    @classmethod
    def _load_json_file(cls, file_path: str) -> List[Any]:
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except (json.JSONDecodeError, OSError):
            return []

    @classmethod
    def append_json(cls, file_path: str, new_data: Dict[str, Any]) -> bool:
        if not cls._active:
            existing_data = cls._load_json_file(file_path)
            existing_data.append(new_data)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            return True

        if file_path not in cls._json_cache:
            cls._json_cache[file_path] = cls._load_json_file(file_path)

        cls._json_cache[file_path].append(new_data)
        return True

    @classmethod
    def get_json(cls, file_path: str) -> List[Any]:
        if cls._active and file_path in cls._json_cache:
            return cls._json_cache[file_path]

        return cls._load_json_file(file_path)

    @classmethod
    def get_media_duration(cls, media_path: str) -> Optional[float]:
        if media_path in cls._media_duration_cache:
            return cls._media_duration_cache[media_path]
        if media_path in _PERSISTENT_MEDIA_DURATION:
            duration = _PERSISTENT_MEDIA_DURATION[media_path]
            cls._media_duration_cache[media_path] = duration
            return duration
        return None

    @classmethod
    def set_media_duration(cls, media_path: str, duration: Optional[float]) -> None:
        cls._media_duration_cache[media_path] = duration
        _PERSISTENT_MEDIA_DURATION[media_path] = duration

    @classmethod
    def prewarm_media_durations(cls, media_paths: List[str]) -> None:
        """批量开始前解析所有唯一素材时长，避免循环内重复调用 MediaInfo。"""
        from jianyingdraft.utils.media_parser import resolve_media_duration

        for path in media_paths:
            if not path or cls.get_media_duration(path) is not None:
                continue
            duration = resolve_media_duration(path)
            cls.set_media_duration(path, duration)

    @classmethod
    def get_copied_material(cls, draft_id: str, source_path: str) -> Optional[str]:
        if cls._active:
            key = f"{draft_id}:{source_path}"
            return cls._material_copy_cache.get(key)
        return None

    @classmethod
    def set_copied_material(cls, draft_id: str, source_path: str, target_path: str) -> None:
        if cls._active:
            key = f"{draft_id}:{source_path}"
            cls._material_copy_cache[key] = target_path

    @classmethod
    def get_track_json_path(cls, draft_id: str) -> str:
        from dotenv import load_dotenv

        load_dotenv()
        save_path = os.getenv("SAVE_PATH")
        return f"{save_path}/{draft_id}/track.json"

    @classmethod
    def prewarm_track_cache(cls, draft_id: str) -> None:
        """预加载 track.json 到内存，避免每个片段两次磁盘读取。"""
        if not cls._active:
            return
        file_path = cls.get_track_json_path(draft_id)
        if file_path not in cls._json_cache:
            cls._json_cache[file_path] = cls._load_json_file(file_path)

    @classmethod
    def get_track_by_name(cls, draft_id: str, track_name: str) -> Optional[Dict[str, Any]]:
        file_path = cls.get_track_json_path(draft_id)
        for track in cls.get_json(file_path):
            add_track_data = track.get("add_track", {})
            if add_track_data.get("track_name") == track_name:
                return track
        return None

    @classmethod
    def is_track_validated(cls, draft_id: str, track_name: str, segment_type: str) -> bool:
        return (draft_id, track_name, segment_type) in cls._validated_tracks

    @classmethod
    def mark_track_validated(cls, draft_id: str, track_name: str, segment_type: str) -> None:
        cls._validated_tracks.add((draft_id, track_name, segment_type))
