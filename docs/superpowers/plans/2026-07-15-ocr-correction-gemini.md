# Gemini OCR Correction Stage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm một stage hiệu đính OCR bằng Google Gemini, chèn giữa `normalize` và `segment`, để sửa lỗi chính tả và khôi phục dấu câu ở mức đoạn văn.

**Architecture:** Module mới `pipeline/correct.py` cung cấp hàm thuần (`chunk_text`, guard độ dài, cache) và hàm điều phối `correct_text(page_text, client, model, cache)` nhận **client được tiêm vào** (dependency injection) nên test được không cần API. Adapter `GeminiClient` bọc SDK `google-genai`. `main.py` thêm cờ `--correct/--model/--no-cache` và chỉ chạy stage khi bật.

**Tech Stack:** Python 3.10, `google-genai` (SDK GenAI mới), `pytest` (test), pipeline hiện có (PyMuPDF, underthesea).

## Global Constraints

- Ngôn ngữ ngữ liệu: tiếng Việt lịch sử — hiệu đính **chỉ sửa lỗi OCR**, không dịch/tóm tắt/đổi tên riêng.
- **Backward-compatible:** khi không truyền `--correct`, hành vi `main.py` phải y hệt hiện tại.
- Guard độ dài: bản sửa lệch **> 30%** độ dài so với gốc → **giữ bản gốc**.
- Cache theo **SHA-256** của `model + "\n" + chunk`, lưu `output/cache/gemini.json`.
- Pipeline **không bao giờ crash** vì lỗi API: retry backoff rồi fallback về text gốc.
- Secret qua env `GEMINI_API_KEY`. SDK dùng dạng mới: `from google import genai`.
- Model flash mặc định: `gemini-2.5-flash` (đổi được qua `--model`).
- Chunk mặc định ~2500 ký tự, **không cắt giữa một block** (`\n` từ normalize là ranh giới).
- Mọi lệnh chạy từ thư mục repo: `/home/anlnm/anlnm/ocr/MidTerm_NLP_K35`.

---

## File Structure

- Create: `pipeline/correct.py` — toàn bộ logic hiệu đính (chunk, guard, cache, prompt, orchestration, adapter, ghi corrections).
- Create: `tests/test_correct.py` — unit test các hàm thuần + orchestration với client giả.
- Create: `conftest.py` (root) — để pytest thêm repo root vào `sys.path` (import được `pipeline`).
- Create: `requirements-dev.txt` — `pytest`.
- Modify: `requirements.txt` — thêm `google-genai`.
- Modify: `main.py` — cờ mới + nối stage + ghi `_corrections.jsonl`.
- Modify: `CLAUDE.md` — tài liệu cờ mới.

---

### Task 1: Project setup (deps + test harness)

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `conftest.py`
- Create: `tests/test_correct.py` (chỉ 1 test smoke tạm)

**Interfaces:**
- Consumes: —
- Produces: `tests/` chạy được bằng `pytest`; `pipeline` import được từ test.

- [ ] **Step 1: Thêm dependency runtime**

Sửa `requirements.txt` thành:

```
PyMuPDF
underthesea
google-genai
```

- [ ] **Step 2: Tạo `requirements-dev.txt`**

```
pytest
```

- [ ] **Step 3: Tạo `conftest.py` (root, rỗng)**

File rỗng tại `/home/anlnm/anlnm/ocr/MidTerm_NLP_K35/conftest.py` để pytest thêm repo root vào `sys.path`:

```python
# Đặt ở root để pytest thêm thư mục này vào sys.path, cho phép "import pipeline".
```

- [ ] **Step 4: Tạo test smoke tạm `tests/test_correct.py`**

```python
def test_pipeline_importable():
    import pipeline
    assert pipeline is not None
```

- [ ] **Step 5: Cài và chạy test**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
pip3 install -r requirements-dev.txt
python3 -m pytest tests/ -v
```
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
git add requirements.txt requirements-dev.txt conftest.py tests/test_correct.py
git commit -m "chore: add google-genai dep and pytest harness"
```

