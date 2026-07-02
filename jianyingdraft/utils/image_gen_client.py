# -*- coding: utf-8 -*-
"""LLM Gateway 图片生成 API 客户端"""
import base64
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "http://llm-gw.jd.local/v1"
DEFAULT_MODEL = "GPT-image-2-joybuilder"


def _get_api_key() -> str:
    key = os.getenv("LLM_GW_API_KEY", "").strip()
    if not key:
        raise ValueError("未配置 LLM_GW_API_KEY 环境变量")
    return key


def _get_base_url() -> str:
    return os.getenv("LLM_GW_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _default_output_dir() -> Path:
    save_path = os.getenv("SAVE_PATH", "").strip()
    if save_path:
        return Path(save_path) / "generated_images"
    return Path.cwd() / "generated_images"


def generate_image(
    prompt: str,
    model: Optional[str] = None,
    output_path: Optional[str] = None,
    reference_image_path: Optional[str] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    调用 LLM Gateway 图片生成接口，将图片保存到本地并返回路径信息。

    Returns:
        dict: prompt, model, image_paths, created 等
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt 不能为空")

    model = (model or os.getenv("LLM_GW_IMAGE_MODEL", DEFAULT_MODEL)).strip()
    url = f"{_get_base_url()}/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_get_api_key()}",
    }
    payload: Dict[str, Any] = {"model": model, "prompt": prompt.strip()}
    if reference_image_path:
        ref_path = Path(reference_image_path)
        if not ref_path.is_file():
            raise ValueError(f"参考图片不存在: {reference_image_path}")
        payload["image"] = base64.b64encode(ref_path.read_bytes()).decode("ascii")

    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    result = response.json()

    image_paths = _save_images(result.get("data") or [], output_path)
    return {
        "prompt": prompt.strip(),
        "model": model,
        "reference_image_path": reference_image_path,
        "created": result.get("created"),
        "image_paths": image_paths,
        "count": len(image_paths),
    }


def _save_images(
    data: List[Dict[str, Any]],
    output_path: Optional[str],
) -> List[str]:
    if not data:
        raise ValueError("API 未返回图片数据")

    saved: List[str] = []
    for index, item in enumerate(data):
        path = _resolve_output_path(output_path, index, len(data))
        path.parent.mkdir(parents=True, exist_ok=True)

        if item.get("b64_json"):
            image_bytes = base64.b64decode(item["b64_json"])
            path.write_bytes(image_bytes)
        elif item.get("url"):
            img_resp = requests.get(item["url"], timeout=60)
            img_resp.raise_for_status()
            path.write_bytes(img_resp.content)
        else:
            raise ValueError("API 返回的图片项缺少 b64_json 或 url 字段")

        saved.append(str(path.resolve()))
    return saved


def _resolve_output_path(
    output_path: Optional[str],
    index: int,
    total: int,
) -> Path:
    if output_path:
        path = Path(output_path)
        if total > 1 and path.suffix:
            path = path.with_stem(f"{path.stem}_{index + 1}")
        elif total > 1:
            path = path / f"image_{index + 1}.png"
        elif not path.suffix:
            path = path / "image.png"
        return path

    out_dir = _default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"gen_{int(time.time())}_{index + 1}.png"
    return out_dir / filename
