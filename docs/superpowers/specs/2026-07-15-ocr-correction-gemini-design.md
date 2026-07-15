# Thiết kế: Bước hiệu đính OCR bằng Gemini

- **Ngày:** 2026-07-15
- **Dự án:** MidTerm_NLP_K35 — ngữ liệu HVQ (đơn ngữ chữ Quốc ngữ, lịch sử VN)
- **Nhánh:** khang

## 1. Bối cảnh & vấn đề

Pipeline hiện tại `extract → normalize → segment → NER` xử lý được PDF dạng text, nhưng
lớp text OCR của 2 cuốn (đặc biệt *Tiến Trình Lịch Sử Việt Nam*) còn nhiều lỗi nằm sẵn:

- **Sai chính tả / dấu thanh:** `Vỉệt→Việt`, `phát sỉnh→phát sinh`, `tập hçfp→tập hợp`.
- **Sai/mất dấu câu:** dấu chấm bị OCR thành phẩy hoặc mất hẳn (`lớnĐể`, `dân tộc, Thời`),
  khiến bước tách câu tạo ra **câu bị dính** (nhiều câu gộp làm một).
- **Tên riêng méo:** `Sơn V7→Sơn Vi`.

Các luật chuẩn hóa offline (`normalize.py`) chỉ xử lý được lỗi hệ thống (dấu thanh cũ→mới,
dấu câu full-width, chèn space sau dấu câu). Lỗi ngữ cảnh/tên riêng cần mô hình ngôn ngữ.

## 2. Mục tiêu

Thêm một bước **hiệu đính OCR bằng LLM (Google Gemini)** để:

1. Sửa lỗi chính tả / dấu thanh còn sót.
2. **Khôi phục dấu câu** để gỡ các câu bị dính → tách câu sạch hơn.

Áp dụng cho **cả 2 cuốn**, ưu tiên cuốn 2. **Không phá** hành vi hiện tại: khi không bật
cờ hiệu đính, pipeline chạy y như cũ.

### Ngoài phạm vi (Non-goals)
- Không thay đổi bước NER.
- Không sửa lỗi bằng LLM local / provider khác (đã chốt dùng Gemini).
- Không dịch, tóm tắt hay diễn giải lại nội dung.

## 3. Quyết định thiết kế đã chốt

| Vấn đề | Quyết định |
|---|---|
| Phương pháp | LLM — Google Gemini |
| Vị trí trong pipeline | **Trước** khi tách câu, ở **mức đoạn văn** |
| Tier model mặc định | **Flash** (đổi được qua `--model`) |
| Output | **Code/file riêng**, giữ nguyên bản gốc + file đối chiếu |

## 4. Kiến trúc & luồng dữ liệu

```
extract → normalize → [correct (Gemini)] → segment → NER
                          ▲ chỉ chạy khi bật --correct
```

### Module mới: `pipeline/correct.py`

- `chunk_text(page_text) -> list[str]`
  Cắt text một trang (đã normalize) thành các **chunk ~2000–3000 ký tự** theo **ranh giới đoạn**
  (`\n` giữa các block); không cắt giữa một đoạn/câu để giữ ngữ cảnh cho LLM.

- `correct_chunk(chunk, client, model) -> str`
  Gọi Gemini với prompt ràng buộc (mục 5), trả về text đã sửa.

- `correct_text(page_text, client, model, cache) -> tuple[str, list[dict]]`
  Điều phối: chunk → (tra cache | gọi API) → guard an toàn → ghép lại.
  Trả về `(corrected_text, records)` với `records` là danh sách cặp `{original, corrected, action}`
  (`action` ∈ `corrected` / `kept_original_length_guard` / `cache_hit` / `fallback_error`).

### Thay đổi `main.py`
- Cờ mới:
  - `--correct` (bật bước hiệu đính; mặc định tắt để backward-compatible),
  - `--model` (mặc định một model tier *flash*, ví dụ `gemini-2.5-flash` — xác nhận tên đúng khi cài SDK),
  - `--no-cache` (bỏ qua cache, luôn gọi API).
