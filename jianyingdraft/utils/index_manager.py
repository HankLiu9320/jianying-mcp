# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name: index_manager.py
"""
import json
import os
import uuid
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')


class IndexManager:
    """
    索引管理器
    负责维护草稿ID、轨道ID、片段ID之间的映射关系
    """
    
    def __init__(self):
        self.index_file_path = os.path.join(SAVE_PATH, "global_index.json")
        self._ensure_index_file()
    
    def _ensure_index_file(self):
        """确保索引文件存在"""
        if not os.path.exists(self.index_file_path):
            # 创建空的索引结构
            empty_index = {
                "draft_mappings": {},
                "track_mappings": {},
                "video_segment_mappings": {},
                "audio_segment_mappings": {},
                "text_segment_mappings": {}
            }
            self._save_index(empty_index)
    
    def _load_index(self) -> Dict[str, Any]:
        """加载索引数据"""
        try:
            with open(self.index_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载索引文件失败: {e}")
            return {
                "draft_mappings": {},
                "track_mappings": {},
                "video_segment_mappings": {},
                "audio_segment_mappings": {},
                "text_segment_mappings": {}
            }
    
    def _save_index(self, index_data: Dict[str, Any]):
        """保存索引数据"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.index_file_path), exist_ok=True)
            with open(self.index_file_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存索引文件失败: {e}")
    
    # ==================== 添加映射方法 ====================
    
    def add_draft_mapping(self, draft_id: str, draft_info: Dict[str, Any]):
        """
        添加草稿映射记录
        
        Args:
            draft_id: 草稿ID
            draft_info: 草稿信息字典
        """
        index_data = self._load_index()
        index_data["draft_mappings"][draft_id] = draft_info
        self._save_index(index_data)
    
    def add_track_mapping(self, track_id: str, draft_id: str, track_name: str, track_type: str):
        """
        添加轨道映射
        
        Args:
            track_id: 轨道ID
            draft_id: 草稿ID
            track_name: 轨道名称
            track_type: 轨道类型 (video/audio/text)
        """
        index_data = self._load_index()
        index_data["track_mappings"][track_id] = {
            "draft_id": draft_id,
            "track_name": track_name,
            "track_type": track_type
        }
        self._save_index(index_data)
    
    def add_video_segment_mapping(self, video_segment_id: str, track_id: str):
        """
        添加视频片段映射
        
        Args:
            video_segment_id: 视频片段ID
            track_id: 轨道ID
        """
        index_data = self._load_index()
        # 通过track_id获取draft_id
        draft_id = self.get_draft_id_by_track_id(track_id)
        if draft_id:
            index_data["video_segment_mappings"][video_segment_id] = {
                "draft_id": draft_id,
                "track_id": track_id
            }
            self._save_index(index_data)
    
    def add_audio_segment_mapping(self, audio_segment_id: str, track_id: str):
        """
        添加音频片段映射
        
        Args:
            audio_segment_id: 音频片段ID
            track_id: 轨道ID
        """
        index_data = self._load_index()
        # 通过track_id获取draft_id
        draft_id = self.get_draft_id_by_track_id(track_id)
        if draft_id:
            index_data["audio_segment_mappings"][audio_segment_id] = {
                "draft_id": draft_id,
                "track_id": track_id
            }
            self._save_index(index_data)
    
    def add_text_segment_mapping(self, text_segment_id: str, track_id: str):
        """
        添加文本片段映射
        
        Args:
            text_segment_id: 文本片段ID
            track_id: 轨道ID
        """
        index_data = self._load_index()
        # 通过track_id获取draft_id
        draft_id = self.get_draft_id_by_track_id(track_id)
        if draft_id:
            index_data["text_segment_mappings"][text_segment_id] = {
                "draft_id": draft_id,
                "track_id": track_id
            }
            self._save_index(index_data)

    
    def get_draft_info(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """
        获取草稿完整信息
        
        Args:
            draft_id: 草稿ID
            
        Returns:
            草稿信息字典，如果不存在返回None
        """
        index_data = self._load_index()
        return index_data["draft_mappings"].get(draft_id)
    
    def get_draft_id_by_track_id(self, track_id: str) -> Optional[str]:
        """
        通过轨道ID获取草稿ID
        
        Args:
            track_id: 轨道ID
            
        Returns:
            草稿ID，如果不存在返回None
        """
        index_data = self._load_index()
        track_info = index_data["track_mappings"].get(track_id)
        return track_info.get("draft_id") if track_info else None
    
    def get_draft_id_by_video_segment_id(self, video_segment_id: str) -> Optional[str]:
        """
        通过视频片段ID获取草稿ID
        
        Args:
            video_segment_id: 视频片段ID
            
        Returns:
            草稿ID，如果不存在返回None
        """
        index_data = self._load_index()
        segment_info = index_data["video_segment_mappings"].get(video_segment_id)
        return segment_info.get("draft_id") if segment_info else None
    
    def get_track_id_by_video_segment_id(self, video_segment_id: str) -> Optional[str]:
        """
        通过视频片段ID获取轨道ID
        
        Args:
            video_segment_id: 视频片段ID
            
        Returns:
            轨道ID，如果不存在返回None
        """
        index_data = self._load_index()
        segment_info = index_data["video_segment_mappings"].get(video_segment_id)
        return segment_info.get("track_id") if segment_info else None
    
    def get_track_name_by_track_id(self, track_id: str) -> Optional[str]:
        """
        通过轨道ID获取轨道名
        
        Args:
            track_id: 轨道ID
            
        Returns:
            轨道名，如果不存在返回None
        """
        index_data = self._load_index()
        track_info = index_data["track_mappings"].get(track_id)
        return track_info.get("track_name") if track_info else None
    
    def get_track_info_by_video_segment_id(self, video_segment_id: str) -> Optional[Dict[str, Any]]:
        """
        通过视频片段ID获取完整轨道信息
        
        Args:
            video_segment_id: 视频片段ID
            
        Returns:
            轨道信息字典，如果不存在返回None
        """
        track_id = self.get_track_id_by_video_segment_id(video_segment_id)
        if track_id:
            index_data = self._load_index()
            return index_data["track_mappings"].get(track_id)
        return None
    
    def get_track_info_by_track_id(self, track_id: str) -> Optional[Dict[str, Any]]:
        """
        通过轨道ID获取完整轨道信息

        Args:
            track_id: 轨道ID

        Returns:
            轨道信息字典，如果不存在返回None
        """
        index_data = self._load_index()
        return index_data["track_mappings"].get(track_id)

    def get_track_id_by_draft_and_name(self, draft_id: str, track_name: str) -> Optional[str]:
        """通过草稿 ID 与轨道名查找轨道 ID。"""
        index_data = self._load_index()
        for track_id, info in index_data["track_mappings"].items():
            if info.get("draft_id") == draft_id and info.get("track_name") == track_name:
                return track_id
        return None

    def list_track_ids_by_draft_id(self, draft_id: str) -> Dict[str, str]:
        """返回草稿下 {track_name: track_id} 映射。"""
        index_data = self._load_index()
        result = {}
        for track_id, info in index_data["track_mappings"].items():
            if info.get("draft_id") == draft_id and info.get("track_name"):
                result[info["track_name"]] = track_id
        return result

    def get_draft_id_by_text_segment_id(self, text_segment_id: str) -> Optional[str]:
        """
        通过文本片段ID获取草稿ID

        Args:
            text_segment_id: 文本片段ID

        Returns:
            草稿ID，如果不存在返回None
        """
        index_data = self._load_index()
        segment_info = index_data["text_segment_mappings"].get(text_segment_id)
        return segment_info.get("draft_id") if segment_info else None

    def get_track_id_by_text_segment_id(self, text_segment_id: str) -> Optional[str]:
        """
        通过文本片段ID获取轨道ID

        Args:
            text_segment_id: 文本片段ID

        Returns:
            轨道ID，如果不存在返回None
        """
        index_data = self._load_index()
        segment_info = index_data["text_segment_mappings"].get(text_segment_id)
        return segment_info.get("track_id") if segment_info else None

    def get_track_info_by_text_segment_id(self, text_segment_id: str) -> Optional[Dict[str, Any]]:
        """
        通过文本片段ID获取完整轨道信息

        Args:
            text_segment_id: 文本片段ID

        Returns:
            轨道信息字典，如果不存在返回None
        """
        track_id = self.get_track_id_by_text_segment_id(text_segment_id)
        if track_id:
            index_data = self._load_index()
            return index_data["track_mappings"].get(track_id)
        return None

    def get_draft_id_by_audio_segment_id(self, audio_segment_id: str) -> Optional[str]:
        """
        通过音频片段ID获取草稿ID

        Args:
            audio_segment_id: 音频片段ID

        Returns:
            草稿ID，如果不存在返回None
        """
        index_data = self._load_index()
        segment_info = index_data["audio_segment_mappings"].get(audio_segment_id)
        return segment_info.get("draft_id") if segment_info else None

    def get_track_id_by_audio_segment_id(self, audio_segment_id: str) -> Optional[str]:
        """
        通过音频片段ID获取轨道ID

        Args:
            audio_segment_id: 音频片段ID

        Returns:
            轨道ID，如果不存在返回None
        """
        index_data = self._load_index()
        segment_info = index_data["audio_segment_mappings"].get(audio_segment_id)
        return segment_info.get("track_id") if segment_info else None

    def get_track_info_by_audio_segment_id(self, audio_segment_id: str) -> Optional[Dict[str, Any]]:
        """
        通过音频片段ID获取完整轨道信息

        Args:
            audio_segment_id: 音频片段ID

        Returns:
            轨道信息字典，如果不存在返回None
        """
        track_id = self.get_track_id_by_audio_segment_id(audio_segment_id)
        if track_id:
            index_data = self._load_index()
            return index_data["track_mappings"].get(track_id)
        return None
    
    # ==================== 工具方法 ====================

    def generate_id(self) -> str:
        """生成新的UUID"""
        return str(uuid.uuid4())


# 全局索引管理器实例
index_manager = IndexManager()
