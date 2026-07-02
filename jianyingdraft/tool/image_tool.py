# -*- coding: utf-8 -*-
"""图片生成 MCP 工具"""
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP

from jianyingdraft.utils.response import ToolResponse


def image_tools(mcp: FastMCP):
    @mcp.tool()
    def generate_image(
        prompt: str,
        model: Optional[str] = None,
        output_path: Optional[str] = None,
        reference_image_path: Optional[str] = None,
    ) -> ToolResponse:
        """
        通过 LLM Gateway 根据文本提示词生成图片，并保存到本地文件。

        Args:
            prompt: 图片描述提示词，例如 "A photograph of a red fox in an autumn forest"
            model: 图片生成模型，默认 GPT-image-2-joybuilder
            output_path: 输出图片路径（绝对路径）；省略时保存到 SAVE_PATH/generated_images/ 或当前目录下 generated_images/
            reference_image_path: 参考图片绝对路径，用于风格/角色参考生成

        Returns:
            ToolResponse: 包含 image_paths、model、prompt 等信息
        """
        try:
            from jianyingdraft.utils.image_gen_client import generate_image as gen_image

            result = gen_image(
                prompt=prompt,
                model=model,
                output_path=output_path,
                reference_image_path=reference_image_path,
            )
            paths = result.get("image_paths") or []
            return ToolResponse(
                success=True,
                message=f"成功生成 {len(paths)} 张图片",
                data=result,
            )
        except ValueError as e:
            return ToolResponse(success=False, message=str(e))
        except requests.HTTPError as e:
            detail = ""
            if e.response is not None:
                try:
                    detail = e.response.text[:500]
                except Exception:
                    pass
            return ToolResponse(
                success=False,
                message=f"图片生成 API 请求失败: {e}; {detail}".strip(),
            )
        except requests.RequestException as e:
            return ToolResponse(
                success=False,
                message=f"图片生成网络请求失败: {e}",
            )
        except Exception as e:
            return ToolResponse(
                success=False,
                message=f"图片生成失败: {e}",
            )
