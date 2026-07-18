# -*- coding: utf-8 -*-
"""Nhận diện thực thể (NER) cho văn bản lịch sử tiếng Việt.

Kết hợp hai tầng:
1. Mô hình underthesea.ner  -> PER / LOC / ORG (mô hình CRF tổng quát).
2. Luật + từ điển (gazetteer) -> TME, NUM, TITLE, DYNASTY và bổ trợ
   PER/LOC cho văn phong sử liệu (mô hình tổng quát hay bỏ sót).

Khi các span chồng lấn nhau: span dài hơn thắng; nếu bằng nhau thì theo
độ ưu tiên TME > DYNASTY > TITLE > (mô hình) > LOC luật > PER luật > NUM.
"""

import re

from underthesea import ner as uts_ner

# ---------------------------------------------------------------------------
# Bảng chữ cái tiếng Việt
# ---------------------------------------------------------------------------
_UP = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
_LO = "a-zđàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ"

# Một "từ viết hoa": chấp nhận gạch nối kiểu chính tả cũ (Lam-Sơn, Thái-Tổ,
# Xích-quỷ) — phần sau gạch nối có thể viết hoa hoặc thường.
_CAPWORD = rf"[{_UP}][{_LO}]+(?:-[{_UP}{_LO}][{_LO}]*)*"
_CAPSEQ = rf"{_CAPWORD}(?:\s+{_CAPWORD})*"

_CAN = "Giáp|Ất|Bính|Đinh|Mậu|Kỷ|Canh|Tân|Nhâm|Quý"
_CHI = "Tý|Sửu|Dần|Mão|Mẹo|Thìn|Tỵ|Ngọ|Mùi|Thân|Dậu|Tuất|Hợi"
_CANCHI = rf"(?:{_CAN})\s+(?:{_CHI})"

# Hậu tố kỷ nguyên: "trước Công nguyên", "TCN", "tr. Th. Ch. G.S.",
# "trước Thiên Chúa giáng sinh" (sách in cũ)
_ERA = (
    r"(?:tr(?:ước)?|sau)\s+(?:Công\s+[Nn]guyên|Thiên\s+Chúa(?:\s+giáng\s+sinh)?)|"
    r"tr\.?\s?Th\.?\s?Ch\.?(?:\s?G\.?\s?S\.?)?|TCN|SCN|tr\.?\s?CN"
)

# ---------------------------------------------------------------------------
# Luật thời gian (TME)
# ---------------------------------------------------------------------------
_TME_PATTERNS = [
    rf"[Nn]gày\s+(?:mồng\s+|mùng\s+)?(?:\d{{1,2}}|{_CANCHI})\b",
    rf"[Tt]háng\s+(?:\d{{1,2}}|[Gg]iêng|[Cc]hạp)(?:\s+nhuận)?\b",
    rf"[Nn]ăm\s+{_CAPSEQ}\s+thứ\s+\d+\b",          # năm Hồng Đức thứ 2
    # "năm 333 tr. Th. Ch. G.S.", "năm 40 trước Công nguyên", "179 TCN"
    rf"[Nn]ăm\s+\d{{1,4}}\s*(?:{_ERA})\b",
    r"\b\d{1,4}\s*(?:TCN|tr\.?\s?CN)\b",
    rf"[Nn]ăm\s+(?:\d{{3,4}}|{_CANCHI})\b",
    rf"[Nn]iên\s?hiệu\s+{_CAPSEQ}(?:\s+thứ\s+\d+)?\b",
    rf"[Đđ]ời\s+(?:vua\s+|chúa\s+)?{_CAPSEQ}\b",
    r"[Mm]ùa\s+(?:xuân|hạ|thu|đông)\b",
    rf"[Tt]hế\s?kỷ\s+(?:thứ\s+)?[IVX\d]+(?:\s*(?:{_ERA}))?\b",
    r"[Gg]iờ\s+(?:" + _CHI + r")\b",
    # "thời kỳ Hùng Vương", "sơ kỳ thời đại đá mới", "hậu kỳ thời đại đồng thau"
    rf"(?:[Ss]ơ\s+kỳ\s+|[Tt]rung\s+kỳ\s+|[Hh]ậu\s+kỳ\s+)?"
    rf"[Tt]hời\s+(?:kỳ|đại)\s+(?:{_CAPSEQ}|đá(?:\s+(?:cũ|giữa|mới))?|"
    rf"đồng\s+thau|đồ\s+(?:đồng|sắt|đá))\b",
    # Ngày tháng dạng số: 12/3/1970, ngày 2-9-1945
    r"(?:[Nn]gày\s+)?\d{1,2}\s*[/-]\s*\d{1,2}\s*[/-]\s*\d{2,4}\b",
]
_TME_RE = [re.compile(p) for p in _TME_PATTERNS]

