"""Near-pronunciation acceptance must not turn other meanings into LED commands."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from commands import classify_sentence, interpret_sentence


class PhoneticCommandTests(unittest.TestCase):
    def test_reported_recognition_error_maps_to_right(self):
        match = interpret_sentence("有并开灯")
        self.assertEqual(match.command, "GREEN_ON")
        self.assertEqual(match.phrase, "右邊開燈")
        self.assertEqual(match.method, "phonetic")

    def test_homophones_and_bounded_side_pronunciation(self):
        cases = {
            "BLUE_ON": ("佐邊開燈", "坐边开灯", "左并开灯", "左並開燈", "左賓開燈", "左变开灯", "左边开登", "佐邊楷燈"),
            "GREEN_ON": ("有并开灯", "又邊開燈", "有邊開燈", "右並開燈", "右賓開燈", "右变开灯", "右边开登", "右邊凱燈"),
        }
        for command, phrases in cases.items():
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    self.assertEqual(classify_sentence(phrase), command)

    def test_polite_single_command_prefixes(self):
        for prefix in ("請", "请", "幫我", "帮我", "請幫我", "请帮我", "麻煩", "麻烦", "麻煩幫我", "麻烦帮我"):
            with self.subTest(prefix=prefix):
                self.assertEqual(classify_sentence(prefix + "有并开灯"), "GREEN_ON")
                self.assertEqual(classify_sentence(prefix + "左邊開燈"), "BLUE_ON")

    def test_negation_and_cancellation_override_phonetics(self):
        for phrase in (
            "不要右邊開燈", "不要有并开灯", "別左邊開燈", "别又边开灯", "右邊不要開燈",
            "右邊不開燈", "不是右邊開燈", "我沒有說右邊開燈", "不右開燈", "右邊開燈不要",
            "請不要有并开灯", "請幫我不要左邊開燈", "取消右邊開燈", "停止左邊開燈",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(classify_sentence(phrase))

    def test_similar_but_different_actions_and_objects_are_dropped(self):
        for phrase in (
            "右邊關燈", "左邊關灯", "又边关灯", "右邊台燈", "左邊檯燈", "有并台灯",
            "左邊看燈", "右边砍灯", "右邊開門", "右邊開冷氣", "左邊開車", "右邊開店",
            "右邊買燈", "右邊拆燈", "右邊開等會", "右邊關登", "右邊開凍", "右邊太冷",
            "右邊揩燈", "左邊揩燈", "右邊開凳", "左邊開凳",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(classify_sentence(phrase))

    def test_questions_reports_conditions_and_multiple_directions_are_dropped(self):
        for phrase in (
            "右邊開燈嗎", "右邊開燈？", "有并开灯?", "可以右邊開燈嗎", "如果右邊開燈",
            "他說右邊開燈", "請說右邊開燈", "右邊開燈是什麼意思", "昨天右邊開燈",
            "左邊開燈右邊開燈", "左右邊開燈", "左邊或右邊開燈", "左又開燈", "左有開燈",
            "開燈", "右邊", "天氣很好", "請今天天氣很好", "右邊開燈1", "右邊開燈💡",
            "右邊開燈然後不要", "右邊開燈左邊關燈",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(classify_sentence(phrase))

    def test_no_generic_direction_edit_distance_or_partial_matching(self):
        for phrase in ("後邊開燈", "前邊開燈", "上邊開燈", "下邊開燈", "右半開燈", "左北開燈", "我又邊開燈", "有并开灯今天"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(classify_sentence(phrase))

    def test_explains_drop_and_handles_empty_or_oversized_input(self):
        for phrase in ("", " ", "有" * 101, "不要有并开灯", "右邊關燈", "左邊右邊開燈"):
            with self.subTest(phrase=phrase):
                match = interpret_sentence(phrase)
                self.assertEqual(match.method, "rejected")
                self.assertIsNone(match.command)
                self.assertIsNone(match.phrase)
                self.assertTrue(match.reason)


if __name__ == "__main__":
    unittest.main()
