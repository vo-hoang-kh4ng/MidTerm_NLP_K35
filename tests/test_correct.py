import pytest


def test_pipeline_importable():
    import pipeline
    assert pipeline is not None


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
    cache = {}
    out, recs = correct_text("abcdefghij", client, "m", cache)
    assert out == "abcdefghij"
    assert recs[0]["action"] == "kept_original_length_guard"
    assert cache  # guard-failure vẫn được cache (ratio không đổi khi chạy lại)
    calls_after_first = client.calls
    out2, recs2 = correct_text("abcdefghij", client, "m", cache)
    assert out2 == "abcdefghij"
    assert recs2[0]["action"] == "cache_hit"
    assert client.calls == calls_after_first  # không gọi lại API


def test_correct_text_fallback_on_error():
    client = FakeClient(mapping={"boom": "boom"}, errors={"boom"})
    cache = {}
    out, recs = correct_text("boom", client, "m", cache)
    assert out == "boom"
    assert recs[0]["action"] == "fallback_error"
    assert cache == {}  # lỗi thì không cache


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


def test_gemini_generate_exhausts_retries_and_reraises():
    calls = {"n": 0}

    class Models:
        def generate_content(self, model, contents):
            calls["n"] += 1
            raise RuntimeError(f"rate limit {calls['n']}")

    class Underlying:
        models = Models()

    gc = _make_gemini_with_underlying(Underlying())
    sleep = FakeSleep()
    with pytest.raises(RuntimeError):
        gc.generate("p", "m", retries=3, sleep=sleep)
    assert calls["n"] == 3
    assert sleep.slept == [1, 2]


def test_write_corrections_jsonl(tmp_path):
    p = str(tmp_path / "c.jsonl")
    write_corrections(p, [{"original": "a", "corrected": "á", "action": "corrected"}])
    lines = open(p, encoding="utf-8").read().splitlines()
    assert len(lines) == 1
    assert _json.loads(lines[0])["corrected"] == "á"
