"""
diag_ocr_scores.py
OCR 1 trang cụ thể mà KHÔNG áp dụng score_threshold, in ra TẤT CẢ dòng
PaddleOCR nhận diện được kèm điểm confidence - dùng để kiểm tra xem 1
đoạn text bị "biến mất" trong pipeline có phải do bị lọc bởi
config.OCR_SCORE_THRESHOLD hay không.

Cách dùng:
    python diag_ocr_scores.py "input/Hùng Vương Dựng Nước tập 1.pdf" <số_trang>
"""

import sys
import io

import fitz
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR

import config


def main():

    if len(sys.argv) < 3:
        print("Cách dùng: python diag_ocr_scores.py <đường_dẫn_pdf> <số_trang>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2])

    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]

    pix = page.get_pixmap(dpi=config.OCR_DPI)
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    image_np = np.array(image)

    doc.close()

    print("Loading PaddleOCR...")
    ocr = PaddleOCR(lang=config.OCR_LANG)

    result = ocr.predict(image_np)

    if len(result) == 0:
        print("Không có kết quả OCR nào.")
        return

    result = result[0]

    polys = result["dt_polys"]
    texts = result["rec_texts"]
    scores = result["rec_scores"]

    print(f"\nTổng số dòng phát hiện được (CHƯA lọc): {len(texts)}\n")

    # Sắp theo y để dễ đối chiếu với vị trí trên trang
    items = list(zip(polys, texts, scores))
    items.sort(key=lambda it: it[0][:, 1].min())

    threshold = config.OCR_SCORE_THRESHOLD

    for poly, text, score in items:

        y = int(poly[:, 1].min())

        flag = "GIỮ LẠI" if score >= threshold else ">>> BỊ LOẠI (dưới threshold) <<<"

        print(f"y={y:5d}  score={score:.4f}  [{flag}]  text={text!r}")

    print(f"\nNgưỡng hiện tại (config.OCR_SCORE_THRESHOLD) = {threshold}")


if __name__ == "__main__":
    main()
