"""
Cách dùng:

    # 1 file:
    python extract_pdf_text.py --pdf "input/HungVuongtrongtamthucnguoiViet.pdf"

    # nhiều file cùng lúc:
    python extract_pdf_text.py --pdf a.pdf b.pdf c.pdf

    # tuỳ chỉnh thư mục đích:
    python3 extract_pdf_text.py --pdf HungVuongtrongtamthucnguoiViet.pdf HungVuongtrongtamthucnguoiViet2.pdf HungVuongtrongtamthucnguoiViet3.pdf HungVuongtrongtamthucnguoiViet4.pdf HungVuongtrongtamthucnguoiViet5.pdf  --out-dir knowledge/history_books
"""

import os
import re
import argparse
from collections import Counter

import fitz  # PyMuPDF

import config


def clean_extracted_text(text):
    """
    Dọn một số lỗi thường gặp khi trích text từ PDF:
    - Ligature/diacritic bị rớt khi extract (vd 'c ch' thay vì 'cách')
      -> không thể tự động sửa 100% bằng rule, nhưng dọn khoảng trắng thừa,
         xuống dòng thừa, số trang lẫn vào giữa câu.
    """

    # Windows line ending
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Gộp khoảng trắng liên tiếp trong 1 dòng
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Xoá các dòng chỉ chứa số trang đơn lẻ (thường 1-4 chữ số)
    text = re.sub(r"\n\s*\d{1,4}\s*\n", "\n", text)

    # Gộp nhiều dòng trống liên tiếp thành 1
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def remove_inline_footnote_markers(text):
    """
    Xóa số cước chú (footnote reference) bị dính liền vào cuối từ khi
    PDF extract superscript thành ký tự thường, kiểu:

        "Vua Vũ chia chín châu3 thì Bách Việt4 thuộc..."
        -> "Vua Vũ chia chín châu thì Bách Việt thuộc..."

    Quy tắc: chỉ xóa 1-2 chữ số ĐI NGAY SAU 1 ký tự chữ (không phải số,
    không phải khoảng trắng) và NGAY TRƯỚC khoảng trắng/dấu câu.
    Nhờ vậy các số thật sự (có khoảng trắng phía trước, vd "năm thứ 17",
    "[257 TCN]", ngày tháng năm...) KHÔNG bị ảnh hưởng, vì lookbehind
    yêu cầu ký tự ngay trước số phải là chữ cái, không phải khoảng trắng.

    Giới hạn đã biết: số cước chú bị tách ra dòng riêng ở chỗ ngắt trang
    (vd '...Hy thị\\n1 đến ở Nam Giao...') không được xử lý ở đây, vì
    không thể phân biệt chắc chắn với nội dung liệt kê thật (1. 2. 3.).
    Trường hợp này là nhiễu nhỏ, chấp nhận được vì file chỉ dùng làm
    ngữ cảnh RAG, không phải văn bản cần chính xác tuyệt đối.
    """

    pattern = re.compile(
        r'(?<=[A-Za-zÀ-ỹ])(\d{1,2})(?=[\s,\.;:\)\]"]|$)'
    )

    return pattern.sub("", text)


def _normalize_header_line(line):
    """
    Chuẩn hóa 1 dòng để so khớp header/footer lặp lại giữa các trang,
    bất chấp số trang thay đổi ở đầu/cuối dòng.
    Vd: '6 Đại Việt Sử Ký Toàn Thư - Ngoại Kỷ - Quyển I'
        '9 Đại Việt Sử Ký Toàn Thư - Ngoại Kỷ - Quyển I'
    đều chuẩn hóa về: 'đại việt sử ký toàn thư - ngoại kỷ - quyển i'
    """

    norm = line.strip()

    # Bỏ số trang ở đầu dòng (vd "6 Đại Việt..." -> "Đại Việt...")
    norm = re.sub(r"^\d{1,4}\s+", "", norm)

    # Bỏ số trang ở cuối dòng (vd "...Quyển I 6" -> "...Quyển I")
    norm = re.sub(r"\s+\d{1,4}$", "", norm)

    return norm.lower().strip()


