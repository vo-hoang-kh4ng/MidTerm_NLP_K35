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

_CAPWORD = rf"[{_UP}][{_LO}]+"
_CAPSEQ = rf"{_CAPWORD}(?:\s+{_CAPWORD})*"

_CAN = "Giáp|Ất|Bính|Đinh|Mậu|Kỷ|Canh|Tân|Nhâm|Quý"
_CHI = "Tý|Sửu|Dần|Mão|Mẹo|Thìn|Tỵ|Ngọ|Mùi|Thân|Dậu|Tuất|Hợi"
_CANCHI = rf"(?:{_CAN})\s+(?:{_CHI})"

# ---------------------------------------------------------------------------
# Luật thời gian (TME)
# ---------------------------------------------------------------------------
_TME_PATTERNS = [
    rf"[Nn]gày\s+(?:mồng\s+|mùng\s+)?(?:\d{{1,2}}|{_CANCHI})\b",
    rf"[Tt]háng\s+(?:\d{{1,2}}|[Gg]iêng|[Cc]hạp)(?:\s+nhuận)?\b",
    rf"[Nn]ăm\s+{_CAPSEQ}\s+thứ\s+\d+\b",          # năm Hồng Đức thứ 2
    rf"[Nn]ăm\s+(?:\d{{3,4}}|{_CANCHI})\b",
    rf"[Nn]iên\s?hiệu\s+{_CAPSEQ}(?:\s+thứ\s+\d+)?\b",
    rf"[Đđ]ời\s+(?:vua\s+|chúa\s+)?{_CAPSEQ}\b",
    r"[Mm]ùa\s+(?:xuân|hạ|thu|đông)\b",
    r"[Tt]hế\s?kỷ\s+(?:thứ\s+)?[IVX\d]+\b",
    r"[Gg]iờ\s+(?:" + _CHI + r")\b",
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
    "điện|thành|phủ|huyện|xã|thôn|làng|trấn|đạo|lộ|châu|phường|tổng|hạt|"
    "sông|núi|hồ|đầm|cửa biển|cửa|đèo|đảo|chùa|đền|miếu|quán|cầu|chợ|bến|"
    "kinh đô|kinh thành|nước|xứ|động|nguồn|ải|cung|lầu|gác|hành cung"
)
_LOC_RE = re.compile(rf"\b(?:{_LOC_CUES})\s+{_CAPSEQ}")

# ---------------------------------------------------------------------------
# Nhân danh sau chức danh (bổ trợ PER): "vua Lê Thánh Tông", "tướng Trần..."
# ---------------------------------------------------------------------------
_PER_RE = re.compile(
    rf"\b(?:vua|chúa|ông|bà|họ|tướng|quan|công chúa|hoàng hậu|thái tử)\s+({_CAPSEQ})"
)

# ---------------------------------------------------------------------------
# Số lượng (NUM)
# ---------------------------------------------------------------------------
_NUM_UNITS = "vạn|ức|nghìn|ngàn|trăm|dặm|trượng|thước|tấc|mẫu|sào|quan|hộc|thạch|cân|lạng|người|năm|tháng|ngày|đời|chiếc|con|quyển|đạo|viên"
_NUM_RE = re.compile(rf"\b\d+(?:[.,]\d+)*(?:\s+(?:{_NUM_UNITS})\b)?")

# Độ ưu tiên khi span bằng độ dài (số nhỏ = ưu tiên cao)
_PRIORITY = {"TME": 0, "DYNASTY": 1, "TITLE": 2, "PER": 3, "LOC": 3, "ORG": 3,
             "LOC_RULE": 4, "PER_RULE": 5, "NUM": 6}


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
        label = {"LOC_RULE": "LOC", "PER_RULE": "PER"}.get(label, label)
        # Cắt dấu câu/khoảng trắng dính ở hai mép span
        text = sentence[start:end].strip(" ,.;:!?()[]\"'-")
        if not text:
            continue
        result.append({"text": text, "label": label})
    return result
