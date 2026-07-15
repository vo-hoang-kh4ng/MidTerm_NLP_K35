# -*- coding: utf-8 -*-
"""Hiệu đính lỗi OCR văn bản tiếng Việt bằng Google Gemini.

Chèn giữa bước chuẩn hóa và tách câu: sửa chính tả/dấu thanh và khôi phục
dấu câu ở mức đoạn văn để tách câu sạch hơn. Thiết kế cho phép tiêm client
(dependency injection) nên phần điều phối test được mà không gọi API thật.
"""


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