# ---------------------------------------------------------------------------
# Triều đại (DYNASTY)
# ---------------------------------------------------------------------------
_DYNASTY_RE = re.compile(rf"\b(?:[Nn]hà|[Tt]riều)\s+{_CAPSEQ}")

# ---------------------------------------------------------------------------
# Chức danh, tước vị (TITLE) — từ điển, ưu tiên cụm dài trước
# ---------------------------------------------------------------------------
_TITLES = [
    "thái thượng hoàng", "hoàng thái hậu", "hoàng thái tử", "an phủ sứ",
    "tuyên phủ sứ", "kinh lược sứ", "tiết độ sứ", "đô ngự sử", "ngự sử đài",
    "hàn lâm học sĩ", "đại học sĩ", "đông các học sĩ", "quốc tử giám tế tửu",
    "hoàng đế", "hoàng hậu", "hoàng tử", "thái tử", "công chúa", "phò mã",
    "quốc công", "quận công", "tể tướng", "thừa tướng", "thái sư", "thái phó",
    "thái bảo", "thái úy", "thiếu sư", "thiếu phó", "thiếu bảo", "thiếu úy",
    "tư đồ", "tư mã", "tư không", "thượng thư", "thị lang", "học sĩ",
    "ngự sử", "tiến sĩ", "trạng nguyên", "bảng nhãn", "thám hoa", "hoàng giáp",
    "cử nhân", "tú tài", "hương cống", "sinh đồ", "tri phủ", "tri huyện",
    "tri châu", "tổng đốc", "tuần phủ", "án sát", "bố chính", "hiệp trấn",
    "trấn thủ", "tổng trấn", "tướng quân", "đại tướng", "đô đốc", "đề đốc",
    "lãnh binh", "cai đội", "chánh sứ", "phó sứ", "tham tri", "tham tụng",
    "bồi tụng", "hành khiển", "thứ sử", "thái thú", "thái giám", "quan lang",
    "vua", "chúa",
    # Chức danh hiện đại (sách thế kỷ 20, vd kỷ yếu Hùng Vương Dựng Nước)
    "phó giáo sư", "giáo sư", "viện trưởng", "hiệu trưởng", "chủ tịch",
    "phó chủ tịch", "bộ trưởng", "thứ trưởng", "giám đốc",
]
_TITLES.sort(key=len, reverse=True)
_TITLE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in _TITLES) + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Địa danh theo từ chỉ loại + tên riêng (bổ trợ LOC)
# ---------------------------------------------------------------------------
_LOC_CUES = (
    "điện|thành phố|thành|phủ|tỉnh|quận|huyện|xã|thôn|làng|trấn|đạo|lộ|châu|"
    "phường|tổng|hạt|sông|núi|hồ|đầm|cửa biển|cửa|đèo|đảo|chùa|đền|miếu|quán|"
    "cầu|chợ|bến|kinh đô|kinh thành|nước|xứ|động|nguồn|ải|cung|lầu|gác|"
    "hành cung|miền|vùng|di chỉ|địa điểm|gò|đồi|hang|mái đá"
)
_LOC_RE = re.compile(rf"\b(?:{_LOC_CUES})\s+{_CAPSEQ}")