def remove_running_headers_footers(
    pages,
    edge_lines=2,
    min_ratio=0.3
):
    """
    Tự động phát hiện header/footer lặp lại ở đầu/cuối mỗi trang
    (vd '6 Đại Việt Sử Ký Toàn Thư - Ngoại Kỷ - Quyển I' lặp lại
    hàng trăm lần trong sách dài, số trang thay đổi mỗi lần) và xóa chúng.

    Cách làm: xét `edge_lines` dòng đầu + `edge_lines` dòng cuối của
    mỗi trang, CHUẨN HÓA bỏ số trang rồi đếm tần suất. Dòng (đã chuẩn
    hóa) nào xuất hiện ở >= min_ratio số trang thì coi là header/footer
    lặp, xóa dòng gốc tương ứng khỏi mỗi trang.
    """

    if len(pages) < 3:
        return pages

    page_lines_list = [p.split("\n") for p in pages]

    edge_counter = Counter()

    for lines in page_lines_list:

        candidates = lines[:edge_lines] + lines[-edge_lines:]

        for line in candidates:

            norm = _normalize_header_line(line)

            # Bỏ qua dòng trống hoặc quá ngắn (không đáng tin là header)
            if len(norm) < 3:
                continue

            edge_counter[norm] += 1

    threshold = max(2, int(len(pages) * min_ratio))

    repeated_norms = {
        norm for norm, count in edge_counter.items()
        if count >= threshold
    }

    cleaned_pages = []

    for lines in page_lines_list:

        cleaned = [
            ln for ln in lines
            if _normalize_header_line(ln) not in repeated_norms
        ]

        cleaned_pages.append("\n".join(cleaned))

    if repeated_norms:
        print(f"  Đã phát hiện và xóa {len(repeated_norms)} mẫu header/footer lặp lại:")
        for norm in list(repeated_norms)[:10]:
            print(f"    - {norm}")
        if len(repeated_norms) > 10:
            print(f"    ... và {len(repeated_norms) - 10} mẫu khác")

    return cleaned_pages


def extract_pdf(pdf_path, strip_headers=True, strip_footnote_markers=True):

    doc = fitz.open(pdf_path)

    pages_text = [page.get_text("text") for page in doc]

    doc.close()

    if strip_headers:
        pages_text = remove_running_headers_footers(pages_text)

    full_text = "\n".join(pages_text)

    if strip_footnote_markers:
        full_text = remove_inline_footnote_markers(full_text)

    return clean_extracted_text(full_text)


def main():

    parser = argparse.ArgumentParser(
        description="Trích text từ PDF born-digital, lưu vào knowledge_dir"
    )

    parser.add_argument(
        "--pdf",
        nargs="+",
        required=True,
        help="1 hoặc nhiều đường dẫn file PDF cần trích text"
    )

    parser.add_argument(
        "--out-dir",
        type=str,
        default=os.path.join(config.BASE_DIR, "knowledge", "history_books"),
        help="Thư mục lưu file .txt kết quả (mặc định: knowledge/history_books)"
    )

    parser.add_argument(
        "--no-strip-headers",
        action="store_true",
        help=(
            "Tắt tính năng tự động xóa header/footer lặp lại theo trang "
            "(mặc định: BẬT, nên để bật với sách nhiều trang)"
        )
    )

    parser.add_argument(
        "--no-strip-footnotes",
        action="store_true",
        help=(
            "Tắt tính năng xóa số cước chú dính liền vào từ (vd 'châu3') "
            "(mặc định: BẬT)"
        )
    )

    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    for pdf_path in args.pdf:

        if not os.path.exists(pdf_path):
            print(f"[BỎ QUA] Không tìm thấy: {pdf_path}")
            continue

        print(f"Đang trích text: {pdf_path}")

        text = extract_pdf(
            pdf_path,
            strip_headers=not args.no_strip_headers,
            strip_footnote_markers=not args.no_strip_footnotes
        )

        filename = os.path.splitext(os.path.basename(pdf_path))[0] + ".txt"
        out_path = os.path.join(args.out_dir, filename)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

        print(f"  -> Đã lưu: {out_path} ({len(text)} ký tự)")

    print()
    print("Xong. Chạy tiếp:")
    print(f"  python build_knowledge_index.py --knowledge-dir {args.out_dir} --rebuild")


if __name__ == "__main__":
    main()
