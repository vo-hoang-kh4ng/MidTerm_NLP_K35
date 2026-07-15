# -*- coding: utf-8 -*-
"""Trích xuất text từ file PDF bằng PyMuPDF (fitz).

Nếu PDF có bookmark (mục lục điện tử) thì tự xác định khoảng trang nội dung
chính: bỏ các chương kiểu mục lục / lời nói đầu / sách dẫn... và bỏ phần
đầu sách (bìa, lời giới thiệu) đứng trước chương nội dung đầu tiên.
Nếu PDF không có bookmark thì lấy toàn bộ file.
"""

import re

import fitz  # PyMuPDF

# Tiêu đề bookmark KHÔNG phải nội dung chính
_RE_JUNK_TITLE = re.compile(
    r"mục\s*lục|lời\s*nói\s*đầu|lời\s*giới\s*thiệu|lời\s*tựa|phàm\s*lệ|"
    r"sách\s*dẫn|phụ\s*lục|tài\s*liệu\s*tham\s*khảo|contents|index|preface|foreword",
    re.IGNORECASE,
)
# Tiêu đề trông giống một chương nội dung: "I. ...", "Chương 1", "Phần 2", "1. ..."
_RE_CHAPTER_TITLE = re.compile(r"^\s*(?:chương|phần|quyển|[IVXLC]+[.\s]|\d+[.\s])", re.IGNORECASE)


def detect_content_range(pdf_path):
    """Trả về (start_page, end_page, chapters) tính theo trang PDF bắt đầu từ 1.

    chapters: danh sách (tiêu_đề, trang_đầu, trang_cuối) của các chương nội dung
    chính được giữ lại (rỗng nếu PDF không có bookmark -> lấy hết).
    """
    doc = fitz.open(pdf_path)
    total = doc.page_count
    toc = doc.get_toc()
    doc.close()

    if not toc:  # không có bookmark -> lấy toàn bộ
        return 1, total, []

    # Chỉ xét bookmark cấp 1, sắp theo trang; mỗi mục phủ đến trước mục kế tiếp
    entries = sorted([(page, title.strip()) for lvl, title, page in toc if lvl == 1])
    segments = []
    for i, (page, title) in enumerate(entries):
        end = entries[i + 1][0] - 1 if i + 1 < len(entries) else total
        segments.append((title, page, end))

    # Giữ các chương nội dung: bỏ mục lục/lời nói đầu...; bỏ luôn mục mở đầu
    # từ trang 1 (bìa sách/tên sách) nếu nó không có dạng tiêu đề chương và
    # phía sau còn chương thực sự khác.
    content = [s for s in segments if not _RE_JUNK_TITLE.search(s[0])]
    if (len(content) > 1 and content[0][1] == 1
            and not _RE_CHAPTER_TITLE.match(content[0][0])):
        content = content[1:]

    if not content:  # bookmark toàn mục "rác" -> an toàn: lấy hết
        return 1, total, []

    return content[0][1], content[-1][2], content


def extract_pages(pdf_path, start_page=1, end_page=None):
    """Trả về danh sách (số_trang, text) cho các trang [start_page, end_page].

    start_page/end_page tính theo trang PDF, bắt đầu từ 1.
    end_page=None nghĩa là đến hết file.
    """
    doc = fitz.open(pdf_path)
    total = doc.page_count
    if end_page is None or end_page > total:
        end_page = total

    pages = []
    for pno in range(start_page - 1, end_page):
        text = doc.load_page(pno).get_text("text")
        pages.append((pno + 1, text))
    doc.close()
    return pages
