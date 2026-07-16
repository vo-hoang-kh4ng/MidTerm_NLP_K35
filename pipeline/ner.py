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

# Cho phép nối âm tiết bằng gạch nối kiểu chính tả cũ: "Nguyễn-vương", "Gia-định"
_CAPWORD = rf"[{_UP}][{_LO}]+(?:-[{_LO}]+)*"
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


def _flex(phrase):
    """Cho phép khoảng trắng HOẶC gạch nối giữa các âm tiết của một cụm từ,
    để khớp cả chính tả hiện đại ("tri phủ") lẫn chính tả cũ ("tri-phủ")."""
    return r"[ -]".join(re.escape(w) for w in phrase.split(" "))


_TITLE_ALTS = [_flex(t) for t in _TITLES]
_TITLE_RE = re.compile(
    r"\b(?:" + "|".join(_TITLE_ALTS) + r")\b",
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
# (?<!-): tránh khớp nhầm khi từ chỉ loại là nửa sau một từ ghép gạch nối
# thuộc chức danh, ví dụ "tri-phủ" (chức quan) không phải "phủ" (địa danh).
_LOC_RE = re.compile(rf"(?<!-)\b(?:{_LOC_CUES})\s+{_CAPSEQ}")

# ---------------------------------------------------------------------------
# Nhân danh sau chức danh (bổ trợ PER): "vua Lê Thánh Tông", "tướng Trần..."
# Dùng chung bộ từ điển chức danh (_TITLES) cộng thêm vài đại từ chỉ người.
# ---------------------------------------------------------------------------
_PER_CUES_EXTRA = ["ông", "bà", "họ", "tướng", "quan"]
_PER_ALT = "|".join(_TITLE_ALTS + [re.escape(w) for w in _PER_CUES_EXTRA])
# Không dùng IGNORECASE: {_CAPSEQ} dựa vào phân biệt hoa/thường để nhận diện
# tên riêng, bật IGNORECASE sẽ khiến nó khớp nhầm cả cụm từ thường.
_PER_RE = re.compile(rf"(?i:\b(?:{_PER_ALT})\b)\s*,?\s+({_CAPSEQ})")

# ---------------------------------------------------------------------------
# Sửa nhãn: mô hình chung hay gán nhầm người có chức danh thành LOC/ORG
# ("Đô đốc Pagiơ" -> LOC). Nếu span (hoặc phần ngay trước span) bắt đầu/kết
# thúc bằng một chức danh đã biết, coi phần tên còn lại là PER.
# ---------------------------------------------------------------------------
_TITLE_PREFIX_RE = re.compile(
    r"^(?:" + _PER_ALT + r")\b[\s,]+", re.IGNORECASE
)
_TITLE_BEFORE_RE = re.compile(
    r"(?:" + _PER_ALT + r")\s*,?\s*$", re.IGNORECASE
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


def _retitle_person(sentence, start, end, label):
    """LOC/ORG mà chính span hoặc phần ngay trước nó là một chức danh
    -> coi phần tên là PER (mô hình chung hay gán nhầm các trường hợp này)."""
    if label not in ("LOC", "ORG"):
        return start, end, label
    text = sentence[start:end]
    m = _TITLE_PREFIX_RE.match(text)
    if m and m.end() < len(text):
        return start + m.end(), end, "PER"
    if _TITLE_BEFORE_RE.search(sentence[:start]):
        return start, end, "PER"
    return start, end, label


def _trim_internal_punct(text):
    """Cắt span tại dấu phẩy/chấm phẩy nằm giữa (không phải ở mép), giữ lại
    phần sau cùng — sửa lỗi mô hình đôi khi gộp span qua ranh giới câu con."""
    for ch in (",", ";"):
        idx = text.rfind(ch)
        if 0 < idx < len(text) - 1:
            text = text[idx + 1:]
    return text.strip(" ,.;:!?()[]\"'-")


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
        start, end, label = _retitle_person(sentence, start, end, label)
        # Cắt dấu câu/khoảng trắng dính ở hai mép span
        text = _trim_internal_punct(sentence[start:end].strip(" ,.;:!?()[]\"'-"))
        if not text:
            continue
        result.append({"text": text, "label": label})
    return result
