# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Vietnamese NLP pipeline that turns an OCR'd historical PDF (the book *Lịch triều hiến chương loại chí*) into cleaned sentences and named-entity annotations. The pipeline is: **PDF → text extraction → normalization → sentence segmentation → NER → JSON**.

## Commands

```bash
# Full run (defaults to the bundled book, code HVQ_036, auto page detection)
python main.py --pdf <file.pdf>

# Quick smoke test on the first N sentences
python main.py --pdf <file.pdf> --limit 200

# Force a page range instead of bookmark auto-detection
python main.py --pdf <file.pdf> --start-page 30 --end-page 500

# Custom work code + output dir (affects sentence_id prefix and filenames)
python main.py --pdf <file.pdf> --code HVQ_036 --outdir output
```

Bật hiệu đính OCR bằng Gemini (cần `GEMINI_API_KEY`), chạy trước bước tách câu:

```bash
export GEMINI_API_KEY=...
python3 main.py --pdf <file.pdf> --code <MÃ>_corr --correct [--model gemini-flash-lite-latest] [--no-cache]
```

Thêm output khi bật `--correct`: `<MÃ>_corr_corrections.jsonl` (cặp đoạn gốc→đã sửa)
và cache `output/cache/gemini.json` (tái lập, tránh gọi lại API).

**Lưu ý chi phí:** `--limit` chỉ cắt bớt *câu* sau khi đã tách, không giới hạn số
trang gửi lên Gemini — một lần chạy `--correct --limit 40` vẫn gọi API cho
*toàn bộ* các trang được trích. Muốn thử nghiệm rẻ, hãy giới hạn phạm vi trang
bằng `--start-page`/`--end-page` (hoặc trỏ vào một PDF ngắn), không phải `--limit`.

Dependencies: `pip install -r requirements.txt` (`PyMuPDF`, `underthesea`, `google-genai`).
Dev/test deps: `pip install -r requirements-dev.txt` (`pytest`).

```bash
pip install -r requirements.txt
```

Outputs land in `output/`:
- `<code>_seg.tsv` — one line per sentence: `sentence_id<TAB>sentence`
- `<code>_ner.json` — list of `{sentence_id, sentence, entities: [{text, label}]}`

Test suite: `python3 -m pytest tests/` (covers `pipeline/correct.py`; 19 tests, no
real API calls — uses injected fake clients). No linter or build step. PDFs are
gitignored (`*.pdf`).

## Architecture

`main.py` orchestrates a four-stage pipeline (labeled `[0/4]`..`[4/4]` in console output); each stage lives in its own module under `pipeline/` and is a pure function over text. Understanding the stage boundaries is key:

1. **`extract.py`** — `detect_content_range()` reads the PDF's level-1 bookmarks (TOC) to skip front-matter (mục lục, lời nói đầu, sách dẫn…) and the cover page, keeping only real content chapters. Falls back to the whole file when there are no bookmarks. `extract_pages()` then pulls raw text per page via PyMuPDF. Pages are 1-indexed throughout.

2. **`normalize.py`** — `normalize_page_text()` does the heavy lifting and is the most domain-specific module. It: NFC-normalizes Unicode; converts old-style tone placement to modern (`hoà→hòa`, `thuỷ→thủy`, with a `qu`-guard so `quý` is untouched); fixes OCR tone-misplacement (`tòan→toàn`); strips running headers/page numbers/URLs/all-caps chapter titles/OCR gibberish (`_is_junk_line`, `_looks_gibberish`); and rejoins hyphen-broken and wrapped lines into continuous blocks. **Volume/part headings (`Quyển I`, etc.) are dropped as content but still act as block boundaries** so sentences on either side don't merge.

3. **`segment.py`** — `split_sentences()` splits each normalized block with underthesea's `sent_tokenize`, treating `\n` block edges as hard sentence boundaries, and drops fragments that are too short or contain no letters.

4. **`ner.py`** — `extract_entities()` merges two sources: the general **underthesea CRF model** (`_model_entities`, yields PER/LOC/ORG from BIO tags) and a **rule/gazetteer layer** (`_rule_entities`) tuned for historical Vietnamese that the general model misses: `TME` (dates incl. can-chi cycles, niên hiệu, reigns), `DYNASTY`, `TITLE` (official ranks), `NUM`, plus rule-based `LOC`/`PER`. Overlapping spans are resolved by **longer-span-wins, then a fixed priority** (`_PRIORITY`: TME > DYNASTY > TITLE > model > rule-LOC > rule-PER > NUM). Internal labels `LOC_RULE`/`PER_RULE` are renamed to `LOC`/`PER` on output.
- **`correct.py`** (optional, `--correct`) — sits between normalize and segment; sends each normalized page in `<=2500`-char chunks to Gemini via `correct_text()`/`GeminiClient` to fix OCR spelling/tone errors and restore sentence-ending punctuation before segmentation. A length-ratio guard (`within_length_guard`, default 30%) rejects corrections that drift too far in length (keeps the original chunk instead). Results are cached on disk keyed by a hash of `(model, chunk)` (`cache_key`/`load_cache`/`save_cache` at `output/cache/gemini.json`) so reruns don't re-call the API. API errors fall back to the original chunk (`fallback_error`) rather than crashing the pipeline. Every chunk's original→corrected pair and action is written to `<code>_corrections.jsonl` via `write_corrections`.

### Working in this codebase

- The normalization and NER rules are heavily specialized to this one book's OCR quirks and historical-text vocabulary (chapter names like "Dư địa chí", tone errors, can-chi date forms). When adjusting NER coverage, edit the regex patterns and gazetteers at the top of `ner.py` and re-run with `--limit` to spot-check before a full pass.
- Character-position bookkeeping matters: `_model_entities` uses `sentence.find` with a moving cursor to map tokens back to spans, and span selection in `extract_entities` relies on `(start, end, label)` tuples — preserve that contract when touching either.
- All modules assume UTF-8; `main.py` reconfigures stdout to UTF-8 for Windows consoles.
