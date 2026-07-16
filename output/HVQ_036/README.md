# HVQ_036 — Ngữ liệu đơn ngữ chữ Quốc ngữ chuyên ngành lịch sử Việt Nam

Mã tác phẩm: `HVQ_036`. Gồm 2 quyển, mỗi quyển một thư mục riêng theo đúng quy
ước của đề bài (`[matacpham]_[chapter]/[matacpham]_[chapter]_*`):

- **HVQ_036_LLKN** — *Lịch Sử Việt Nam Từ Lê Lợi Khởi Nghĩa Đến Nguyễn Suy
  Vong* (158 trang nội dung, 1.498 câu, 4.472 thực thể).
- **HVQ_036_TTLS** — *Tiến Trình Lịch Sử Việt Nam* (396 trang, 7.276 câu,
  16.802 thực thể).

## Nội dung mỗi thư mục

- `<code>_seg.tsv`: câu đã tách, định dạng `[sentence_id]\t[sentence]`.
- `<code>_ner.json`: kết quả NER, mỗi phần tử
  `{sentence_id, sentence, entities: [{text, label}]}`. Nhãn gồm
  `PER, LOC, ORG, TITLE, TME, NUM, DYNASTY`.
- `<code>_corrections.jsonl`: (phụ, không bắt buộc theo đề) từng đoạn văn bản
  gốc/đã hiệu đính và hành động tương ứng (`corrected`/`cache_hit`/
  `fallback_error`), phục vụ kiểm tra chất lượng hiệu đính.
- `cache/gemini.json`: cache kết quả hiệu đính Gemini theo `(model, đoạn văn)`,
  giúp tái lập kết quả mà không cần gọi lại API.

## Phương pháp

Đầu vào là PDF dạng text (không phải ảnh scan), xử lý qua pipeline: trích
text (PyMuPDF) → chuẩn hóa tiếng Việt → hiệu đính OCR bằng Gemini
(`gemini-flash-lite-latest`) → tách câu (underthesea) → NER (mô hình CRF
underthesea + luật/gazetteer lịch sử). Chi tiết kiến trúc xem `CLAUDE.md` ở
thư mục gốc dự án; báo cáo đầy đủ xem `report/baocao.tex`.

Cả hai quyển đã được hiệu đính OCR hoàn tất 100% (LLKN: 153/153 đoạn,
TTLS: 394/394 đoạn) sau nhiều lượt chạy lại tận dụng cache để vượt qua giới
hạn quota miễn phí của Gemini API.