---

### Task 2: `chunk_text` — cắt đoạn theo ranh giới block

**Files:**
- Create: `pipeline/correct.py`
- Test: `tests/test_correct.py`

**Interfaces:**
- Consumes: —
- Produces: `chunk_text(page_text: str, max_chars: int = 2500) -> list[str]`
  Cắt theo dòng (`\n`); gộp các block đến khi vượt `max_chars` thì mở chunk mới;
  không tách một block; block đơn lớn hơn `max_chars` thành 1 chunk riêng.
  Bỏ qua dòng rỗng. Trả về list rỗng nếu input rỗng/trắng.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_correct.py`:

```python
from pipeline.correct import chunk_text


def test_chunk_groups_blocks_until_limit():
    text = "aaa\nbbb\nccc\nddd"  # 4 block, mỗi block 3 ký tự
    chunks = chunk_text(text, max_chars=8)
    # "aaa\nbbb" = 7 ký tự (<=8); thêm "\nccc" -> 11 (>8) nên tách
    assert chunks == ["aaa\nbbb", "ccc\nddd"]


def test_chunk_keeps_oversized_block_whole():
    big = "x" * 30
    chunks = chunk_text("short\n" + big, max_chars=10)
    assert "short" in chunks[0]
    assert big in chunks  # block lớn không bị cắt


def test_chunk_empty_returns_empty():
    assert chunk_text("   \n  \n") == []
```

- [ ] **Step 2: Chạy test để chắc chắn fail**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k chunk -v
```
Expected: FAIL với `ImportError: cannot import name 'chunk_text'`.

- [ ] **Step 3: Cài đặt tối thiểu**

Tạo `pipeline/correct.py`:

```python
# -*- coding: utf-8 -*-
"""Hiệu đính lỗi OCR văn bản tiếng Việt bằng Google Gemini.

Chèn giữa bước chuẩn hóa và tách câu: sửa chính tả/dấu thanh và khôi phục
dấu câu ở mức đoạn văn để tách câu sạch hơn. Thiết kế cho phép tiêm client
(dependency injection) nên phần điều phối test được mà không gọi API thật.
"""


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
```

- [ ] **Step 4: Chạy test để chắc chắn pass**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k chunk -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
git add pipeline/correct.py tests/test_correct.py
git commit -m "feat: add chunk_text for OCR correction stage"
```

---

### Task 3: Guard độ dài + cache key

**Files:**
- Modify: `pipeline/correct.py`
- Test: `tests/test_correct.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `within_length_guard(original: str, corrected: str, max_ratio: float = 0.3) -> bool`
    Trả `True` nếu `abs(len(corrected)-len(original)) / max(len(original),1) <= max_ratio`
    **và** `corrected.strip()` không rỗng.
  - `cache_key(model: str, chunk: str) -> str` — SHA-256 hex của `model + "\n" + chunk`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_correct.py`:

```python
from pipeline.correct import within_length_guard, cache_key


def test_guard_accepts_small_change():
    assert within_length_guard("Viet Nam ta", "Việt Nam ta") is True


def test_guard_rejects_big_shrink():
    assert within_length_guard("x" * 100, "x" * 50) is False


def test_guard_rejects_empty():
    assert within_length_guard("abc", "   ") is False


def test_cache_key_stable_and_model_sensitive():
    k1 = cache_key("gemini-2.5-flash", "abc")
    k2 = cache_key("gemini-2.5-flash", "abc")
    k3 = cache_key("gemini-2.5-pro", "abc")
    assert k1 == k2 and k1 != k3 and len(k1) == 64
```

- [ ] **Step 2: Chạy test để chắc chắn fail**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k "guard or cache_key" -v
```
Expected: FAIL với `ImportError`.

- [ ] **Step 3: Cài đặt tối thiểu**

Thêm vào đầu `pipeline/correct.py` (sau docstring) và cuối file:

```python
import hashlib
```

