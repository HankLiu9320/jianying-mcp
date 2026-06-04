# -*- coding: utf-8 -*-
"""
素材验证器
负责验证素材路径/URL和时长
"""
import os
import requests
import shutil
from urllib.parse import urlparse
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv
from jianyingdraft.utils.media_parser import get_media_duration
from jianyingdraft.utils.time_format import (
    DURATION_TOLERANCE_MS,
    clamp_timerange_dict_to_max_duration,
    duration_ms_from_timerange_dict,
    format_error_duration_exceeded,
    format_ms_as_seconds_str,
    parse_time_to_ms,
)

# 加载环境变量
load_dotenv()

# 获取环境变量
SAVE_PATH = os.getenv('SAVE_PATH')


class MaterialValidator:
    """素材验证器"""

    # 支持的媒体格式
    SUPPORTED_AUDIO_FORMATS = {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg', '.wma'}
    SUPPORTED_VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}
    SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    # 视频轨道片段：视频 + 图片（如 png）
    SUPPORTED_VISUAL_FORMATS = SUPPORTED_VIDEO_FORMATS | SUPPORTED_IMAGE_FORMATS

    def __init__(self, draft_id: str = None):
        self.draft_id = draft_id
    
    def validate_material_path(self, material_path: str, expected_type: str = None) -> None:
        """
        验证素材路径或URL
        
        Args:
            material_path: 素材路径或URL
            expected_type: 期望的素材类型 ("audio", "video", "image", "visual")
            
        Raises:
            FileNotFoundError: 本地文件不存在
            ValueError: URL无法访问或格式不支持
        """
        if self._is_url(material_path):
            self._validate_url(material_path, expected_type)
        else:
            self._validate_local_file(material_path, expected_type)
    
    def validate_source_timerange(self, material_path: str, source_timerange: Dict[str, str]) -> None:
        """
        验证源时间范围不超过素材实际时长
        
        Args:
            material_path: 素材路径
            source_timerange: 源时间范围 {"start": "0s", "duration": "5s"}
            
        Raises:
            ValueError: 时间范围超出素材时长
        """
        duration = get_media_duration(material_path)
        if duration is None:
            return

        max_duration_ms = int(round(duration * 1000))
        requested_ms = duration_ms_from_timerange_dict(source_timerange)

        if requested_ms <= max_duration_ms:
            return

        if clamp_timerange_dict_to_max_duration(source_timerange, max_duration_ms):
            return

        if requested_ms <= max_duration_ms + DURATION_TOLERANCE_MS:
            source_timerange["duration"] = format_ms_as_seconds_str(max_duration_ms)
            return

        raise ValueError(
            format_error_duration_exceeded(requested_ms, max_duration_ms, material_path)
        )

    def download_and_localize_material(self, material_path: str, expected_type: str = None) -> str:
        """
        下载网络素材或复制本地素材到material文件夹进行统一管理

        Args:
            material_path: 素材路径或URL
            expected_type: 期望的素材类型

        Returns:
            str: 本地化后的相对路径

        Raises:
            ValueError: 下载失败或验证失败
        """
        if not self.draft_id:
            raise ValueError("素材本地化需要指定草稿ID")

        from jianyingdraft.utils.global_cache import GlobalBatchCache
        cached_path = GlobalBatchCache.get_copied_material(self.draft_id, material_path)
        if cached_path:
            return self._get_relative_path(cached_path)

        if self._is_url(material_path):
            # 网络素材：下载到本地
            local_path = self._download_url_to_local(material_path, expected_type)
        else:
            # 本地素材：复制到material文件夹
            local_path = self._copy_local_to_material(material_path, expected_type)

        from jianyingdraft.utils.global_cache import GlobalBatchCache as _GBC

        if not _GBC.is_active():
            self.validate_material_path(local_path, expected_type)

        GlobalBatchCache.set_copied_material(self.draft_id, material_path, local_path)
        # 返回相对路径
        return self._get_relative_path(local_path)

    def _download_url_to_local(self, url: str, expected_type: str = None) -> str:
        """
        下载URL到本地素材文件夹

        Args:
            url: 网络URL
            expected_type: 期望的素材类型

        Returns:
            str: 本地文件的绝对路径
        """
        try:
            # 创建素材文件夹
            material_dir = self._get_material_dir()
            os.makedirs(material_dir, exist_ok=True)

            # 获取文件名
            filename = self._extract_filename_from_url(url)

            # 处理重名文件
            local_path = self._get_unique_filename(material_dir, filename)

            # 下载文件
            print(f"正在下载素材: {url}")
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"素材下载完成: {local_path}")
            return local_path

        except Exception as e:
            raise ValueError(f"下载素材失败: {url} ({str(e)})")

    def _copy_local_to_material(self, local_path: str, expected_type: str = None) -> str:
        """
        复制本地文件到material文件夹

        Args:
            local_path: 本地文件路径
            expected_type: 期望的素材类型

        Returns:
            str: material文件夹中的文件绝对路径
        """
        try:
            local_path = os.path.abspath(local_path)
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"源文件不存在: {local_path}")

            material_dir = os.path.abspath(self._get_material_dir())
            os.makedirs(material_dir, exist_ok=True)

            # 源文件已在 material 目录内，无需复制
            if local_path == material_dir or local_path.startswith(material_dir + os.sep):
                return local_path

            filename = os.path.basename(local_path)
            base_path = os.path.join(material_dir, filename)
            if os.path.exists(base_path) and os.path.getsize(local_path) == os.path.getsize(base_path):
                return base_path

            target_path = self._get_unique_filename(material_dir, filename)

            # 同盘优先硬链接，避免批量时重复拷贝大文件
            try:
                if os.stat(local_path).st_dev == os.stat(material_dir).st_dev:
                    os.link(local_path, target_path)
                    return target_path
            except OSError:
                pass

            shutil.copy2(local_path, target_path)
            return target_path

        except Exception as e:
            raise ValueError(f"复制本地素材失败: {local_path} ({str(e)})")

    def _get_material_dir(self) -> str:
        """获取素材文件夹路径"""
        return os.path.join(SAVE_PATH, self.draft_id, "material")

    def _extract_filename_from_url(self, url: str) -> str:
        """从URL提取文件名"""
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)

        if not filename or '.' not in filename:
            # 如果无法从URL获取文件名，使用默认名称
            filename = f"material_{hash(url) % 10000}.tmp"

        return filename

    def _get_unique_filename(self, directory: str, filename: str) -> str:
        """
        获取唯一的文件名，避免重名

        Args:
            directory: 目标目录
            filename: 原始文件名

        Returns:
            str: 唯一的文件路径
        """
        base_path = os.path.join(directory, filename)

        if not os.path.exists(base_path):
            return base_path

        # 文件已存在，添加序号后缀
        name, ext = os.path.splitext(filename)
        counter = 1

        while True:
            new_filename = f"{name}_{counter}{ext}"
            new_path = os.path.join(directory, new_filename)

            if not os.path.exists(new_path):
                return new_path

            counter += 1

            if counter > 1000:  # 防止无限循环
                raise ValueError(f"无法创建唯一文件名: {filename}")

    def _get_relative_path(self, absolute_path: str) -> str:
        """
        将绝对路径转换为相对路径

        Args:
            absolute_path: 绝对路径

        Returns:
            str: 相对路径（相对于草稿目录）
        """
        draft_dir = os.path.join(SAVE_PATH, self.draft_id)

        try:
            # 获取相对路径
            rel_path = os.path.relpath(absolute_path, draft_dir)
            # 统一使用正斜杠，确保跨平台兼容性
            return rel_path.replace(os.sep, '/')
        except ValueError:
            # 如果无法计算相对路径，返回文件名
            return f"material/{os.path.basename(absolute_path)}"
    
    def _is_url(self, path: str) -> bool:
        """判断是否为URL"""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _validate_url(self, url: str, expected_type: str = None) -> None:
        """验证URL可访问性和格式"""
        try:
            # 发送HEAD请求检查URL可访问性
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code >= 400:
                raise ValueError(f"URL无法访问: {url} (状态码: {response.status_code})")
            
            # 检查文件格式
            if expected_type:
                self._validate_format_from_url(url, expected_type)
                
        except requests.RequestException as e:
            raise ValueError(f"URL验证失败: {url} ({str(e)})")
    
    def _validate_local_file(self, file_path: str, expected_type: str = None) -> None:
        """验证本地文件存在性和格式"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"素材文件不存在: {file_path}")
        
        if not os.path.isfile(file_path):
            raise ValueError(f"路径不是文件: {file_path}")
        
        # 检查文件格式
        if expected_type:
            self._validate_format_from_path(file_path, expected_type)
    
    def _validate_format_from_path(self, file_path: str, expected_type: str) -> None:
        """从文件路径验证格式"""
        ext = os.path.splitext(file_path)[1].lower()
        self._check_format_support(ext, expected_type, file_path)
    
    def _validate_format_from_url(self, url: str, expected_type: str) -> None:
        """从URL验证格式"""
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1].lower()
        if ext:  # 如果URL包含文件扩展名
            self._check_format_support(ext, expected_type, url)
    
    def _check_format_support(self, ext: str, expected_type: str, source: str) -> None:
        """检查格式是否支持"""
        if expected_type == "audio" and ext not in self.SUPPORTED_AUDIO_FORMATS:
            raise ValueError(f"不支持的音频格式 {ext}: {source}")
        elif expected_type == "video" and ext not in self.SUPPORTED_VIDEO_FORMATS:
            raise ValueError(f"不支持的视频格式 {ext}: {source}")
        elif expected_type == "image" and ext not in self.SUPPORTED_IMAGE_FORMATS:
            raise ValueError(f"不支持的图片格式 {ext}: {source}")
        elif expected_type == "visual" and ext not in self.SUPPORTED_VISUAL_FORMATS:
            raise ValueError(f"不支持的视频/图片格式 {ext}: {source}")
    

    
# 便捷函数
def validate_material(material_path: str, material_type: str = None,
                     source_timerange: Dict[str, str] = None) -> None:
    """
    便捷的素材验证函数

    Args:
        material_path: 素材路径或URL
        material_type: 素材类型 ("audio", "video", "image", "visual")
        source_timerange: 源时间范围（可选）
    """
    validator = MaterialValidator()

    # 验证路径/URL和格式
    validator.validate_material_path(material_path, material_type)

    # 验证时长（如果提供了源时间范围）
    if source_timerange and material_type in ["audio", "video"]:
        validator.validate_source_timerange(material_path, source_timerange)


def download_and_validate_material(draft_id: str, material_path: str, material_type: str = None,
                                  target_timerange: Dict[str, str] = None) -> str:
    """
    下载并验证素材的便捷函数

    Args:
        draft_id: 草稿ID
        material_path: 素材路径或URL
        material_type: 素材类型 ("audio", "video", "image", "visual")
        target_timerange: 源时间范围

    Returns:
        str: 本地化后的相对路径
    """
    validator = MaterialValidator(draft_id)

    # 下载并本地化素材
    local_path = validator.download_and_localize_material(material_path, material_type)

    # 验证时长：用原始路径查缓存（复制前后时长相同，避免对 material 副本再跑 MediaInfo）
    if target_timerange and material_type in ("audio", "video", "visual"):
        ext = os.path.splitext(material_path)[1].lower()
        should_check_duration = material_type in ("audio", "video") or (
            material_type == "visual" and ext in MaterialValidator.SUPPORTED_VIDEO_FORMATS
        )
        if should_check_duration:
            validator.validate_source_timerange(material_path, target_timerange)
            from jianyingdraft.utils import global_cache as gc
            duration = gc.GlobalBatchCache.get_media_duration(material_path)
            abs_local = local_path if os.path.isabs(local_path) else os.path.join(SAVE_PATH, draft_id, local_path)
            gc.GlobalBatchCache.set_media_duration(abs_local, duration)

    return local_path


