# -*- coding: utf-8 -*-
"""Trích text từ PDF scan ảnh (không có text layer) bằng PaddleOCR.

Đường vào thay thế cho pipeline.extract.extract_pages khi PDF chỉ chứa ảnh
quét: render từng trang thành ảnh (PyMuPDF) rồi nhận dạng bằng PaddleOCR.
Trả về cùng cấu trúc (số_trang, text) để các bước sau (normalize, correct,
segment, ner) dùng nguyên như với PDF có text layer.
"""

import gc
import io


def _load_paddleocr(lang):
    """Import PaddleOCR tại chỗ để pipeline chính không bắt buộc cài paddle."""
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        raise SystemExit(
            "Thiếu PaddleOCR. Cài: pip install paddlepaddle paddleocr"
        )
    return PaddleOCR(lang=lang)


def _page_to_image(page, dpi):
    """Render một trang PDF thành ảnh numpy (RGB)."""
    import numpy as np
    from PIL import Image

    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return np.array(img)


def _image_to_text(ocr, image):
    """Nhận dạng một ảnh trang, trả về text (mỗi dòng OCR một dòng)."""
    result = ocr.predict(image)
    if not result:
        return ""
    page = result[0]
    if "rec_texts" not in page:
        return ""
    return "\n".join(page["rec_texts"])


def extract_pages_ocr(pdf_path, start_page=1, end_page=None, dpi=200, lang="vi"):
    """Trả về danh sách (số_trang, text) cho các trang [start_page, end_page].

    Cùng hợp đồng với pipeline.extract.extract_pages: trang tính từ 1,
    end_page=None nghĩa là đến hết file.
    """
    import fitz

    ocr = _load_paddleocr(lang)

    doc = fitz.open(pdf_path)
    total = doc.page_count
    if end_page is None or end_page > total:
        end_page = total

    pages = []
    for pno in range(start_page - 1, end_page):
        print(f"      OCR trang {pno + 1}/{end_page}")
        image = _page_to_image(doc.load_page(pno), dpi)
        text = _image_to_text(ocr, image)
        pages.append((pno + 1, text))
        del image
        gc.collect()
    doc.close()
    return pages
