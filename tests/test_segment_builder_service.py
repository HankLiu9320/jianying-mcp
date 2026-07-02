# -*- coding: utf-8 -*-
import json
import unittest
from pathlib import Path

from jianyingdraft.services.segment_builder_service import (
    SubtitleLine,
    align_subtitles_with_asr,
    group_subtitles_by_sentence,
)


def _item(fname: str, display: str, tts: str = "", skip_tts: bool = False):
    return (fname, display, tts, 0.0, 0.0, skip_tts)


class GroupSubtitlesTest(unittest.TestCase):
  def test_s00_groups_skip_tts_into_same_sentence(self):
    items = [
      _item("S00_L01", "你以为社保", "你以为社保，就是每月被扣的那笔钱。"),
      _item("S00_L02", "就是每月被扣的钱", skip_tts=True),
      _item("S00_L03", "其实是五个账户", "其实，那是五个账户，在悄悄给你存保障。"),
      _item("S00_L04", "在悄悄存保障", skip_tts=True),
    ]
    groups = group_subtitles_by_sentence(items)
    self.assertEqual(len(groups), 2)
    self.assertEqual(groups[0].audio_name, "S00_sent00.mp3")
    self.assertEqual([line.display for line in groups[0].lines], [
      "你以为社保",
      "就是每月被扣的钱",
    ])
    self.assertEqual(groups[1].audio_name, "S00_sent01.mp3")
    self.assertEqual([line.display for line in groups[1].lines], [
      "其实是五个账户",
      "在悄悄存保障",
    ])
    self.assertNotIn("在悄悄存保障", groups[0].tts_text)

  def test_no_display_fallback_tts(self):
    tts_texts = {group.tts_text for group in group_subtitles_by_sentence([
      _item("S00_L01", "你以为社保", "你以为社保，就是每月被扣的那笔钱。"),
      _item("S00_L02", "就是每月被扣的钱", skip_tts=True),
      _item("S00_L03", "其实是五个账户", "其实，那是五个账户，在悄悄给你存保障。"),
      _item("S00_L04", "在悄悄存保障", skip_tts=True),
    ])}
    self.assertNotIn("在悄悄存保障", tts_texts)

  def test_orphan_skip_tts_raises(self):
    with self.assertRaises(ValueError):
      group_subtitles_by_sentence([
        _item("S00_L02", "就是每月被扣的钱", skip_tts=True),
      ])


class WordAlignTest(unittest.TestCase):
  def test_word_align_s00_sent00(self):
    cache = Path("/Users/liujianjia/2_tools/jianying/aidata/social-insurance-basics/_asr_cache/S00_sent00.json")
    if not cache.exists():
      self.skipTest("ASR cache not available")
    utterances = json.loads(cache.read_text(encoding="utf-8"))["utterances"]
    lines = [
      SubtitleLine(display="你以为社保"),
      SubtitleLine(display="就是每月被扣的钱"),
    ]
    timings = align_subtitles_with_asr(lines, utterances, audio_duration=3.0, offset=0.0)
    self.assertEqual(len(timings), 2)
    self.assertLess(timings[0][0], timings[0][1])
    self.assertLessEqual(timings[0][1], timings[1][0] + 0.05)
    self.assertGreater(timings[1][1], timings[1][0])

  def test_word_align_subsequence_skips_middle_asr(self):
    utterances = [{
      "text": "一个人扛不起的大病养老失业大家凑钱一起扛",
      "start_time": 0,
      "end_time": 5000,
      "words": [
        {"text": "一个", "start_time": 100, "end_time": 400},
        {"text": "人", "start_time": 400, "end_time": 600},
        {"text": "扛", "start_time": 600, "end_time": 900},
        {"text": "不起", "start_time": 900, "end_time": 1200},
        {"text": "的", "start_time": 1200, "end_time": 1300},
        {"text": "大病", "start_time": 1300, "end_time": 1900},
        {"text": "养老", "start_time": 2000, "end_time": 2500},
        {"text": "失业", "start_time": 2500, "end_time": 3000},
        {"text": "大家", "start_time": 3100, "end_time": 3500},
        {"text": "凑钱", "start_time": 3500, "end_time": 3900},
        {"text": "一起", "start_time": 3900, "end_time": 4300},
        {"text": "扛", "start_time": 4300, "end_time": 4700},
      ],
    }]
    lines = [
      SubtitleLine(display="一个人扛不起"),
      SubtitleLine(display="大家凑钱一起扛"),
    ]
    timings = align_subtitles_with_asr(lines, utterances, audio_duration=5.0, offset=10.0)
    self.assertEqual(len(timings), 2)
    self.assertAlmostEqual(timings[0][0], 10.0, places=1)
    self.assertAlmostEqual(timings[-1][1], 15.0, places=1)
    self.assertLessEqual(timings[0][1], timings[1][0] + 0.001)
    self.assertGreater(timings[1][1], timings[1][0])


class SocialInsuranceRegressionTest(unittest.TestCase):
  def test_subtitle_items_produce_94_groups_not_126(self):
    items_path = Path("/Users/liujianjia/2_tools/jianying/aidata/social-insurance-basics/subtitle_items.json")
    if not items_path.exists():
      self.skipTest("subtitle_items not available")
    raw = json.loads(items_path.read_text(encoding="utf-8"))
    tuples = [
      (
        str(item.get("filename") or ""),
        str(item.get("display") or ""),
        str(item.get("tts_text") or ""),
        0.0,
        0.0,
        bool(item.get("skip_tts", False)),
      )
      for item in raw
    ]
    groups = group_subtitles_by_sentence(tuples)
    self.assertEqual(len(groups), 94)
    fallback = [g for g in groups if g.tts_text == g.lines[-1].display]
    self.assertEqual(fallback, [])


if __name__ == "__main__":
  unittest.main()
