# -*- coding: utf-8 -*-
"""Tách câu tiếng Việt bằng underthesea."""

import re

from underthesea import sent_tokenize

# Câu quá ngắn hoặc không có chữ cái -> loại (rác OCR còn sót)
_RE_HAS_LETTER = re.compile(r"[a-zA-ZÀ-ỹĐđ]")


def split_sentences(text, min_len=4):
    """Tách văn bản thành danh sách câu đã làm sạch.

    Text có thể gồm nhiều khối ngăn bằng \\n (tiêu đề quyển/phần đứng riêng);
    ranh giới khối luôn là ranh giới câu.
    """
    sentences = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        for sent in sent_tokenize(block):
            s = sent.strip()
            if len(s) < min_len:
                continue
            if not _RE_HAS_LETTER.search(s):
                continue
            sentences.append(s)
    return sentences