# ---------------------------------------------------------------------------
# Nhân danh sau chức danh (bổ trợ PER): "vua Lê Thánh Tông", "tướng Trần..."
# ---------------------------------------------------------------------------
_PER_RE = re.compile(
    rf"\b(?:vua|chúa|ông|bà|họ|tướng|quan|công chúa|hoàng hậu|thái tử|"
    rf"giáo sư|đồng chí)\s+({_CAPSEQ})"
)

# ---------------------------------------------------------------------------
# Tên riêng đứng trần model hay bỏ sót.
# Match nguyên cụm, phân biệt hoa thường.
# ---------------------------------------------------------------------------
_GAZ_PER = [
    "Kinh Dương Vương", "Lạc Long Quân", "Âu Cơ", "An Dương Vương",
    "Sơn Tinh", "Thủy Tinh", "Thánh Gióng", "Chử Đồng Tử", "Tiên Dung",
    "An Tiêm", "Lang Liêu", "Tản Viên", "Hùng Vương",
    "Ngô Sĩ Liên", "Lê Quý Đôn", "Phan Huy Chú",
    # Sử Lê -> Nguyễn (HVQ_037/038)
    "Lê Lợi", "Nguyễn Trãi", "Nguyễn Huệ", "Quang Trung",
    "Lê Thái Tổ", "Lê Thái Tông", "Lê Nhân Tông", "Lê Thánh Tông",
    "Lê Hiến Tông", "Lê Chiêu Thống", "Gia Long", "Minh Mạng", "Tự Đức",
]
_GAZ_LOC = [
    "Văn Lang", "Âu Lạc", "Phong Châu", "Cổ Loa", "Bạch Hạc", "Việt Trì",
    "Phú Thọ", "Vĩnh Phú", "Lâm Thao", "Núi Đọ", "Đa Bút", "Thiệu Dương",
    "Đông Khối", "Việt Khê", "Lũng Hòa", "Gò Bông", "Phùng Nguyên",
    "Đồng Đậu", "Gò Mun", "Đông Sơn",
    # Quốc hiệu / địa danh sử trung-cận đại (HVQ_037/038)
    "Xích Quỷ", "Đại Cồ Việt", "Đại Việt", "Đại Nam", "Chiêm Thành",
    "Chân Lạp", "Thăng Long", "Lam Sơn", "Phú Xuân", "Gia Định",
    "Đàng Trong", "Đàng Ngoài",
]
_GAZ_ORG = [
    "Ủy ban Khoa học Xã hội Việt Nam", "Viện Khảo cổ học", "Viện Sử học",
    "Viện Bảo tàng Lịch sử", "Viện Dân tộc học", "Viện Văn học",
    "Viện Kinh tế học", "Viện Mỹ thuật Mỹ nghệ", "Viện Vật lý Hà Nội",
    "Bảo tàng Lịch sử", "Trường Đại học Tổng hợp", "Vụ Bảo tồn Bảo tàng",
    "Ban Tuyên giáo Tỉnh ủy Vĩnh Phú", "Đoàn Địa chất 58",
]


def _gaz_regex(names):
    names = sorted(names, key=len, reverse=True)  # cụm dài match trước
    # Khoảng trắng trong tên chấp nhận cả gạch nối chính tả cũ (Văn-Lang,
    # Chiêm-Thành); từ sau gạch nối/khoảng trắng có thể viết thường (Xích-quỷ).
    parts = []
    for n in names:
        words = n.split()
        pat = re.escape(words[0])
        for w in words[1:]:
            head = f"[{w[0].upper()}{w[0].lower()}]" if w[0].isalpha() else re.escape(w[0])
            pat += r"[\s\-]" + head + re.escape(w[1:])
        parts.append(pat)
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)")


_GAZ_RES = [
    (_gaz_regex(_GAZ_ORG), "ORG_GAZ"),
    (_gaz_regex(_GAZ_PER), "PER_GAZ"),
    (_gaz_regex(_GAZ_LOC), "LOC_GAZ"),
]

