"""Local, bounded pronunciation repair for two LED commands.

This is deliberately not whole-sentence edit distance: changing one syllable in
a four-syllable command can change its direction, action, or object entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from pypinyin import Style, lazy_pinyin


@dataclass(frozen=True)
class SentenceMatch:
    command: str | None
    phrase: str | None
    method: str  # exact, phonetic, or rejected
    reason: str


_CANONICAL = {"左邊開燈": "BLUE_ON", "右邊開燈": "GREEN_ON"}
_TRADITIONAL = str.maketrans({"边": "邊", "开": "開", "灯": "燈"})
_PREFIXES = ("麻煩幫我", "麻烦帮我", "請幫我", "请帮我", "幫我", "帮我", "麻煩", "麻烦", "請", "请")
# The command templates below also reject other extra words. These checks give
# the user a useful reason, and run BEFORE removing a polite request prefix.
_NEGATION = ("不", "別", "别", "勿", "沒", "没", "無", "无", "取消", "停止", "停下", "撤回")
_OTHER_ACTION = ("關", "关", "熄", "閉", "闭", "揩", "凳", "看燈", "看灯", "台燈", "台灯", "檯燈", "檯灯")
_QUESTION_OR_REPORT = ("嗎", "吗", "是否", "能否", "為何", "为何", "為什麼", "为什么", "怎麼", "怎么", "如何", "如果", "假如", "說", "说", "唸", "念", "例如", "比如")
# No general edit-distance fallback: the first syllable cannot drift from left
# to right, and kai/deng cannot drift to kan/guan/tai/men/dian, etc.
_DIRECTION = {"zuo": "左邊開燈", "you": "右邊開燈"}
_SIDE_SYLLABLES = frozenset({"bian", "bin", "bing"})


def _reject(reason: str) -> SentenceMatch:
    return SentenceMatch(None, None, "rejected", reason)


def interpret_sentence(text: str) -> SentenceMatch:
    """Use a full short-command template, semantic exclusions, then phonetics.

    Tone differences and homophone characters are tolerated. bian/bin/bing are
    the only near-syllable variants, based on the observed '有并开灯' error.
    The original transcript is never rewritten by this function.
    """
    if not isinstance(text, str) or not text.strip():
        return _reject("沒有辨識到完整語句")
    if len(text) > 100:
        return _reject("語句太長，請一次說一個開燈口令")
    text = unicodedata.normalize("NFKC", text)
    # Question marks carry meaning; don't erase them as ordinary punctuation.
    if "?" in text:
        return _reject("這是疑問句，不執行控制")
    normalized = "".join(
        char for char in text
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    ).translate(_TRADITIONAL)
    if any(word in normalized for word in _NEGATION):
        return _reject("包含否定或取消意思，不執行控制")
    if any(word in normalized for word in _OTHER_ACTION):
        return _reject("動作或對象不是明確的開燈，不執行控制")
    if any(word in normalized for word in _QUESTION_OR_REPORT):
        return _reject("是疑問、條件或轉述語句，不執行控制")
    if "左" in normalized and "右" in normalized:
        return _reject("同時出現左右方向，請一次指定一邊")
    # Strip at most one explicitly allowed request prefix, never arbitrary text.
    for prefix in _PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    if normalized in _CANONICAL:
        return SentenceMatch(_CANONICAL[normalized], normalized, "exact", "明確的開燈口令")
    if len(normalized) != 4 or not all("\u3400" <= char <= "\u9fff" for char in normalized):
        return _reject("不符合單一左右開燈口令，未送出")
    # Use one pronunciation per character; don't enumerate polyphonic readings
    # just to force a sentence into one of the control commands.
    sounds = lazy_pinyin(normalized, style=Style.NORMAL, strict=True)
    if len(sounds) != 4 or sounds[0] not in _DIRECTION or sounds[1] not in _SIDE_SYLLABLES:
        return _reject("左右方向不夠明確，請重說一次")
    if sounds[2:] != ["kai", "deng"]:
        return _reject("開燈的動作或對象不明確，不執行控制")
    phrase = _DIRECTION[sounds[0]]
    return SentenceMatch(_CANONICAL[phrase], phrase, "phonetic", "同音或近音校正")


def classify_sentence(text: str) -> str | None:
    """Compatibility helper for callers that only need a command or a dropout."""
    return interpret_sentence(text).command
