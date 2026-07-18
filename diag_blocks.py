"""
diag_blocks.py
Kiểm tra cấu trúc block mà PyMuPDF trả về cho 1 trang cụ thể - dùng để
xác định vì sao hybrid_extractor không trích được 1 vùng text nào đó
(thường do: không có block nào bao phủ vùng đó, hoặc bbox bị lệch).

Cách dùng:
    python diag_blocks.py "input/Hùng Vương Dựng Nước tập 1.pdf" <số_trang>

    <số_trang> đếm từ 1 (trang đầu tiên = 1)
"""

import sys
import fitz


def main():

    if len(sys.argv) < 3:
        print("Cách dùng: python diag_blocks.py <đường_dẫn_pdf> <số_trang>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    page_num = int(sys.argv[2])

    doc = fitz.open(pdf_path)

    if page_num < 1 or page_num > len(doc):
        print(f"Trang không hợp lệ. File có {len(doc)} trang.")
        sys.exit(1)

    page = doc[page_num - 1]

    print(f"Kích thước trang (mediabox): {page.mediabox}")
    print(f"Kích thước trang (rect): {page.rect}")
    print()

    page_dict = page.get_text("dict")
    blocks = page_dict.get("blocks", [])

    print(f"Tổng số block: {len(blocks)}")
    print()

    for i, block in enumerate(blocks):

        btype = block.get("type", 0)
        bbox = block.get("bbox")

        type_name = "TEXT" if btype == 0 else "IMAGE"

        print(f"--- Block {i}: type={type_name}, bbox={bbox} ---")

        if btype == 0:
            for line in block.get("lines", []):
                spans_text = "".join(
                    span.get("text", "") for span in line.get("spans", [])
                )
                print(f"    line bbox={line['bbox']}: {spans_text!r}")
        else:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            print(f"    Kích thước vùng ảnh: {width:.1f} x {height:.1f} point")
            print(f"    So với trang: {page.rect.width:.1f} x {page.rect.height:.1f} point")

            coverage = (width * height) / (page.rect.width * page.rect.height) * 100
            print(f"    Tỷ lệ diện tích so với cả trang: {coverage:.1f}%")

        print()

    doc.close()


if __name__ == "__main__":
    main()
