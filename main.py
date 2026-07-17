# -*- coding: utf-8 -*-
"""Pipeline: PDF -> trích text -> chuẩn hóa -> tách câu -> NER -> JSON.

Chạy:
    python main.py --pdf lich_trieu_hien_chuong_loai_chi_phan_huy_chu_tap_1_ocr.pdf

Kết quả trong thư mục output/:
    <MA>_seg.tsv  : mỗi dòng "sentence_id<TAB>câu"
    <MA>_ner.json      : [{"sentence_id", "sentence", "entities": [...]}, ...]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from pipeline.extract import detect_content_range, extract_pages
from pipeline.normalize import normalize_page_text
from pipeline.segment import split_sentences
from pipeline.ner import extract_entities
from pipeline.correct import (
    correct_text, GeminiClient, load_cache, save_cache, write_corrections,
)

# Console Windows cần UTF-8 để in tiếng Việt
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser(description="Trích text PDF, chuẩn hóa, tách câu và NER tiếng Việt")
    p.add_argument("--pdf", default="lich_trieu_hien_chuong_loai_chi_phan_huy_chu_tap_1_ocr.pdf",
                   help="Đường dẫn file PDF đầu vào")
    p.add_argument("--code", default="HVQ_036",
                   help="Mã tác phẩm dùng trong sentence_id và tên file output")
    p.add_argument("--start-page", type=int, default=None,
                   help="Trang PDF bắt đầu (mặc định: tự phát hiện theo bookmark)")
    p.add_argument("--end-page", type=int, default=None,
                   help="Trang PDF kết thúc (mặc định: tự phát hiện theo bookmark)")
    p.add_argument("--outdir", default="output", help="Thư mục ghi kết quả")
    p.add_argument("--limit", type=int, default=0, help="Chỉ xử lý N câu đầu (0 = tất cả, dùng để thử nhanh)")
    p.add_argument("--correct", action="store_true",
                   help="Bật hiệu đính OCR bằng Gemini trước khi tách câu")
    p.add_argument("--model", default="gemini-flash-lite-latest",
                   help="Model Gemini dùng khi --correct")
    p.add_argument("--no-cache", action="store_true",
                   help="Không dùng cache hiệu đính (luôn gọi API)")
    return p.parse_args()


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

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

    # 0) Xác định khoảng trang nội dung chính theo bookmark của PDF
    auto_start, auto_end, chapters = detect_content_range(args.pdf)
    if chapters:
        print("[0/4] PDF có bookmark — chỉ lấy các chương nội dung chính:")
        for title, p1, p2 in chapters:
            print(f"      - {title} (trang {p1}-{p2})")
    else:
        print("[0/4] PDF không có bookmark — lấy toàn bộ file")
    start_page = args.start_page or auto_start
    end_page = args.end_page or auto_end

    # 1) Trích text từ PDF
    print(f"[1/4] Trích text: {args.pdf} (trang {start_page}-{end_page})")
    pages = extract_pages(args.pdf, start_page, end_page)
    print(f"      -> {len(pages)} trang")

    # 2) Chuẩn hóa + 3) Tách câu
    print("[2/4] Chuẩn hóa text tiếng Việt")
    print("[3/4] Tách câu (underthesea)")
    sentences = []
    for page_no, raw in pages:
        clean = normalize_page_text(raw)
        if not clean:
            continue
        if args.correct:
            clean, recs = correct_text(clean, corr_client, args.model, corr_cache)
            corr_records.extend(recs)
        sentences.extend(split_sentences(clean))
    if args.correct:
        if not args.no_cache:
            save_cache(cache_path, corr_cache)
        corr_path = outdir / f"{args.code}_corrections.jsonl"
        write_corrections(str(corr_path), corr_records)
        print(f"      -> {len(corr_records)} đoạn hiệu đính: {corr_path}")
    if args.limit:
        sentences = sentences[: args.limit]
    print(f"      -> {len(sentences)} câu")

    sent_path = outdir / f"{args.code}_seg.tsv"

    # 4) NER từng câu
    print("[4/4] NER (underthesea + luật)")
    records = []
    t0 = time.time()
    with open(sent_path, "w", encoding="utf-8") as f_sent:
        for i, sent in enumerate(sentences, start=1):
            sid = f"{args.code}_{i:06d}"
            f_sent.write(f"{sid}\t{sent}\n")
            records.append({
                "sentence_id": sid,
                "sentence": sent,
                "entities": extract_entities(sent),
            })
            if i % 1000 == 0:
                rate = i / (time.time() - t0)
                print(f"      {i}/{len(sentences)} câu ({rate:.0f} câu/giây)")

    ner_path = outdir / f"{args.code}_ner.json"
    with open(ner_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    n_ent = sum(len(r["entities"]) for r in records)
    print(f"\nHoàn tất sau {time.time() - t0:.1f} giây")
    print(f"  Câu       : {sent_path} ({len(records)} câu)")
    print(f"  NER       : {ner_path} ({n_ent} thực thể)")


if __name__ == "__main__":
    main()
