#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 02-分镜脚本.md 构建 gushi-shichang-shime 剪映草稿。

注意：分镜制作应优先使用 MCP 批量工具（batch_create_tracks / batch_add_segments），
避免逐条 add_*_segment 导致往返过慢。本脚本仅作本地调试或 CI 参考。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from jianyingdraft.jianying.audio import AudioSegment
from jianyingdraft.jianying.text import TextSegment
from jianyingdraft.jianying.video import VideoSegment
from jianyingdraft.jianying.export import ExportDraft
from jianyingdraft.utils.media_parser import get_media_duration

AID = "/Users/liujianjia/2_tools/jianying/aidata/gushi-shichang-shime"
MAT = os.path.join(ROOT, "material")
DRAFT_ID = os.environ.get("DRAFT_ID", "")
DRAFT_NAME = "gushi-shichang-shime"

AUDIO_ITEMS = [
    ("S01_L01.mp3", "股市是什么？"),
    ("S02_L01.mp3", "用最白话说："),
    ("S02_L02.mp3", "股市就是一个很大的「买卖公司所有权」的地方。"),
    ("S03_L01.mp3", "比如有一家做手机、做人工智能的公司，"),
    ("S03_L02.mp3", "你觉得它十年后特别能赚钱，"),
    ("S04_L01.mp3", "你就可以花钱买它的一小部分——"),
    ("S04_L02.mp3", "这就叫股票。"),
    ("S05_L01.mp3", "买的人多了，大家都看好它，"),
    ("S05_L02.mp3", "它的价格就会被抬高；"),
    ("S06_L01.mp3", "买的人少了，或者大家突然不看好它了，"),
    ("S06_L02.mp3", "价格就会掉下来。"),
    ("S07_L01.mp3", "所以，股市反映的往往不是「今天公司柜台上收了多少钱」，"),
    ("S08_L01.mp3", "而是千千万万人在猜："),
    ("S08_L02.mp3", "「我觉得它未来能赚多少。」"),
]

SUB_STYLE = {"size": 8.0, "bold": True, "color": (0.1, 0.1, 0.2), "align": 1}
SUB_CLIP = {"transform_y": -0.85}


def aid(name: str) -> str:
    return os.path.join(AID, name)


def aud(name: str) -> str:
    return os.path.join(MAT, name)


def tr(start: float, end: float) -> str:
    dur = max(0.01, (end - start) - 0.001)
    return f"{start}s-{dur}s"


