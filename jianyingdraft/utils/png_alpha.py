# -*- coding: utf-8 -*-
"""PNG alpha 紧裁切与满画幅校验。"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple

from PIL import Image


@dataclass
class MarginMetrics:
    left: float
    right: float
    top: float
    bottom: float
    fill_ratio: float
    bbox: Tuple[int, int, int, int]
    width: int
    height: int

    @property
    def max_margin(self) -> float:
        return max(self.left, self.right, self.top, self.bottom)

    def axis_margins_ok(self, max_margin_ratio: float) -> bool:
        """至少一个轴向（左+右 或 上+下）贴边，允许另一轴向居中留白。"""
        horizontal_ok = self.left <= max_margin_ratio and self.right <= max_margin_ratio
        vertical_ok = self.top <= max_margin_ratio and self.bottom <= max_margin_ratio
        return horizontal_ok or vertical_ok

    def tight_fill_ok(self, max_margin_ratio: float) -> bool:
        """内容贴满输出画布（紧裁切后四边均贴边）。"""
        return self.max_margin <= max_margin_ratio

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "max_margin": self.max_margin,
        }


def _ensure_rgba(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        return image
    return image.convert("RGBA")


def compute_alpha_bbox(
    image: Image.Image,
    alpha_threshold: int = 128,
) -> Optional[Tuple[int, int, int, int]]:
    """返回 (left, upper, right, lower)，PIL crop 格式；无有效像素时 None。"""
    rgba = _ensure_rgba(image)
    alpha = rgba.getchannel("A")
    mask = alpha.point(lambda p: 255 if p >= alpha_threshold else 0)
    return mask.getbbox()


def measure_margins(
    image: Image.Image,
    alpha_threshold: int = 128,
) -> MarginMetrics:
    rgba = _ensure_rgba(image)
    width, height = rgba.size
    bbox = compute_alpha_bbox(rgba, alpha_threshold)
    if bbox is None:
        return MarginMetrics(
            left=1.0,
            right=1.0,
            top=1.0,
            bottom=1.0,
            fill_ratio=0.0,
            bbox=(0, 0, 0, 0),
            width=width,
            height=height,
        )

    x0, y0, x1, y1 = bbox
    content_w = max(x1 - x0, 1)
    content_h = max(y1 - y0, 1)
    return MarginMetrics(
        left=x0 / width,
        right=(width - x1) / width,
        top=y0 / height,
        bottom=(height - y1) / height,
        fill_ratio=(content_w * content_h) / (width * height),
        bbox=bbox,
        width=width,
        height=height,
    )


def _aspect_ratio(width: int, height: int) -> float:
    if height <= 0:
        return 1.0
    return width / height


def _compute_output_size(
    crop_w: int,
    crop_h: int,
    source_w: int,
    source_h: int,
    target_width: Optional[int],
    target_height: Optional[int],
) -> Tuple[int, int]:
    """
    在保持裁切内容宽高比不变的前提下，计算输出尺寸（仅等比缩放，禁止拉伸）。

    - 未指定 target：输出为裁切后原始像素尺寸
    - 仅指定一边：另一边按比例推导
    - 同时指定 target_w/h：在框内 contain 缩放，输出为缩放后紧贴内容的尺寸（不铺到固定方形画布）
    """
    crop_ar = _aspect_ratio(crop_w, crop_h)

    if target_width is None and target_height is None:
        return crop_w, crop_h

    if target_width is not None and target_height is None:
        new_w = max(1, target_width)
        new_h = max(1, int(round(new_w / crop_ar)))
        return new_w, new_h

    if target_height is not None and target_width is None:
        new_h = max(1, target_height)
        new_w = max(1, int(round(new_h * crop_ar)))
        return new_w, new_h

    tw, th = target_width, target_height
    scale = min(tw / crop_w, th / crop_h)
    new_w = max(1, int(round(crop_w * scale)))
    new_h = max(1, int(round(new_w / crop_ar)))
    return new_w, new_h


def _resize_preserving_aspect(
    cropped: Image.Image,
    output_width: int,
    output_height: int,
) -> Image.Image:
    """等比缩放至 output 尺寸（宽高须已由 _compute_output_size 按同一比例算出）。"""
    crop_w, crop_h = cropped.size
    if crop_w <= 0 or crop_h <= 0:
        raise ValueError("裁切后内容尺寸无效")

    if (output_width, output_height) == (crop_w, crop_h):
        return cropped.copy()

    return cropped.resize((output_width, output_height), Image.Resampling.LANCZOS)


def _check_alpha_quality(
    image: Image.Image,
    margins: MarginMetrics,
    alpha_threshold: int = 10,
) -> bool:
    """紧贴满画幅时四角可为内容像素；有留白时要求四角近乎透明。"""
    if margins.tight_fill_ok(0.01):
        return True
    rgba = _ensure_rgba(image)
    alpha = rgba.getchannel("A")
    w, h = rgba.size
    points = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    transparent_count = sum(1 for x, y in points if alpha.getpixel((x, y)) < alpha_threshold)
    return transparent_count >= 3


@dataclass
class TrimPngAlphaResult:
    input_path: str
    output_path: str
    source_size: Tuple[int, int]
    cropped_size: Tuple[int, int]
    output_size: Tuple[int, int]
    source_aspect_ratio: float
    cropped_aspect_ratio: float
    output_aspect_ratio: float
    aspect_ratio_preserved: bool
    bbox_before: Optional[Tuple[int, int, int, int]]
    margins_before: Dict[str, Any]
    margins_after: Dict[str, Any]
    margin_ok: bool
    alpha_corners_ok: bool
    written: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def trim_png_alpha(
    input_path: str,
    output_path: Optional[str] = None,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
    alpha_threshold: int = 128,
    max_margin_ratio: float = 0.02,
    validate_only: bool = False,
) -> TrimPngAlphaResult:
    """
    按 alpha 包围盒裁切 PNG，**保持内容原有宽高比**等比缩放输出（禁止拉伸）。

    默认 output_path=input_path（覆盖原文件）。
    未指定 target 时仅裁切透明边，输出尺寸=内容包围盒尺寸。
    指定 target 时在目标框内 contain 缩放，输出尺寸随比例变化（如 512×384），不强制铺到方形画布。
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"PNG 文件不存在: {input_path}")

    ext = os.path.splitext(input_path)[1].lower()
    if ext != ".png":
        raise ValueError(f"仅支持 PNG 文件，当前: {input_path}")

    out_path = output_path or input_path
    if not validate_only:
        out_dir = os.path.dirname(os.path.abspath(out_path))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

    with Image.open(input_path) as img:
        rgba = _ensure_rgba(img)
        source_size = rgba.size
        source_ar = _aspect_ratio(*source_size)
        margins_before = measure_margins(rgba, alpha_threshold)
        bbox = compute_alpha_bbox(rgba, alpha_threshold)
        if bbox is None:
            raise ValueError(f"PNG 无有效 alpha 主体（阈值 {alpha_threshold}）: {input_path}")

        cropped = rgba.crop(bbox)
        cropped_size = cropped.size
        cropped_ar = _aspect_ratio(*cropped_size)

        out_w, out_h = _compute_output_size(
            cropped_size[0],
            cropped_size[1],
            source_size[0],
            source_size[1],
            target_width,
            target_height,
        )
        output_ar = _aspect_ratio(out_w, out_h)

        # 允许 1px 舍入误差
        aspect_ratio_preserved = abs(output_ar - cropped_ar) <= max(0.02, cropped_ar * 0.002)

        result_img = _resize_preserving_aspect(cropped, out_w, out_h)
        margins_after_obj = measure_margins(result_img, alpha_threshold)
        margin_ok = margins_after_obj.tight_fill_ok(max_margin_ratio) or margins_after_obj.axis_margins_ok(
            max_margin_ratio
        )
        alpha_corners_ok = _check_alpha_quality(result_img, margins_after_obj)

        written = False
        if not validate_only:
            result_img.save(out_path, format="PNG")
            written = True

    return TrimPngAlphaResult(
        input_path=os.path.abspath(input_path),
        output_path=os.path.abspath(out_path),
        source_size=source_size,
        cropped_size=cropped_size,
        output_size=(out_w, out_h),
        source_aspect_ratio=round(source_ar, 6),
        cropped_aspect_ratio=round(cropped_ar, 6),
        output_aspect_ratio=round(output_ar, 6),
        aspect_ratio_preserved=aspect_ratio_preserved,
        bbox_before=bbox,
        margins_before=margins_before.to_dict(),
        margins_after=margins_after_obj.to_dict(),
        margin_ok=margin_ok,
        alpha_corners_ok=alpha_corners_ok,
        written=written,
    )
