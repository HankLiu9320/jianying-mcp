# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name:track.py
"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')


class Track:
    """
    轨道管理类
    负责轨道的创建和数据存储
    """

    def __init__(self, draft_id: str, track_id: str = None):
        """
        初始化轨道

        Args:
            draft_id: 草稿ID
            track_id: 轨道ID
        """
        self.draft_id = draft_id
        self.track_id = track_id

    def add_track(self, track_type: str, track_name: Optional[str] = None) -> str:
        """
        添加轨道

        Args:
            track_type: 轨道类型，如 "video", "audio", "text"
            track_name: 轨道名称（可选）

        Returns:
            str: 轨道ID

        Raises:
            ValueError: 轨道类型无效或轨道名称格式错误
            NameError: 轨道名称已存在或同类型轨道需要指定名称
        """
        # 1. 验证轨道类型
        self._validate_track_type(track_type)

        # 2. 验证轨道唯一性
        self._validate_track_uniqueness(track_type, track_name)

        track_id = str(uuid.uuid4())

        # 构建轨道数据
        add_track_params = {
            "track_type": track_type
        }

        # 只添加用户明确传入的可选参数
        if track_name:
            add_track_params["track_name"] = track_name

        # 构建完整的轨道数据
        track_data = {
            "track_id": track_id,
            "operation": "add_track",
            "add_track": add_track_params,
            "created_at": datetime.now().isoformat()
        }

        # 保存参数
        self.add_json_to_file(track_data)
        self.track_id = track_id
        return track_id

    def add_json_to_file(self, new_data: Dict[str, Any]) -> bool:
        """
        向现有JSON文件中添加新的JSON数据，保持文件结构规范

        Args:
            new_data: 要添加的新数据

        Returns:
            bool: 添加是否成功
        """
        try:
            # 确保目录存在
            os.makedirs(f"{SAVE_PATH}/{self.draft_id}", exist_ok=True)
            file_path = f"{SAVE_PATH}/{self.draft_id}/track.json"

            # 读取现有数据
            existing_data = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        # 如果不是列表，转换为列表
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                except (json.JSONDecodeError, FileNotFoundError):
                    # 如果文件不存在或格式错误，初始化为空列表
                    existing_data = []

            # 添加新数据
            existing_data.append(new_data)

            # 保存为规范的JSON数组格式
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"添加JSON数据失败: {e}")
            return False

    def get_tracks(self) -> list:
        """
        获取所有轨道记录

        Returns:
            List: 轨道记录列表
        """
        try:
            from jianyingdraft.utils.global_cache import GlobalBatchCache
            file_path = f"{SAVE_PATH}/{self.draft_id}/track.json"
            return GlobalBatchCache.get_json(file_path)
        except Exception as e:
            print(f"读取轨道数据失败: {e}")
            return []

    def get_track_by_id(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        根据轨道ID获取轨道信息

        Args:
            track_id: 轨道ID

        Returns:
            Dict: 轨道信息，如果不存在返回None
        """
        tracks = self.get_tracks()
        for track in tracks:
            if track.get("track_id") == track_id:
                return track
        return None

    def get_tracks_by_type(self, track_type: str) -> list:
        """
        根据轨道类型获取轨道列表

        Args:
            track_type: 轨道类型

        Returns:
            List: 指定类型的轨道列表
        """
        tracks = self.get_tracks()
        result = []
        for track in tracks:
            add_track_data = track.get("add_track", {})
            if add_track_data.get("track_type") == track_type:
                result.append(track)
        return result

    def delete_track(self, track_id: str) -> bool:
        """
        删除指定轨道

        Args:
            track_id: 轨道ID

        Returns:
            bool: 删除是否成功
        """
        try:
            tracks = self.get_tracks()
            updated_tracks = [track for track in tracks if track.get("track_id") != track_id]

            if len(updated_tracks) == len(tracks):
                print(f"未找到轨道ID: {track_id}")
                return False

            file_path = f"{SAVE_PATH}/{self.draft_id}/track.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(updated_tracks, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"删除轨道失败: {e}")
            return False

    def get_track_count(self) -> int:
        """
        获取轨道总数

        Returns:
            int: 轨道数量
        """
        return len(self.get_tracks())

    def get_track_count_by_type(self, track_type: str) -> int:
        """
        获取指定类型的轨道数量

        Args:
            track_type: 轨道类型

        Returns:
            int: 指定类型的轨道数量
        """
        return len(self.get_tracks_by_type(track_type))

    def _validate_track_type(self, track_type: str):
        """验证轨道类型"""
        valid_types = {"video", "audio", "text"}
        if track_type not in valid_types:
            raise ValueError(f"无效的轨道类型: {track_type}，支持的类型: {', '.join(valid_types)}")

    def _validate_track_uniqueness(self, track_type: str, track_name: Optional[str]):
        """验证轨道唯一性"""
        existing_tracks = self.get_tracks()

        # 检查轨道名称唯一性
        if track_name:
            for track in existing_tracks:
                add_track_data = track.get("add_track", {})
                if add_track_data.get("track_name") == track_name:
                    raise NameError(f"轨道名称已存在: {track_name}")

        # 检查同类型轨道是否需要命名
        same_type_tracks = self.get_tracks_by_type(track_type)
        if len(same_type_tracks) > 0 and not track_name:
            raise NameError(f"已存在 {track_type} 类型的轨道，请为新轨道指定名称以避免混淆")

    def validate_track_exists(self, track_name: str) -> bool:
        """验证轨道是否存在"""
        if not track_name:
            return False

        existing_tracks = self.get_tracks()
        for track in existing_tracks:
            add_track_data = track.get("add_track", {})
            if add_track_data.get("track_name") == track_name:
                return True
        return False

    def get_track_by_name(self, track_name: str) -> Optional[Dict[str, Any]]:
        """根据轨道名称获取轨道信息"""
        existing_tracks = self.get_tracks()
        for track in existing_tracks:
            add_track_data = track.get("add_track", {})
            if add_track_data.get("track_name") == track_name:
                return track
        return None


