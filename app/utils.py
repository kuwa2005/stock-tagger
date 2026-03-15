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


def caption_to_keywords(caption: str, max_keywords: int = 20) -> List[str]:
    """
    キャプションからキーワードを抽出する。
    カンマ・ピリオドで分割し、ストップワードを除去。
    """
    if not caption or not caption.strip():
        return []

    # 句読点で分割、小文字化、空白除去
    text = caption.lower().strip()
    parts = re.split(r"[,.\-;:\s]+", text)

    # ストップワード（英語）
    stop_words = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "can", "need",
    }

    keywords = []
    seen = set()
    for w in parts:
        w = w.strip()
        if len(w) < 2:
            continue
        if w in stop_words:
            continue
        if w in seen:
            continue
        seen.add(w)
        keywords.append(w)
        if len(keywords) >= max_keywords:
            break

    return keywords
