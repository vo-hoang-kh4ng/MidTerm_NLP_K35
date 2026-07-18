"""
hybrid_extractor.py
Trích text từ PDF theo chiến lược lai (hybrid) ở MỨC SPAN/DÒNG NHỎ NHẤT
có thể lấy được, để xử lý đúng cả trường hợp 1 dòng có PHẦN là text
thật, PHẦN là ảnh chèn giữa dòng (ngẫu nhiên, không theo quy luật).

Cách hoạt động:
    1. Với mỗi trang, lấy toàn bộ "span" text thật (PyMuPDF tách sẵn
       theo từng đoạn chữ liền font/style), mỗi span có toạ độ (bbox)
       riêng - đây là đơn vị nhỏ nhất PyMuPDF cung cấp cho text thật.
    2. Với mỗi block là ẢNH, KHÔNG OCR gộp phẳng thành 1 cục text. Thay
       vào đó, OCR vùng ảnh đó và giữ lại TOẠ ĐỘ TỪNG DÒNG chữ nhận
       diện được (PaddleOCR trả về x,y cho từng dòng), quy đổi ngược
       toạ độ đó về hệ toạ độ PDF (point) - biến mỗi dòng OCR thành 1
       "item" có vị trí như 1 span thật.
    3. Gộp TẤT CẢ item (span text thật + dòng OCR từ ảnh) lại thành 1
       danh sách, nhóm theo DÒNG dựa trên toạ độ y gần nhau, rồi trong
       từng dòng sắp theo x trái->phải.
    => Kết quả: nếu 1 dòng có nửa đầu là text thật, nửa sau là ảnh chèn
       giữa dòng, cả 2 phần đều nằm đúng vị trí tương đối của nhau khi
       ráp lại, thay vì bị tách rời thành 2 cục văn bản không liên quan.

    Nếu 1 trang không lấy được item nào (toàn bộ trang là ảnh scan
    thuần không tách được block) -> fallback OCR cả trang.
"""

import io
import logging