def main():
    if not DRAFT_ID:
        from jianyingdraft.jianying.draft import Draft
        from jianyingdraft.jianying.track import Track

        draft = Draft()
        result = draft.create_draft(draft_name=DRAFT_NAME)
        draft_id = result["draft_id"]
        for name in (
            "video_bg",
            "video_layer1",
            "video_layer2",
            "video_layer3",
            "video_overlay",
            "video_overlay_b",
            "video_overlay_c",
            "audio_narration",
            "text_subtitle",
        ):
            ttype = "audio" if name == "audio_narration" else "text" if name == "text_subtitle" else "video"
            Track(draft_id).add_track(ttype, name)
    else:
        draft_id = DRAFT_ID

    print("draft_id:", draft_id)

    vbg = VideoSegment(draft_id, track_name="video_bg")
    v1 = VideoSegment(draft_id, track_name="video_layer1")
    v2 = VideoSegment(draft_id, track_name="video_layer2")
    v3 = VideoSegment(draft_id, track_name="video_layer3")
    vo = VideoSegment(draft_id, track_name="video_overlay")
    vob = VideoSegment(draft_id, track_name="video_overlay_b")
    voc = VideoSegment(draft_id, track_name="video_overlay_c")
    au = AudioSegment(draft_id, track_name="audio_narration")
    ts = TextSegment(draft_id, track_name="text_subtitle")

    shot_audio_groups = [[0], [1, 2], [3, 4], [5, 6], [7, 8], [9, 10], [11], [12, 13]]
    t_acc = 0.0
    s = []
    for group in shot_audio_groups:
        for idx in group:
            t_acc += get_media_duration(aud(AUDIO_ITEMS[idx][0]))
        s.append(t_acc)

    audio_starts = []
    t = 0.0
    for fname, subtitle in AUDIO_ITEMS:
        dur = get_media_duration(aud(fname))
        audio_starts.append(t)
        au.add_audio_segment(aud(fname), tr(t, t + dur))
        ts.add_text_segment(subtitle, tr(t, t + dur), style=SUB_STYLE, clip_settings=SUB_CLIP)
        t += dur

    # 背景
    vbg.add_video_segment(aid("img_bg_stock_hall.png"), tr(0, s[0]))
    vbg.add_video_segment(aid("img_bg_white.png"), tr(s[0], s[3]))
    vbg.add_video_segment(aid("img_bg_stock_hall.png"), tr(s[3], s[5]))
    vbg.add_video_segment(aid("img_bg_white.png"), tr(s[5], s[6]))
    vbg.add_video_segment(aid("img_bg_stock_hall.png"), tr(s[6], s[7]))

    # 镜头 01
    v1.add_video_segment(
        aid("img_role_narrator_v1.png"), tr(0.3, s[0]),
        clip_settings={"scale_x": 0.85, "scale_y": 0.85, "transform_y": -0.35},
    )
    vo.add_video_segment(
        aid("img_prop_title_question.png"), tr(0.3, s[0]),
        clip_settings={"scale_x": 0.55, "scale_y": 0.55, "transform_y": 0.35},
    )

    # 镜头 02
    v1.add_video_segment(
        aid("img_role_narrator_v1.png"), tr(s[0], s[1]),
        clip_settings={"scale_x": 0.45, "scale_y": 0.45, "transform_x": -0.55, "transform_y": -0.45},
    )
    v2.add_video_segment(
        aid("img_prop_ownership_exchange.png"), tr(audio_starts[2], s[1]),
        clip_settings={"scale_x": 0.5, "scale_y": 0.5, "transform_x": 0.45},
    )
    v3.add_video_segment(
        aid("img_prop_exchange_sign.png"), tr(audio_starts[2], s[1]),
        clip_settings={"scale_x": 0.65, "scale_y": 0.65},
    )

    # 镜头 03
    v1.add_video_segment(
        aid("img_prop_tech_company.png"), tr(s[1], audio_starts[4]),
        clip_settings={"scale_x": 0.5, "scale_y": 0.5, "transform_x": 0.45},
    )
    v2.add_video_segment(
        aid("img_role_thinker_v1.png"), tr(audio_starts[4], s[2]),
        clip_settings={"scale_x": 0.5, "scale_y": 0.5, "transform_x": -0.45},
    )
    vo.add_video_segment(
        aid("img_prop_bubble_future_money.png"), tr(audio_starts[4] + 0.5, s[2]),
        clip_settings={"scale_x": 0.35, "scale_y": 0.35, "transform_x": -0.45, "transform_y": 0.15},
    )

    # 镜头 04
    v1.add_video_segment(
        aid("img_prop_tech_company.png"), tr(s[2], s[3]),
        clip_settings={"scale_x": 0.38, "scale_y": 0.38, "transform_x": 0.5, "transform_y": 0.25},
    )
    v2.add_video_segment(
        aid("img_role_investor_v1.png"), tr(s[2], s[3]),
        clip_settings={"scale_x": 0.42, "scale_y": 0.42, "transform_x": -0.5, "transform_y": -0.4},
    )
    v3.add_video_segment(
        aid("img_prop_stock_slice.png"), tr(audio_starts[5] + 1.0, audio_starts[6]),
        clip_settings={"scale_x": 0.48, "scale_y": 0.48},
    )
    vo.add_video_segment(
        aid("img_prop_label_stock.png"), tr(audio_starts[6], s[3]),
        clip_settings={"scale_x": 0.55, "scale_y": 0.55, "transform_y": 0.3},
    )

    # 镜头 05
    v1.add_video_segment(
        aid("img_prop_stock_slice.png"), tr(s[3], s[4]),
        clip_settings={"scale_x": 0.5, "scale_y": 0.5},
    )
    for seg, tx in ((vo, -0.65), (vob, -0.20), (voc, 0.20), (v2, 0.65)):
        seg.add_video_segment(
            aid("img_role_investor_v1.png"), tr(s[3], audio_starts[8]),
            clip_settings={"scale_x": 0.32, "scale_y": 0.32, "transform_x": tx, "transform_y": -0.35},
        )
    v3.add_video_segment(
        aid("img_prop_price_up.png"), tr(audio_starts[8], s[4]),
        clip_settings={"scale_x": 0.4, "scale_y": 0.4, "transform_x": 0.55, "transform_y": 0.35},
    )

    # 镜头 06
    v1.add_video_segment(
        aid("img_prop_stock_slice.png"), tr(s[4], s[5]),
        clip_settings={"scale_x": 0.55, "scale_y": 0.55},
    )
    v2.add_video_segment(
        aid("img_role_investor_v1.png"), tr(s[4], s[4] + 2.5),
        clip_settings={"scale_x": 0.38, "scale_y": 0.38, "transform_x": -0.55, "transform_y": -0.3},
    )
    vo.add_video_segment(
        aid("img_role_thinker_v1.png"), tr(s[4] + 2.5, s[5]),
        clip_settings={"scale_x": 0.48, "scale_y": 0.48, "transform_x": -0.5},
    )
    v3.add_video_segment(
        aid("img_prop_price_down.png"), tr(audio_starts[10], s[5]),
        clip_settings={"scale_x": 0.4, "scale_y": 0.4, "transform_x": 0.55, "transform_y": 0.35},
    )

    # 镜头 07
    v1.add_video_segment(
        aid("img_role_narrator_v1.png"), tr(s[5], s[6]),
        clip_settings={"scale_x": 0.4, "scale_y": 0.4, "transform_y": -0.42},
    )
    v2.add_video_segment(
        aid("img_prop_cash_today.png"), tr(s[5] + 0.5, s[5] + 3.0),
        clip_settings={"scale_x": 0.42, "scale_y": 0.42, "transform_x": -0.45},
    )
    v3.add_video_segment(
        aid("img_prop_cross_mark_red.png"), tr(s[5] + 2.5, s[6]),
        clip_settings={"scale_x": 0.35, "scale_y": 0.35, "transform_x": -0.45, "transform_y": 0.05},
    )
    vo.add_video_segment(
        aid("img_prop_stock_slice.png"), tr(s[5] + 3.0, s[6]),
        clip_settings={"scale_x": 0.45, "scale_y": 0.45, "transform_x": 0.4},
    )

    # 镜头 08
    v1.add_video_segment(
        aid("img_prop_crowd_guess.png"), tr(s[6], s[7]),
        clip_settings={"scale_x": 0.62, "scale_y": 0.62},
    )
    bubble_positions = [(-0.55, 0.05), (-0.2, 0.08), (0.2, 0.05), (0.55, 0.08)]
    for seg, tx in zip(
        (vo, vob, voc, v2),
        [-0.55, -0.2, 0.2, 0.55],
    ):
        seg.add_video_segment(
            aid("img_role_investor_v1.png"), tr(audio_starts[13], s[7]),
            clip_settings={"scale_x": 0.28, "scale_y": 0.28, "transform_x": tx, "transform_y": -0.15},
        )
    for i, (bx, by) in enumerate(bubble_positions):
        start = audio_starts[13] + 0.3 + i * 0.25
        end = s[7] if i == len(bubble_positions) - 1 else start + 0.24
        v3.add_video_segment(
            aid("img_prop_bubble_future_money.png"), tr(start, end),
            clip_settings={"scale_x": 0.22, "scale_y": 0.22, "transform_x": bx, "transform_y": by},
        )

    ExportDraft().export(draft_id)
    print("导出完成:", DRAFT_NAME, "总时长约", round(s[7], 2), "秒")


if __name__ == "__main__":
    main()
