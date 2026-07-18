# -*- coding: utf-8 -*-
"""Pipeline: PDF -> trích text -> chuẩn hóa -> tách câu -> NER -> JSON.

Chạy:
    python main.py                       # quét input/<MÃ>/*.pdf, mã = tên folder
    python main.py --pdf <file.pdf> --code HVQ_036   # chạy một file lẻ

Kết quả trong thư mục output/:
    <MA>_seg.tsv  : mỗi dòng "sentence_id<TAB>câu"
    <MA>_ner.json      : [{"sentence_id", "sentence", "entities": [...]}, ...]
"""

import argparse
import json
import os
import re
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
    p.add_argument("--input-dir", default="input",
                   help="Thư mục input chứa các folder con dạng <MÃ>/<file>.pdf; "
                        "mỗi folder được xử lý với mã = tên folder (mặc định: input)")
    p.add_argument("--pdf", default=None,
                   help="Chạy một file PDF lẻ thay vì quét --input-dir")
    p.add_argument("--code", default="HVQ_036",
                   help="Mã tác phẩm dùng trong sentence_id và tên file output (chỉ dùng với --pdf)")
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
    p.add_argument("--ocr", action="store_true",
                   help="PDF là ảnh quét không có text layer: render trang + PaddleOCR "
                        "thay vì trích text bằng PyMuPDF (cần cài paddleocr)")
    p.add_argument("--ocr-dpi", type=int, default=200,
                   help="DPI render trang khi --ocr (mặc định 200)")
    return p.parse_args()


def collect_jobs(args):
    """Trả về danh sách (danh_sách_pdf, mã) cần xử lý.

    --pdf chạy một file lẻ với mã --code; mặc định quét các folder con của
    --input-dir, mỗi folder <MÃ>/ là một tác phẩm với mã = tên folder.
    Folder có nhiều PDF (nhiều tập) thì tất cả được gộp chung một output.
    """
    if args.pdf:
        return [([args.pdf], args.code)]

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        sys.exit(f"Không thấy thư mục input: {input_dir} (hoặc dùng --pdf <file>)")

    jobs = []
    for sub in sorted(input_dir.iterdir()):
        if not sub.is_dir():
            continue
        pdfs = sorted(sub.glob("*.pdf"))
        if not pdfs:
            print(f"[!] Bỏ qua {sub.name}: không có file PDF")
            continue
        jobs.append(([str(p) for p in pdfs], sub.name))

    if not jobs:
        sys.exit(f"Không tìm thấy PDF nào trong các folder con của {input_dir}/")
    return jobs


def extract_one_pdf(pdf_path, args):
    """Bước 0+1 cho một PDF: dò khoảng trang nội dung rồi trích text.

    Trả về danh sách (số_trang, text).
    """
    # 0) Xác định khoảng trang nội dung chính theo bookmark của PDF
    auto_start, auto_end, chapters = detect_content_range(pdf_path)
    if chapters:
        print("[0/4] PDF có bookmark — chỉ lấy các chương nội dung chính:")
        for title, p1, p2 in chapters:
            print(f"      - {title} (trang {p1}-{p2})")
    else:
        print("[0/4] PDF không có bookmark — lấy toàn bộ file")
    start_page = args.start_page or auto_start
    end_page = args.end_page or auto_end

    # 1) Trích text từ PDF
    if args.ocr:
        from pipeline.ocr import extract_pages_ocr
        print(f"[1/4] OCR ảnh trang (PaddleOCR): {pdf_path} (trang {start_page}-{end_page})")
        pages = extract_pages_ocr(pdf_path, start_page, end_page, dpi=args.ocr_dpi)
    else:
        print(f"[1/4] Trích text: {pdf_path} (trang {start_page}-{end_page})")
        pages = extract_pages(pdf_path, start_page, end_page)
    print(f"      -> {len(pages)} trang")
    return pages