- Khi bật `--correct`: với mỗi trang, sau `normalize_page_text` gọi `correct_text(...)`
  rồi mới `split_sentences(...)`. Gom `records` để ghi file đối chiếu.
- Nếu thiếu `GEMINI_API_KEY` mà bật `--correct` → dừng sớm với thông báo rõ ràng.

## 5. Prompt & an toàn nội dung

Đây là ngữ liệu sử — rủi ro lớn nhất là LLM "sửa" nhầm **từ cổ / tên riêng lạ** làm **sai nội dung**.

### Prompt (ràng buộc chặt)
Nội dung cốt lõi (tiếng Việt) yêu cầu model:
- Chỉ **sửa lỗi OCR**: chính tả, dấu thanh, từ bị dính/tách sai, khôi phục dấu chấm cuối câu.
- **TUYỆT ĐỐI KHÔNG**: dịch, tóm tắt, thêm/bớt/diễn giải, đổi văn phong.
- **Giữ nguyên** tên riêng, số, năm, niên hiệu — trừ khi rõ ràng là ký tự OCR méo.
- **Chỉ trả về văn bản đã sửa**, không thêm lời dẫn/giải thích.

### Chốt chặn an toàn (không phụ thuộc model)
1. **Guard độ dài:** nếu `len(corrected)` lệch > **30%** so với `len(original)` → **giữ bản gốc**,
   ghi `action=kept_original_length_guard`. Chặn hallucination / mất đoạn.
2. **Cache theo hash** nội dung chunk (SHA-256) → lưu `output/cache/gemini_<model>.json`.
   Chạy lại **miễn phí + tái lập được**; đồng thời là kho đối chiếu gốc→sửa.
3. **Fallback lỗi API:** retry có backoff (vd 3 lần); vẫn lỗi → trả **text gốc**
   (`action=fallback_error`), pipeline **không bao giờ crash**.

## 6. Provenance / Output

- Chạy hiệu đính dùng **code riêng** (ví dụ `--code HVQ_036_TTLS_corr`) → không đè
  `HVQ_036_TTLS_sentences.txt` / `_ner.json` gốc.
- Xuất thêm **`output/<code>_corrections.jsonl`** — mỗi dòng một cặp `{original, corrected, action}`
  để kiểm tra chất lượng và đưa vào báo cáo đồ án.

## 7. Cấu hình & phụ thuộc

- Biến môi trường: `GEMINI_API_KEY`.
- Thêm `google-genai` (SDK mới của Google GenAI) vào `requirements.txt`.

## 8. Xử lý lỗi

| Tình huống | Hành vi |
|---|---|
| Thiếu `GEMINI_API_KEY` khi `--correct` | Dừng sớm, thông báo cách đặt biến |
| Lỗi mạng / rate-limit | Retry backoff; hết lượt → fallback text gốc |
| Model trả rỗng / chênh độ dài lớn | Guard giữ bản gốc |
| Cache hỏng / không đọc được | Coi như cache miss, gọi lại API |

## 9. Kiểm thử

1. **Unit test guard độ dài** với **Gemini client mock** (không tốn API): xác nhận
   chunk bị chênh >30% thì giữ bản gốc; chunk hợp lệ thì nhận bản sửa.
2. **Chạy `--limit` mẫu nhỏ** mỗi cuốn (vd 40 câu), soi `_corrections.jsonl`
   để mắt thường kiểm: có sửa đúng lỗi tiêu biểu, không đổi tên riêng.
3. **Backward-compat:** chạy không `--correct` → output trùng khớp hành vi hiện tại.

## 10. Rủi ro & giả định

- **Giả định:** người chạy có `GEMINI_API_KEY` hợp lệ và quota đủ cho ~760 trang.
- **Rủi ro:** rate-limit tier free có thể làm chậm → cache + backoff giảm nhẹ.
- **Rủi ro:** vẫn có thể sót vài lỗi model không nhận ra hoặc sửa sai tên riêng hiếm →
  file `_corrections.jsonl` cho phép rà soát thủ công phần quan trọng.
