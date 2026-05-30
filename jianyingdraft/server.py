# -*- coding: utf-8 -*-
"""
Author: jian wei
File Name:server.py
"""
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("JianYingDraft")
# 将当前目录添加到python项目
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from jianyingdraft.tool.draft_tool import draft_tools
from jianyingdraft.tool.track_tool import track_tools
from jianyingdraft.tool.video_tool import video_tools
from jianyingdraft.tool.text_tool import text_tools
from jianyingdraft.tool.audio_tool import audio_tools
from jianyingdraft.tool.utility_tool import utility_tools
from jianyingdraft.tool.batch_tool import batch_tools


def main():
    # 注册所有工具
    draft_tools(mcp)
    track_tools(mcp)
    video_tools(mcp)
    text_tools(mcp)
    audio_tools(mcp)
    utility_tools(mcp)
    batch_tools(mcp)
    mcp.run()


if __name__ == "__main__":
    main()
