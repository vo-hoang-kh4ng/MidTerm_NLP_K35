# -*- coding: utf-8 -*-
"""Hiệu đính lỗi OCR văn bản tiếng Việt bằng Google Gemini.

Chèn giữa bước chuẩn hóa và tách câu: sửa chính tả/dấu thanh và khôi phục
dấu câu ở mức đoạn văn để tách câu sạch hơn. Thiết kế cho phép tiêm client
(dependency injection) nên phần điều phối test được mà không gọi API thật.
"""

import hashlib
import json
import os


def chunk_text(page_text, max_chars=2500):
    """Cắt text (đã normalize) thành các chunk <= max_chars theo ranh giới block.

    Không tách một block; block đơn dài hơn max_chars trở thành 1 chunk riêng.
    """
    blocks = [b for b in page_text.split("\n") if b.strip()]
    chunks = []
    buf = []
    size = 0
    for b in blocks:
        add = len(b) + (1 if buf else 0)  # +1 cho "\n" nối
        if buf and size + add > max_chars:
            chunks.append("\n".join(buf))
            buf, size = [], 0
            add = len(b)
        buf.append(b)
        size += add
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def within_length_guard(original, corrected, max_ratio=0.3):
    """True nếu độ dài bản sửa lệch <= max_ratio so với gốc và không rỗng."""
    if not corrected.strip():
        return False
    base = max(len(original), 1)
    return abs(len(corrected) - len(original)) / base <= max_ratio


def cache_key(model, chunk):
    """SHA-256 hex của (model, chunk) — khóa cache ổn định, phân biệt model."""
    return hashlib.sha256((model + "\n" + chunk).encode("utf-8")).hexdigest()


def load_cache(path):
    """Đọc cache JSON; thiếu file hoặc hỏng -> {}."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(path, cache):
    """Ghi cache ra JSON UTF-8, tạo thư mục cha nếu cần."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