```python
def within_length_guard(original, corrected, max_ratio=0.3):
    """True nếu độ dài bản sửa lệch <= max_ratio so với gốc và không rỗng."""
    if not corrected.strip():
        return False
    base = max(len(original), 1)
    return abs(len(corrected) - len(original)) / base <= max_ratio


def cache_key(model, chunk):
    """SHA-256 hex của (model, chunk) — khóa cache ổn định, phân biệt model."""
    return hashlib.sha256((model + "\n" + chunk).encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Chạy test để chắc chắn pass**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k "guard or cache_key" -v
```
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
git add pipeline/correct.py tests/test_correct.py
git commit -m "feat: add length guard and cache key helpers"
```

---

### Task 4: Cache đọc/ghi ra đĩa

**Files:**
- Modify: `pipeline/correct.py`
- Test: `tests/test_correct.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `load_cache(path: str) -> dict` — đọc JSON; file thiếu/hỏng → trả `{}`.
  - `save_cache(path: str, cache: dict) -> None` — tạo thư mục cha nếu cần, ghi JSON UTF-8.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_correct.py`:

```python
from pipeline.correct import load_cache, save_cache


def test_cache_roundtrip(tmp_path):
    p = str(tmp_path / "sub" / "gemini.json")
    save_cache(p, {"k": "đã sửa"})
    assert load_cache(p) == {"k": "đã sửa"}


def test_load_missing_returns_empty(tmp_path):
    assert load_cache(str(tmp_path / "none.json")) == {}


