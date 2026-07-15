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


CORRECTION_PROMPT = (
    "Bạn là công cụ hiệu đính lỗi OCR cho văn bản lịch sử tiếng Việt. "
    "Hãy sửa: lỗi chính tả, sai dấu thanh, từ bị dính hoặc tách sai, và "
    "khôi phục dấu chấm ở cuối câu. TUYỆT ĐỐI KHÔNG dịch, KHÔNG tóm tắt, "
    "KHÔNG thêm/bớt hay diễn giải nội dung, KHÔNG đổi văn phong. Giữ nguyên "
    "tên riêng, số, năm và niên hiệu, trừ khi chúng rõ ràng là ký tự OCR bị méo. "
    "Chỉ trả về đúng văn bản đã sửa, không kèm lời dẫn hay giải thích.\n\n"
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
