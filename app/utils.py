"""ユーティリティ関数"""
import re
from typing import List


def merge_keywords(
    ram_tags: List[str],
    caption_keywords: List[str],
    max_keywords: int = 20,
) -> List[str]:
    """
    RAM++ タグとキャプションキーワードを統合。
    RAM++ を優先し、重複を除いて caption から補完。
    """
    seen = set()
    result = []
    for t in ram_tags:
        w = t.strip().lower()
        if len(w) >= 2 and w not in seen:
            seen.add(w)
            result.append(t.strip())
            if len(result) >= max_keywords:
                return result
    for w in caption_keywords:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            result.append(w)
            if len(result) >= max_keywords:
                return result
    return result


# 英語ストップワード + 画像キャプション特有の定型語（"The image shows ..." 等）
STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "it", "its", "it's", "this", "that", "these", "those", "there", "here",
    "which", "who", "whom", "whose", "what", "where", "when", "while", "also",
    "into", "onto", "over", "under", "up", "down", "out", "off", "about",
    "some", "any", "each", "other", "such", "than", "then", "very", "so",
    "they", "them", "their", "he", "him", "his", "she", "her", "we", "our",
    "you", "your", "i", "my", "me", "not", "no", "only", "just", "both",
    "appears", "appear", "seems", "seem", "looks", "look", "shows", "show",
    "showing", "shown", "depicts", "depicting", "features", "featuring",
    "image", "picture", "photo", "photograph", "background", "foreground",
    "visible", "overall", "several", "various", "slightly", "likely",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


def caption_to_keywords(caption: str, max_keywords: int = 20) -> List[str]:
    """
    キャプションからキーワードを抽出する。
    単語単位に分割し（ハイフン語 "black-and-white" は保持）、ストップワードを除去。
    """
    if not caption or not caption.strip():
        return []

    keywords = []
    seen = set()
    for w in _TOKEN_RE.findall(caption.lower()):
        if w.endswith("'s"):
            w = w[:-2]
        if len(w) < 2 or w.isdigit():
            continue
        if w in STOP_WORDS:
            continue
        if w in seen:
            continue
        seen.add(w)
        keywords.append(w)
        if len(keywords) >= max_keywords:
            break

    return keywords
