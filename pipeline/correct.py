# -*- coding: utf-8 -*-
"""Hiệu đính lỗi OCR văn bản tiếng Việt bằng Google Gemini.

Chèn giữa bước chuẩn hóa và tách câu: sửa chính tả/dấu thanh và khôi phục
dấu câu ở mức đoạn văn để tách câu sạch hơn. Thiết kế cho phép tiêm client
(dependency injection) nên phần điều phối test được mà không gọi API thật.
"""

import hashlib
import json
import os
import time


def chunk_text(page_text, max_chars=2500):
    """Cắt text (đã normalize) thành các chunk <= max_chars theo ranh giới block.

    Không tách một block; block đơn dài hơn max_chars trở thành 1 chunk riêng.
    """
    blocks = [b for b in page_text.split("\n") if b.strip()]
    chunks = []
    buf = []
    size = 0
    for b in blocks:
        add = len(b) + (1 if buf else 0)  # +1 cho "\n" nối
        if buf and size + add > max_chars:
            chunks.append("\n".join(buf))
            buf, size = [], 0
            add = len(b)
        buf.append(b)
        size += add
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def within_length_guard(original, corrected, max_ratio=0.3):
    """True nếu độ dài bản sửa lệch <= max_ratio so với gốc và không rỗng."""
    if not corrected.strip():
        return False
    base = max(len(original), 1)
    return abs(len(corrected) - len(original)) / base <= max_ratio


def cache_key(model, chunk):
    """SHA-256 hex của (model, chunk) — khóa cache ổn định, phân biệt model."""
    return hashlib.sha256((model + "\n" + chunk).encode("utf-8")).hexdigest()


def load_cache(path):
    """Đọc cache JSON; thiếu file hoặc hỏng -> {}."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(path, cache):
    """Ghi cache ra JSON UTF-8, tạo thư mục cha nếu cần."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# Bảng tên riêng/thuật ngữ viết đúng, dùng làm tài liệu đối chiếu trong prompt
# Gemini chỉ dùng khi gặp chuỗi OCR méo giống mục nào đó; tên không xuất hiện
# trong đoạn văn thì không ảnh hưởng.
GLOSSARY = [
    # Truyền thuyết / thời dựng nước
    "Hùng Vương", "Văn Lang", "Âu Lạc", "Lạc Việt", "Lạc hầu", "Lạc tướng",
    "Kinh Dương Vương", "Lạc Long Quân", "Âu Cơ", "An Dương Vương",
    "Sơn Tinh", "Thủy Tinh", "Thánh Gióng", "Chử Đồng Tử", "Tản Viên",
    # Khảo cổ học
    "Đông Sơn", "Phùng Nguyên", "Gò Mun", "Đồng Đậu", "trống đồng",
    "Núi Đọ", "Đa Bút", "Thiệu Dương", "Đông Khối", "Việt Khê", "Lũng Hòa",
    "Viện Khảo cổ học", "Viện Sử học", "Viện Bảo tàng Lịch sử",
    "Ủy ban Khoa học Xã hội Việt Nam",
    # Sử trung-cận đại
    "Đại Việt", "Đại Cồ Việt", "Đại Nam", "Chiêm Thành", "Chân Lạp",
    "Thăng Long", "Phú Xuân", "Gia Định", "Đàng Trong", "Đàng Ngoài",
    "Lê Lợi", "Lam Sơn", "Nguyễn Trãi", "Lê Thánh Tông", "Quang Trung",
    "Tây Sơn", "Gia Long", "Minh Mạng", "Tự Đức",
    # Thư tịch cổ
    "Lĩnh Nam chích quái", "Việt điện u linh", "Đại Việt sử ký toàn thư",
    "Việt sử thông giám cương mục", "Lịch triều hiến chương loại chí",
    "Dư địa chí", "Phủ biên tạp lục",
]

CORRECTION_PROMPT = (
    "Bạn là công cụ hiệu đính lỗi OCR cho văn bản lịch sử tiếng Việt. "
    "Hãy sửa: lỗi chính tả, sai dấu thanh, từ bị dính hoặc tách sai, ký tự "
    "ngoại lai lẫn vào (chữ Hán/Nhật, Kirin, ký hiệu rác), và khôi phục dấu "
    "chấm ở cuối câu. TUYỆT ĐỐI KHÔNG dịch, KHÔNG tóm tắt, KHÔNG thêm/bớt "
    "hay diễn giải nội dung, KHÔNG đổi văn phong. Giữ nguyên tên riêng, số, "
    "năm và niên hiệu, trừ khi chúng rõ ràng là ký tự OCR bị méo. GIỮ NGUYÊN "
    "chính tả cũ có gạch nối của sách in xưa (Lam-Sơn, Nghệ-An, Thái-Tổ...), "
    "phiên âm gạch nối (Béc-lin, Lê-nin-grát) và mã hiệu (C14, M12) — không "
    "hiện đại hóa chúng. "
    "Chỉ trả về đúng văn bản đã sửa, không kèm lời dẫn hay giải thích.\n\n"
    "Tên riêng/thuật ngữ viết đúng để đối chiếu khi khôi phục chữ OCR méo: "
    + "; ".join(GLOSSARY) + ".\n\n"
    "Văn bản cần sửa:\n"
)


def build_prompt(chunk):
    """Ghép chỉ dẫn hiệu đính với đoạn văn cần sửa."""
    return CORRECTION_PROMPT + chunk


def correct_text(page_text, client, model, cache, max_ratio=0.3):
    """Hiệu đính text một trang theo từng chunk; trả (text_đã_sửa, records)."""
    out_parts = []
    records = []
    for chunk in chunk_text(page_text):
        key = cache_key(model, chunk)
        if key in cache:
            corrected, action = cache[key], "cache_hit"
        else:
            try:
                resp = client.generate(build_prompt(chunk), model)
            except Exception:
                corrected, action = chunk, "fallback_error"
            else:
                if within_length_guard(chunk, resp, max_ratio):
                    corrected, action = resp, "corrected"
                else:
                    corrected, action = chunk, "kept_original_length_guard"
                cache[key] = corrected
        out_parts.append(corrected)
        records.append({"original": chunk, "corrected": corrected, "action": action})
    return "\n".join(out_parts), records


class GeminiClient:
    """Adapter mỏng quanh SDK google-genai (import lười để test không cần SDK)."""

    def __init__(self, api_key):
        from google import genai  # lazy: chỉ cần khi chạy thật
        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt, model, retries=3, sleep=time.sleep):
        last = None
        for attempt in range(retries):
            try:
                resp = self._client.models.generate_content(
                    model=model, contents=prompt
                )
                return resp.text
            except Exception as e:  # rate-limit/mạng -> backoff rồi thử lại
                last = e
                if attempt < retries - 1:
                    sleep(2 ** attempt)
        raise last


def write_corrections(path, records):
    """Ghi danh sách record ra file JSONL (mỗi dòng một JSON), UTF-8."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
