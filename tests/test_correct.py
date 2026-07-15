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
