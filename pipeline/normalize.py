# -*- coding: utf-8 -*-
"""Chuẩn hóa text tiếng Việt trích từ PDF.

Các bước:
1. Chuẩn hóa Unicode về dạng NFC (dấu tổ hợp -> ký tự dựng sẵn).
2. Chuẩn hóa vị trí dấu thanh theo kiểu mới (hoà -> hòa, thuỷ -> thủy...).
3. Lọc rác từ PDF/OCR: header lặp, số trang, watermark/URL, dòng viết hoa
   toàn bộ (tiêu đề chương), ký tự điều khiển.
4. Nối các dòng bị ngắt giữa câu, gộp khoảng trắng.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# 1) Chuẩn hóa vị trí dấu thanh (kiểu cũ -> kiểu mới)
# ---------------------------------------------------------------------------
# Kiểu cũ đặt dấu trên nguyên âm đầu của "oa/oe/uy" (hoà, khoẻ, thuỷ);
# kiểu mới (chuẩn hiện hành) đặt trên nguyên âm sau (hòa, khỏe, thủy).
_TONE_OLD_NEW = {
    "oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oè": "òe", "oé": "óe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
}
_TONE_UY = {"uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy"}
# Thêm cả dạng viết hoa chữ đầu (Oà -> Òa ...)
_TONE_OLD_NEW.update({k.capitalize(): v.capitalize() for k, v in list(_TONE_OLD_NEW.items())})
_TONE_UY.update({k.capitalize(): v.capitalize() for k, v in list(_TONE_UY.items())})
_TONE_RE = re.compile("|".join(map(re.escape, _TONE_OLD_NEW)))
# "uy" chỉ đổi khi KHÔNG đứng sau q/Q ("qu" là phụ âm đầu: quý, quỳnh giữ nguyên)
_TONE_UY_RE = re.compile(r"(?<![qQ])(?:" + "|".join(map(re.escape, _TONE_UY)) + r")")


# Lỗi OCR đặt dấu sai âm tiết đóng: "tòan/ngòai/lọai" -> "toàn/ngoài/loại".
# Chính tả đúng không bao giờ có "òa" + chữ cái theo sau, nên gặp là sửa.
_O_TONE_TO_A = {"ò": "à", "ó": "á", "ỏ": "ả", "õ": "ã", "ọ": "ạ"}


def normalize_tone_position(text):
    text = _TONE_RE.sub(lambda m: _TONE_OLD_NEW[m.group(0)], text)
    text = _TONE_UY_RE.sub(lambda m: _TONE_UY[m.group(0)], text)
    text = re.sub(
        r"([òóỏõọ])a(?=[a-zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịùúủũụưừứửữựỳýỷỹỵđ])",
        lambda m: "o" + _O_TONE_TO_A[m.group(1)],
        text,
    )
    return text


# ---------------------------------------------------------------------------
# 2) Lọc dòng rác
# ---------------------------------------------------------------------------
_RE_PAGE_NUMBER = re.compile(r"^\s*[-–—.•]*\s*\d{1,4}\s*[-–—.•]*\s*$")
# Header chạy đầu trang: "<số trang> Lịch triều hiến chương loại chí" /
# "<Tên chí> <số trang>" (chấp nhận lỗi OCR trong từ "loại")
_RE_RUNNING_HEADER = re.compile(
    r"^\s*(?:\d{1,4}\s+)?"
    r"(?:Lịch\s+triều\s+hiến\s+chương\s+l\w+\s+chí"
    r"|Dư\s+địa\s+chí|Nhân\s+vật\s+chí|Quan\s+chức\s+chí|Lễ\s+nghi\s+chí"
    r"|Khoa\s+mục\s+chí|Quốc\s+dụng\s+chí|Hình\s+luật\s+chí"
    r"|Binh\s+chế\s+chí|Văn\s+tịch\s+chí|Bang\s+giao\s+chí)"
    r"(?:\s+\d{1,4})?\s*$",
    re.IGNORECASE,
)
_RE_URL = re.compile(r"(https?://|www\.|\.com|\.vn\b)", re.IGNORECASE)
# Ký tự điều khiển + soft hyphen + BOM + zero-width
_RE_CONTROL = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f­﻿​‌‍]"
)

# Chữ cái tiếng Việt viết hoa (dùng để nhận diện dòng tiêu đề toàn chữ hoa)
_VIET_UPPER = (
    "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊ"
    "ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
)
_RE_ALLCAPS_LINE = re.compile(r"^[\s%s0-9\W]+$" % _VIET_UPPER)

# Dòng tiêu đề quyển/phần/chương: "Quyển I", "Quyển V. (Tiếp theo)"...
# (chấp nhận lỗi OCR trong số La Mã: "Quyền XVIH", "Quyển XVTH")
_RE_HEADING = re.compile(
    r"^(?:Quyển|Quyền|Phần|Chương|Mục|Tiết)\s+(?:thứ\s+)?[IVXLCHT\d]+\.?"
    r"(?:\s*\([Tt]iếp theo\))?\s*$"
)
_RE_TIEP_THEO = re.compile(r"^\([Tt]iếp theo\)\s*$")

_VIET_DIACRITIC = set(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợ"
    "ùúủũụưừứửữựỳýỷỹỵđ"
)


def _looks_gibberish(s):
    """Dòng ngắn là rác OCR (hoa văn trang): 'Ra go', 'lo NG ng', '%%p 7/32'."""
    if len(s) > 20 or s[-1:] in ".!?:;,\"”)":
        return False
    letters = sum(c.isalpha() for c in s)
    if letters == 0:
        return True
    nonword = sum(not (c.isalnum() or c.isspace()) for c in s)
    if nonword / len(s) > 0.25:
        return True
    tokens = s.split()
    if all(len(t) <= 3 for t in tokens) and not (set(s.lower()) & _VIET_DIACRITIC):
        return True
    return False


def _is_junk_line(line):
    s = line.strip()
    if not s:
        return True
    if _RE_PAGE_NUMBER.match(s):          
        return True
    if _RE_RUNNING_HEADER.match(s):       
        return True
    if _RE_URL.search(s):                 
        return True
    # Dòng toàn chữ hoa (tiêu đề chương/mục) và không kết thúc bằng dấu câu
    if len(s) <= 80 and _RE_ALLCAPS_LINE.match(s) and any(c.isalpha() for c in s):
        return True
    # Dòng quá ngắn không mang nội dung (ký hiệu OCR lạc)
    if len(s) <= 2 and not s.isalpha():
        return True
    if _looks_gibberish(s):
        return True
    return False


# ---------------------------------------------------------------------------
# 3) Chuẩn hóa ký tự / khoảng trắng
# ---------------------------------------------------------------------------
_CHAR_FIXES = {
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "…": "...",
    " ": " ",
    "–": "-", "—": "-",
    # Dấu câu full-width CJK (hay gặp ở text OCR từ sách in lẫn font Hán):
    # đưa về ASCII để tách câu/underthesea nhận đúng ranh giới câu.
    "，": ",", "．": ".", "。": ".", "、": ",", "；": ";", "：": ":",
    "！": "!", "？": "?", "（": "(", "）": ")",
    "「": '"', "」": '"', "『": '"', "』": '"',
    "｀": "'", "･": "-",
}


def normalize_page_text(raw_text):
    """Chuẩn hóa text của một trang, trả về một khối văn bản liền mạch."""
    text = unicodedata.normalize("NFC", raw_text)
    text = _RE_CONTROL.sub("", text)
    for old, new in _CHAR_FIXES.items():
        text = text.replace(old, new)
    text = normalize_tone_position(text)

    # Ký hiệu chú thích bị OCR nhận nhầm: ®, ©, ™ và "(1)" dính ngay sau từ
    text = re.sub(r"[®©™°]+", "", text)
    text = re.sub(r"(?<=\w)\(\d{1,2}\)", "", text)
    text = re.sub(r"(?<=\w)\(\?+\)?", "", text)

    def _join_block(block_lines):
        # Nối từ bị ngắt bằng gạch nối cuối dòng: "chương-\ntrình" -> "chươngtrình"
        j = "\n".join(block_lines)
        j = re.sub(r"(\w)-\n(\w)", r"\1\2", j)
        # Các ngắt dòng còn lại là ngắt giữa đoạn -> thay bằng khoảng trắng
        j = re.sub(r"\s*\n\s*", " ", j)
        # Gộp khoảng trắng, bỏ khoảng trắng trước dấu câu
        j = re.sub(r"\s+", " ", j)
        j = re.sub(r"\s+([,.;:!?)\]])", r"\1", j)
        j = re.sub(r"([(\[])\s+", r"\1", j)
        # OCR hay dính câu: dấu kết câu liền ngay chữ hoa -> chèn khoảng trắng
        # để underthesea nhận đúng ranh giới câu ("...dân tộc,Thời..." ->
        # "...dân tộc, Thời..."). Chỉ chèn khi sau dấu là chữ cái HOA để tránh
        # phá "tr.290", "G.S." hay số thập phân.
        j = re.sub(r"([.!?,])([%s])" % _VIET_UPPER, r"\1 \2", j)
        return j.strip()

    # Tách trang thành các "khối" ngăn bằng \n. Tiêu đề quyển/phần bị BỎ
    # (nhất quán với tiêu đề chương in hoa như "DƯ ĐỊA CHÍ" đã bị lọc)
    # nhưng vẫn dùng làm ranh giới khối để câu trước và câu sau tiêu đề
    # không bị dính vào nhau.
    blocks, buf = [], []
    for ln in text.splitlines():
        s = ln.strip()
        if _RE_HEADING.match(s) or _RE_TIEP_THEO.match(s):
            if buf:
                blocks.append(_join_block(buf))
                buf = []
            continue
        if _is_junk_line(s):
            continue
        buf.append(ln)
    if buf:
        blocks.append(_join_block(buf))

    return "\n".join(b for b in blocks if b)