# ---------------------------------------------------------------------------
# Số lượng (NUM)
# ---------------------------------------------------------------------------
_NUM_UNITS = "vạn|ức|nghìn|ngàn|trăm|dặm|trượng|thước|tấc|mẫu|sào|quan|hộc|thạch|cân|lạng|người|năm|tháng|ngày|đời|chiếc|con|quyển|đạo|viên"
_NUM_RE = re.compile(rf"\b\d+(?:[.,]\d+)*(?:\s+(?:{_NUM_UNITS})\b)?")

# Độ ưu tiên khi span bằng độ dài (số nhỏ = ưu tiên cao).
# Gazetteer đứng trên model: tên đã biết chắc nhãn thì không để model đổi nhãn.
_PRIORITY = {"TME": 0, "DYNASTY": 1, "TITLE": 2,
             "ORG_GAZ": 3, "PER_GAZ": 3, "LOC_GAZ": 3,
             "PER": 4, "LOC": 4, "ORG": 4,
             "LOC_RULE": 5, "PER_RULE": 6, "NUM": 7}


def _model_entities(sentence):
    """Chạy underthesea.ner và gộp nhãn BIO thành các span (start, end, label)."""
    spans = []
    try:
        tokens = uts_ner(sentence)
    except Exception:
        return spans

    cursor = 0
    cur = None  # (start, end, label)
    for token in tokens:
        word, tag = token[0], token[3]
        idx = sentence.find(word, cursor)
        if idx < 0:  # tokenizer biến đổi từ (hiếm) -> bỏ qua an toàn
            continue
        cursor = idx + len(word)

        if tag.startswith("B-"):
            if cur:
                spans.append(cur)
            cur = [idx, cursor, tag[2:]]
        elif tag.startswith("I-") and cur and tag[2:] == cur[2]:
            cur[1] = cursor
        else:
            if cur:
                spans.append(cur)
            cur = None
    if cur:
        spans.append(cur)

    return [(s, e, lb) for s, e, lb in spans if lb in ("PER", "LOC", "ORG")]


def _rule_entities(sentence):
    """Sinh các span theo luật: TME, DYNASTY, TITLE, LOC, PER, NUM."""
    spans = []
    for rx in _TME_RE:
        for m in rx.finditer(sentence):
            spans.append((m.start(), m.end(), "TME"))
    for m in _DYNASTY_RE.finditer(sentence):
        spans.append((m.start(), m.end(), "DYNASTY"))
    for m in _TITLE_RE.finditer(sentence):
        spans.append((m.start(), m.end(), "TITLE"))
    for m in _LOC_RE.finditer(sentence):
        spans.append((m.start(), m.end(), "LOC_RULE"))
    for m in _PER_RE.finditer(sentence):
        spans.append((m.start(1), m.end(1), "PER_RULE"))
    for rx, label in _GAZ_RES:
        for m in rx.finditer(sentence):
            spans.append((m.start(), m.end(), label))
    for m in _NUM_RE.finditer(sentence):
        spans.append((m.start(), m.end(), "NUM"))
    return spans


def extract_entities(sentence):
    """Trả về danh sách thực thể [{"text", "label"}] theo thứ tự xuất hiện."""
    candidates = _model_entities(sentence) + _rule_entities(sentence)
    # Span dài hơn thắng; bằng nhau thì theo độ ưu tiên
    candidates.sort(key=lambda c: (c[0], -(c[1] - c[0]), _PRIORITY.get(c[2], 9)))

    chosen = []
    for start, end, label in candidates:
        if any(start < e and end > s for s, e, _ in chosen):
            continue
        chosen.append((start, end, label))

    chosen.sort()
    result = []
    for start, end, label in chosen:
        label = {"LOC_RULE": "LOC", "PER_RULE": "PER",
                 "ORG_GAZ": "ORG", "PER_GAZ": "PER", "LOC_GAZ": "LOC"}.get(label, label)
        # Cắt dấu câu/khoảng trắng dính ở hai mép span
        text = sentence[start:end].strip(" ,.;:!?()[]\"'-")
        if not text:
            continue
        result.append({"text": text, "label": label})
    return result