import fitz
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class HybridExtractor:

    def __init__(
        self,
        ocr_processor,
        min_chars_per_page=20,
        min_alpha_ratio=0.3,
        line_y_tolerance=4.0
    ):
        """
        ocr_processor: instance của OCRProcessor (ocr_engine.py).
        min_chars_per_page, min_alpha_ratio: giữ lại để tương thích
            tham số cũ, hiện chỉ dùng như một cảnh báo log tham khảo,
            không còn quyết định nhị phân "dùng text hay dùng ảnh" cho
            cả trang nữa (đã xử lý mịn hơn ở mức item/dòng).
        line_y_tolerance: sai số toạ độ y (đơn vị point PDF) để coi 2
            item là CÙNG 1 DÒNG khi ráp lại. Tăng giá trị này nếu thấy
            các item cùng 1 dòng thực tế bị tách thành nhiều dòng khác
            nhau trong kết quả; giảm nếu thấy 2 dòng khác nhau bị gộp
            nhầm làm một.
        """

        self.ocr_processor = ocr_processor
        self.min_chars_per_page = min_chars_per_page
        self.min_alpha_ratio = min_alpha_ratio
        self.line_y_tolerance = line_y_tolerance

    # ------------------------------------------------------
    # Kiểm tra trang có phải "toàn ảnh scan thuần" hay không: chỉ có
    # đúng 1 block, là ảnh, và phủ gần như 100% diện tích trang. Nếu
    # đúng, KHÔNG nên crop-rồi-OCR-lại (dù về lý thuyết crop = full
    # page) - đã xác nhận PaddleOCR (bản có UVDoc/doc-orientation
    # preprocessing) cho kết quả KHÁC NHAU giữa việc OCR trực tiếp
    # ảnh gốc và OCR ảnh đã qua PIL.crop() dù crop đó phủ 100% ảnh,
    # có thể do các bước tiền xử lý tài liệu (chống méo, xoay ảnh)
    # nhạy với cách ảnh được decode/crop. Dùng thẳng OCR toàn trang
    # (đường đã kiểm chứng cho kết quả đúng) để tránh mất nội dung.
    # ------------------------------------------------------
    def _is_full_page_scan(self, page, blocks, coverage_threshold=0.95):

        if len(blocks) != 1:
            return False

        block = blocks[0]

        if block.get("type", 0) != 1:
            return False

        bbox = block["bbox"]

        block_area = max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])

        page_rect = page.rect

        page_area = page_rect.width * page_rect.height

        if page_area <= 0:
            return False

        coverage = block_area / page_area

        return coverage >= coverage_threshold

    # ------------------------------------------------------
    # Thu thập toàn bộ item (span text thật + dòng OCR từ ảnh) của
    # 1 trang, mỗi item có bbox toạ độ PDF (point) + text
    # ------------------------------------------------------
    def _collect_page_items(self, page):

        page_dict = page.get_text("dict")

        blocks = page_dict.get("blocks", [])

        # Trang toàn ảnh scan thuần (1 block ảnh phủ ~100% trang,
        # không có block text nào khác) -> trả về rỗng để _process_page
        # tự động fallback sang _ocr_full_page() (đường đã kiểm chứng
        # đúng), KHÔNG đi qua crop-rồi-OCR dễ gây sai lệch.
        if self._is_full_page_scan(page, blocks):
            return []

        items = []

        full_page_image = None

        # PDF mặc định 72 point/inch; pixmap render theo self.ocr_processor.dpi
        scale = self.ocr_processor.dpi / 72.0

        for block in blocks:

            btype = block.get("type", 0)

            if btype == 0:

                for line in block.get("lines", []):

                    for span in line.get("spans", []):

                        text = span.get("text", "")

                        if text.strip():

                            items.append({
                                "bbox": span["bbox"],
                                "text": text
                            })

            elif btype == 1:

                if full_page_image is None:

                    pix = page.get_pixmap(dpi=self.ocr_processor.dpi)

                    full_page_image = Image.open(
                        io.BytesIO(pix.tobytes("png"))
                    )

                bbox = block["bbox"]

                crop_box = (
                    max(0, bbox[0] * scale),
                    max(0, bbox[1] * scale),
                    bbox[2] * scale,
                    bbox[3] * scale
                )

                cropped = full_page_image.crop(crop_box)

                cropped_np = np.array(cropped)

                ocr_lines = self.ocr_processor.ocr_page(cropped_np)

                for ocr_line in ocr_lines:

                    if not ocr_line["text"].strip():
                        continue

                    # Quy đổi toạ độ từ pixel (trong ảnh crop) về lại
                    # point PDF, cộng offset gốc của vùng crop (bbox)
                    item_x0 = bbox[0] + (ocr_line["x"] / scale)
                    item_y0 = bbox[1] + (ocr_line["y"] / scale)

                    items.append({
                        "bbox": (item_x0, item_y0, item_x0 + 1, item_y0 + 1),
                        "text": ocr_line["text"]
                    })

        return items

    # ------------------------------------------------------
    # Nhóm các item thành từng DÒNG theo toạ độ y gần nhau, trong mỗi
    # dòng sắp theo x trái -> phải
    # ------------------------------------------------------
    def _group_into_lines(self, items):

        if not items:
            return []

        items_sorted = sorted(items, key=lambda it: it["bbox"][1])

        lines = []
        current_line = [items_sorted[0]]
        current_y = items_sorted[0]["bbox"][1]

        for item in items_sorted[1:]:

            y0 = item["bbox"][1]

            if abs(y0 - current_y) <= self.line_y_tolerance:
                current_line.append(item)
            else:
                lines.append(current_line)
                current_line = [item]
                current_y = y0

        lines.append(current_line)

        result_lines = []

        for line_items in lines:

            line_items_sorted = sorted(
                line_items,
                key=lambda it: it["bbox"][0]
            )

            line_text = " ".join(
                it["text"] for it in line_items_sorted if it["text"].strip()
            )

            if line_text.strip():
                result_lines.append(line_text)

        return result_lines

    # ------------------------------------------------------
    # OCR cả trang (fallback khi trang không lấy được item nào)
    # ------------------------------------------------------
    def _ocr_full_page(self, page):

        pix = page.get_pixmap(dpi=self.ocr_processor.dpi)

        image = Image.open(io.BytesIO(pix.tobytes("png")))

        image_np = np.array(image)

        lines = self.ocr_processor.ocr_page(image_np)

        return "\n".join(line["text"] for line in lines)

    # ------------------------------------------------------
    # Xử lý 1 trang: thu thập item -> nhóm dòng -> ráp text
    # ------------------------------------------------------
    def _process_page(self, page):

        items = self._collect_page_items(page)

        if not items:
            return self._ocr_full_page(page), "full_page_ocr (không có item nào)"

        lines = self._group_into_lines(items)

        page_text = "\n".join(lines)

        if not page_text.strip():
            return self._ocr_full_page(page), "full_page_ocr (rỗng sau khi ráp)"

        method = f"{len(items)} item (text thật + OCR ảnh) ráp thành {len(lines)} dòng"

        return page_text, method

    # ------------------------------------------------------
    # Trích text toàn bộ PDF
    # ------------------------------------------------------
    def extract_text(self, pdf_path, max_pages= None):
        """
        max_pages: giới hạn số trang xử lý (dùng để test nhanh, vd
            max_pages=5 chỉ chạy 5 trang đầu). None = xử lý toàn bộ.
            KHÔNG dùng doc[:n] để giới hạn - fitz.Document không hỗ
            trợ slicing trả về Document con, Python sẽ tự fallback
            gom thành list Python thường (mất hết method như .close()).
        """

        doc = fitz.open(pdf_path)

        total = len(doc)

        pages_to_process = total if max_pages is None else min(max_pages, total)

        pages_text = []

        for idx in range(1, pages_to_process + 1):

            page = doc[idx - 1]

            page_text, method = self._process_page(page)

            logger.info("Trang %d/%d: %s", idx, pages_to_process, method)

            pages_text.append(page_text)

        doc.close()

        return "\n\n".join(pages_text)