def test_load_corrupt_returns_empty(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_cache(str(p)) == {}
```

- [ ] **Step 2: Chạy test để chắc chắn fail**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k cache -v
```
Expected: FAIL với `ImportError` cho `load_cache`.

- [ ] **Step 3: Cài đặt tối thiểu**

Thêm `import json` và `import os` vào phần import của `pipeline/correct.py`, rồi thêm:

```python
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
```

- [ ] **Step 4: Chạy test để chắc chắn pass**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k cache -v
```
Expected: PASS (test_cache_roundtrip, test_load_missing_returns_empty, test_load_corrupt_returns_empty, và test_cache_key_* từ Task 3).

- [ ] **Step 5: Commit**

```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
git add pipeline/correct.py tests/test_correct.py
git commit -m "feat: add on-disk cache load/save for corrections"
```

---

### Task 5: Prompt + orchestration `correct_text`

**Files:**
- Modify: `pipeline/correct.py`
- Test: `tests/test_correct.py`

**Interfaces:**
- Consumes: `chunk_text`, `within_length_guard`, `cache_key` (các Task trước).
- Produces:
  - `build_prompt(chunk: str) -> str` — ghép chỉ dẫn hiệu đính (hằng `CORRECTION_PROMPT`) với chunk.
  - `correct_text(page_text, client, model, cache, max_ratio=0.3) -> tuple[str, list[dict]]`
    Với mỗi chunk: nếu `cache_key` có trong `cache` → dùng lại (`action="cache_hit"`);
    ngược lại gọi `client.generate(prompt, model)`:
      - lỗi exception → `corrected=chunk`, `action="fallback_error"`, **không cache**;
      - qua guard → `action="corrected"`, cache lại;
      - trượt guard → `corrected=chunk`, `action="kept_original_length_guard"`, cache lại.
    Trả `("\n".join(các phần), records)`; mỗi record = `{"original","corrected","action"}`.
    `client` là bất kỳ object có method `generate(prompt: str, model: str) -> str`.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_correct.py`:

```python
from pipeline.correct import build_prompt, correct_text


class FakeClient:
    """Client giả: trả về theo map, hoặc raise nếu chunk nằm trong `errors`."""
    def __init__(self, mapping=None, errors=None):
        self.mapping = mapping or {}
        self.errors = errors or set()
        self.calls = 0

    def generate(self, prompt, model):
        self.calls += 1
        for original, corrected in self.mapping.items():
            if original in prompt:
                if original in self.errors:
                    raise RuntimeError("api down")
                return corrected
        return prompt  # không đổi


def test_build_prompt_contains_chunk_and_rules():
    p = build_prompt("Vỉệt Nam")
    assert "Vỉệt Nam" in p
    assert "OCR" in p


def test_correct_text_applies_correction_and_caches():
    client = FakeClient(mapping={"Vỉệt Nam": "Việt Nam"})
    cache = {}
    out, recs = correct_text("Vỉệt Nam", client, "m", cache)
    assert out == "Việt Nam"
    assert recs[0]["action"] == "corrected"
    # lần 2 dùng cache, không gọi thêm
    out2, recs2 = correct_text("Vỉệt Nam", client, "m", cache)
    assert out2 == "Việt Nam" and recs2[0]["action"] == "cache_hit"
    assert client.calls == 1


def test_correct_text_guard_keeps_original():
    client = FakeClient(mapping={"abcdefghij": "x"})  # rút ngắn quá nhiều
    out, recs = correct_text("abcdefghij", client, "m", {})
    assert out == "abcdefghij"
    assert recs[0]["action"] == "kept_original_length_guard"


def test_correct_text_fallback_on_error():
    client = FakeClient(mapping={"boom": "boom"}, errors={"boom"})
    cache = {}
    out, recs = correct_text("boom", client, "m", cache)
    assert out == "boom"
    assert recs[0]["action"] == "fallback_error"
    assert cache == {}  # lỗi thì không cache
```

- [ ] **Step 2: Chạy test để chắc chắn fail**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k "prompt or correct_text" -v
```
Expected: FAIL với `ImportError` cho `build_prompt`.

- [ ] **Step 3: Cài đặt tối thiểu**

Thêm vào `pipeline/correct.py`:

```python
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
```

- [ ] **Step 4: Chạy test để chắc chắn pass**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -v
```
Expected: PASS (toàn bộ test tính đến giờ).

- [ ] **Step 5: Commit**

```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
git add pipeline/correct.py tests/test_correct.py
git commit -m "feat: add prompt and correct_text orchestration"
```

---

### Task 6: Adapter `GeminiClient` + ghi corrections

**Files:**
- Modify: `pipeline/correct.py`
- Test: `tests/test_correct.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `class GeminiClient` với `__init__(self, api_key)` (lazy import SDK) và
    `generate(self, prompt, model, retries=3, sleep=time.sleep) -> str` — gọi
    `self._client.models.generate_content(model=model, contents=prompt).text`,
    retry backoff `2**attempt` giây, ném exception sau khi hết lượt.
  - `write_corrections(path, records) -> None` — ghi mỗi record 1 dòng JSON (JSONL), UTF-8.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_correct.py`:

```python
import json as _json
from pipeline.correct import GeminiClient, write_corrections


class FakeSleep:
    def __init__(self):
        self.slept = []

    def __call__(self, s):
        self.slept.append(s)


def _make_gemini_with_underlying(underlying):
    """Tạo GeminiClient nhưng thay _client bằng đối tượng giả (không cần SDK/API)."""
    gc = GeminiClient.__new__(GeminiClient)
    gc._client = underlying
    return gc


def test_gemini_generate_returns_text():
    class Resp:
        text = "đã sửa"

    class Models:
        def generate_content(self, model, contents):
            return Resp()

    class Underlying:
        models = Models()

    gc = _make_gemini_with_underlying(Underlying())
    assert gc.generate("p", "m") == "đã sửa"


def test_gemini_generate_retries_then_succeeds():
    calls = {"n": 0}

    class Models:
        def generate_content(self, model, contents):
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("rate limit")
            class R: text = "ok"
            return R()

    class Underlying:
        models = Models()

    gc = _make_gemini_with_underlying(Underlying())
    sleep = FakeSleep()
    assert gc.generate("p", "m", retries=3, sleep=sleep) == "ok"
    assert calls["n"] == 2 and len(sleep.slept) == 1


def test_write_corrections_jsonl(tmp_path):
    p = str(tmp_path / "c.jsonl")
    write_corrections(p, [{"original": "a", "corrected": "á", "action": "corrected"}])
    lines = open(p, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    assert _json.loads(lines[0])["corrected"] == "á"
```

- [ ] **Step 2: Chạy test để chắc chắn fail**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -k "gemini or write_corrections" -v
```
Expected: FAIL với `ImportError` cho `GeminiClient`.

- [ ] **Step 3: Cài đặt tối thiểu**

Thêm `import time` vào phần import của `pipeline/correct.py`, rồi thêm:

```python
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
```

- [ ] **Step 4: Chạy test để chắc chắn pass**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/test_correct.py -v
```
Expected: PASS (tất cả).

- [ ] **Step 5: Commit**

```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
git add pipeline/correct.py tests/test_correct.py
git commit -m "feat: add GeminiClient adapter and JSONL corrections writer"
```

---

### Task 7: Nối stage vào `main.py` + tài liệu

**Files:**
- Modify: `main.py`
- Modify: `CLAUDE.md`
- Test: chạy tay backward-compat (không API) + smoke có API (thủ công).

**Interfaces:**
- Consumes: `correct_text`, `GeminiClient`, `load_cache`, `save_cache`, `write_corrections`.
- Produces: hành vi CLI mới (cờ `--correct`, `--model`, `--no-cache`).

- [ ] **Step 1: Thêm import và cờ CLI**

Trong `main.py`, thêm `import os` (nếu chưa có) và import stage:

```python
from pipeline.correct import (
    correct_text, GeminiClient, load_cache, save_cache, write_corrections,
)
```

Trong `parse_args()`, thêm trước `return p.parse_args()`:

```python
    p.add_argument("--correct", action="store_true",
                   help="Bật hiệu đính OCR bằng Gemini trước khi tách câu")
    p.add_argument("--model", default="gemini-2.5-flash",
                   help="Model Gemini dùng khi --correct")
    p.add_argument("--no-cache", action="store_true",
                   help="Không dùng cache hiệu đính (luôn gọi API)")
```

- [ ] **Step 2: Khởi tạo client + cache khi bật --correct**

Trong `main()`, ngay sau `outdir.mkdir(...)`, thêm:

```python
    corr_client = corr_cache = None
    corr_records = []
    cache_path = str(outdir / "cache" / "gemini.json")
    if args.correct:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            sys.exit("Thiếu GEMINI_API_KEY. Đặt: export GEMINI_API_KEY=...")
        corr_client = GeminiClient(api_key)
        corr_cache = {} if args.no_cache else load_cache(cache_path)
        print(f"[+] Hiệu đính OCR bằng Gemini ({args.model})")
```

- [ ] **Step 3: Nối stage vào vòng lặp trang**

Trong `main()`, thay đoạn dựng `sentences` hiện tại:

```python
    sentences = []
    for page_no, raw in pages:
        clean = normalize_page_text(raw)
        if clean:
            sentences.extend(split_sentences(clean))
```

bằng:

```python
    sentences = []
    for page_no, raw in pages:
        clean = normalize_page_text(raw)
        if not clean:
            continue
        if args.correct:
            clean, recs = correct_text(clean, corr_client, args.model, corr_cache)
            corr_records.extend(recs)
        sentences.extend(split_sentences(clean))
```

- [ ] **Step 4: Lưu cache + ghi corrections sau vòng lặp**

Trong `main()`, ngay sau vòng `for` tách câu (trước `if args.limit:`), thêm:

```python
    if args.correct:
        if not args.no_cache:
            save_cache(cache_path, corr_cache)
        corr_path = outdir / f"{args.code}_corrections.jsonl"
        write_corrections(str(corr_path), corr_records)
        print(f"      -> {len(corr_records)} đoạn hiệu đính: {corr_path}")
```

- [ ] **Step 5: Kiểm backward-compat (không API, không --correct)**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
mapfile -t P < <(ls data/*.pdf)
python3 main.py --pdf "${P[0]}" --code TMP_COMPAT --limit 20 --outdir /tmp/compat_out
ls /tmp/compat_out
```
Expected: tạo `TMP_COMPAT_sentences.txt` và `TMP_COMPAT_ner.json`, không lỗi, không cần key.

- [ ] **Step 6: Smoke có hiệu đính (thủ công, cần key)**

Run (chỉ khi có `GEMINI_API_KEY`):
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
export GEMINI_API_KEY=...          # key thật của bạn
mapfile -t P < <(ls data/*.pdf)
python3 main.py --pdf "${P[1]}" --code HVQ_036_TTLS_corr --correct --limit 40
head -c 600 output/HVQ_036_TTLS_corr_corrections.jsonl
```
Expected: sinh `HVQ_036_TTLS_corr_sentences.txt`, `_ner.json`, `_corrections.jsonl`;
soi vài cặp `original→corrected` thấy sửa đúng lỗi tiêu biểu, không đổi tên riêng.
(Nếu chưa có key: bỏ qua bước này, đã có test đơn vị cho logic.)

- [ ] **Step 7: Cập nhật `CLAUDE.md`**

Trong phần Commands của `CLAUDE.md`, thêm sau khối lệnh chạy hiện có:

```markdown
Bật hiệu đính OCR bằng Gemini (cần `GEMINI_API_KEY`), chạy trước bước tách câu:

​```bash
export GEMINI_API_KEY=...
python3 main.py --pdf <file.pdf> --code <MÃ>_corr --correct [--model gemini-2.5-flash] [--no-cache]
​```

Thêm output khi bật `--correct`: `<MÃ>_corr_corrections.jsonl` (cặp đoạn gốc→đã sửa)
và cache `output/cache/gemini.json` (tái lập, tránh gọi lại API).
```

Trong phần Architecture, thêm một gạch đầu dòng mô tả `pipeline/correct.py` (stage tùy chọn
giữa normalize và segment, guard độ dài 30%, cache theo hash, fallback khi lỗi API).

- [ ] **Step 8: Chạy lại toàn bộ test + commit**

Run:
```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
python3 -m pytest tests/ -v
```
Expected: PASS (tất cả).

```bash
cd /home/anlnm/anlnm/ocr/MidTerm_NLP_K35
git add main.py CLAUDE.md
git commit -m "feat: wire Gemini OCR correction into main pipeline"
```

---

## Self-Review

**Spec coverage:**
- Mục tiêu sửa chính tả + khôi phục dấu câu → prompt (Task 5) + đặt trước segment (Task 7). ✅
- Trước tách câu, mức đoạn → `chunk_text` + wiring (Task 2, 7). ✅
- Model flash mặc định + `--model` → Task 7 Step 1. ✅
- Guard 30% → Task 3 + dùng trong Task 5. ✅
- Cache hash + tái lập → Task 3 (key), Task 4 (đĩa), Task 7 (nạp/lưu). ✅
- Fallback không crash + retry backoff → Task 5 (fallback), Task 6 (retry). ✅
- Provenance code riêng + `_corrections.jsonl` → Task 6 (writer), Task 7 (đường ra). ✅
- Thiếu key → dừng sớm → Task 7 Step 2. ✅
- `google-genai` vào requirements → Task 1. ✅
- Backward-compat → Task 7 Step 5. ✅
- Unit test guard với client mock → Task 5 (FakeClient). ✅

**Placeholder scan:** không còn TODO/TBD; mọi step có code/lệnh cụ thể. ✅

**Type consistency:** `correct_text(page_text, client, model, cache, max_ratio)` dùng nhất quán
Task 5 và Task 7; `client.generate(prompt, model)` khớp giữa `FakeClient`, `GeminiClient`, và
lời gọi trong `correct_text`; `records` gồm khóa `original/corrected/action` dùng thống nhất
ở `correct_text`, `write_corrections`, và test. ✅
