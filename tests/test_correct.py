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