def chapter_numbers(pdf_paths):
    """Suy ra số chapter cho từng PDF từ số đánh ở cuối tên file.

    Ví dụ ..._tap_1_ocr.pdf -> 1 (lấy số cuối cùng xuất hiện trong tên).
    Nếu có file không chứa số hoặc số bị trùng nhau thì bỏ qua tên file,
    đánh số 1..n theo thứ tự sắp xếp tên (kèm cảnh báo).
    """
    nums = []
    for p in pdf_paths:
        found = re.findall(r"\d+", Path(p).stem)
        nums.append(int(found[-1]) if found else None)
    if None in nums or len(set(nums)) != len(nums):
        print("[!] Không suy ra được số tập từ tên file — đánh số theo thứ tự tên")
        return list(range(1, len(pdf_paths) + 1))
    return nums


def process_work(pdf_paths, code, args, outdir, corr_client, corr_cache, cache_path):
    """Chạy pipeline 4 bước cho một tác phẩm.

    Một PDF: ghi thẳng <outdir>/<MÃ>_seg.tsv, <MÃ>_ner.json.
    Nhiều PDF (nhiều quyển/tập): mỗi tập một thư mục riêng
    <outdir>/<MÃ>/<MÃ>_NN/<MÃ>_NN_seg.tsv..., NN lấy theo số ở cuối tên file.
    """
    if len(pdf_paths) == 1:
        pages = extract_one_pdf(pdf_paths[0], args)
        run_pipeline(pages, code, outdir, args, corr_client, corr_cache, cache_path)
        return

    nums = chapter_numbers(pdf_paths)
    for num, pdf_path in sorted(zip(nums, pdf_paths)):
        chap_code = f"{code}_{num:02d}"
        chap_dir = outdir / code / chap_code
        chap_dir.mkdir(parents=True, exist_ok=True)
        print(f"  -- Chapter {chap_code}: {Path(pdf_path).name}")
        pages = extract_one_pdf(pdf_path, args)
        run_pipeline(pages, chap_code, chap_dir, args, corr_client, corr_cache, cache_path)


def run_pipeline(pages, code, outdir, args, corr_client, corr_cache, cache_path):
    """Bước 2-4 trên các trang đã trích: chuẩn hóa, tách câu, NER, ghi output."""
    corr_records = []

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
        corr_path = outdir / f"{code}_corrections.jsonl"
        write_corrections(str(corr_path), corr_records)
        print(f"      -> {len(corr_records)} đoạn hiệu đính: {corr_path}")
    if args.limit:
        sentences = sentences[: args.limit]
    print(f"      -> {len(sentences)} câu")

    sent_path = outdir / f"{code}_seg.tsv"

    # 4) NER từng câu
    print("[4/4] NER (underthesea + luật)")
    records = []
    t0 = time.time()
    with open(sent_path, "w", encoding="utf-8") as f_sent:
        for i, sent in enumerate(sentences, start=1):
            sid = f"{code}_{i:06d}"
            f_sent.write(f"{sid}\t{sent}\n")
            records.append({
                "sentence_id": sid,
                "sentence": sent,
                "entities": extract_entities(sent),
            })
            if i % 1000 == 0:
                rate = i / (time.time() - t0)
                print(f"      {i}/{len(sentences)} câu ({rate:.0f} câu/giây)")

    ner_path = outdir / f"{code}_ner.json"
    with open(ner_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    n_ent = sum(len(r["entities"]) for r in records)
    print(f"\nHoàn tất sau {time.time() - t0:.1f} giây")
    print(f"  Câu       : {sent_path} ({len(records)} câu)")
    print(f"  NER       : {ner_path} ({n_ent} thực thể)")


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    corr_client = corr_cache = None
    cache_path = str(outdir / "cache" / "gemini.json")
    if args.correct:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            sys.exit("Thiếu GEMINI_API_KEY. Đặt: export GEMINI_API_KEY=...")
        corr_client = GeminiClient(api_key)
        corr_cache = {} if args.no_cache else load_cache(cache_path)
        print(f"[+] Hiệu đính OCR bằng Gemini ({args.model})")

    jobs = collect_jobs(args)
    for idx, (pdf_paths, code) in enumerate(jobs, start=1):
        if len(jobs) > 1:
            print(f"\n===== [{idx}/{len(jobs)}] {code}: {len(pdf_paths)} PDF =====")
        process_work(pdf_paths, code, args, outdir, corr_client, corr_cache, cache_path)


if __name__ == "__main__":
    main()
