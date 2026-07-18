"""
diag_hybrid_items.py
Gọi trực tiếp các hàm nội bộ của HybridExtractor cho 1 trang cụ thể,
in ra TỪNG BƯỚC (items thu thập được -> lines sau khi gộp) để xác định
chính xác bước nào làm mất nội dung so với OCR trực tiếp toàn trang.

Cách dùng:
    python diag_hybrid_items.py "input/Hùng Vương Dựng Nước tập 1.pdf" 3
"""

import sys

import fitz

import config
from ocr_engine import OCRProcessor
from hybrid_extractor import HybridExtractor


def main():

    if len(sys.argv) < 3:
        print("Cách dùng: python diag_hybrid_items.py <đường_dẫn_pdf> <số_trang>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2])

    print("Loading OCR...")
    ocr = OCRProcessor(
        dpi=config.OCR_DPI,
        lang=config.OCR_LANG,
        score_threshold=config.OCR_SCORE_THRESHOLD
    )

    extractor = HybridExtractor(
        ocr_processor=ocr,
        min_chars_per_page=config.MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER,
        min_alpha_ratio=config.MIN_ALPHA_RATIO_FOR_TEXT_LAYER,
        line_y_tolerance=config.LINE_Y_TOLERANCE
    )

    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]

    print()
    print("=" * 60)
    print("BƯỚC 1: _collect_page_items() - items thu thập được")
    print("=" * 60)

    items = extractor._collect_page_items(page)

    print(f"Tổng số item: {len(items)}\n")

    items_sorted = sorted(items, key=lambda it: it["bbox"][1])

    for it in items_sorted:
        print(f"  y={it['bbox'][1]:8.2f}  x={it['bbox'][0]:8.2f}  text={it['text']!r}")

    print()
    print("=" * 60)
    print("BƯỚC 2: _group_into_lines() - dòng sau khi gộp")
    print("=" * 60)

    lines = extractor._group_into_lines(items)

    print(f"Tổng số dòng sau khi gộp: {len(lines)}\n")

    for i, line in enumerate(lines):
        print(f"  [{i}] {line!r}")

    doc.close()


if __name__ == "__main__":
    main()
