import os

# Phải set TRƯỚC khi import retriever.py (đụng tới faiss/torch), để
# tránh "segmentation fault" trên macOS do xung đột OpenMP.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import time
import logging
import fitz

import config
import re
from ocr_engine import OCRProcessor
from hybrid_extractor import HybridExtractor
from normalizer import TextNormalizer
from text_corrector import TextCorrector
from sentence_split import SentenceSplitter
from retriever import Retriever
from ner_engine import NERProcessor
from exporter import Exporter
from chunk_builder import ChunkBuilder
from bedrock_corrector import BedrockCorrector

logging.basicConfig(
    level=config.LOG_LEVEL,
    format=config.LOG_FORMAT
)

logger = logging.getLogger(__name__)


class OCRPipeline:

    def __init__(self):
        self.chunk_builder = ChunkBuilder()
        logger.info("Loading OCR...")
        self.ocr = OCRProcessor(
            dpi=config.OCR_DPI,
            lang=config.OCR_LANG,
            score_threshold=config.OCR_SCORE_THRESHOLD
        )

        logger.info("Loading Hybrid Extractor...")
        self.extractor = HybridExtractor(
            ocr_processor=self.ocr,
            min_chars_per_page=config.MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER,
            min_alpha_ratio=config.MIN_ALPHA_RATIO_FOR_TEXT_LAYER,
            line_y_tolerance=config.LINE_Y_TOLERANCE
        )

        logger.info("Loading Normalizer...")
        self.normalizer = TextNormalizer()

        logger.info("Loading Text Corrector (dictionary-based)...")
        self.dict_corrector = TextCorrector()

        logger.info("Loading Sentence Splitter...")
        self.splitter = SentenceSplitter()

        logger.info("Loading Retriever...")
        self.retriever = Retriever(
            index_path=os.path.join(config.BASE_DIR, "vector_db", "faiss.index"),
            metadata_path=os.path.join(config.BASE_DIR, "vector_db", "metadata.pkl"),
            embedding_model=os.path.join(config.BASE_DIR, "models", "bge-m3")
        )

        logger.info("Loading LLM corrector...")


        self.corrector = BedrockCorrector(
            max_tokens=1024,
            temperature=0,
            max_retries=3
        )



        logger.info("Loading NER...")
        self.ner = NERProcessor()

        logger.info("Loading Exporter...")
        self.exporter = Exporter()

    def run(self, pdf_path, work_id):
    
        start = time.time()

        # >>> BỔ SUNG QUAN TRỌNG: Trích xuất văn bản từ PDF trước khi split
        logger.info("Extracting text from PDF...")
        text = self.extractor.extract_text(pdf_path)
        logger.info("Export RAW...")
        self.exporter.export_raw(
            text,
            work_id
        )
        ###################################################
        # STEP 1: SENTENCE SPLITTING
        ###################################################
        logger.info("STEP 1: SENTENCE SPLITTING")
        split_sentences = self.splitter.split(text, work_id=work_id)

        ###################################################
        # STEP 2 & 3: NORMALIZATION & TEXT CORRECTOR (SỬA THÔ)
        ###################################################
        logger.info("STEP 2 & 3: NORMALIZATION & RULE CORRECTION")
        
        for item in split_sentences:
            raw_sentence = item["sentence"]
            normalized = self.normalizer.normalize(raw_sentence)
            # Sửa từ self.corrector thành self.dict_corrector theo đúng __init__
            corrected = self.dict_corrector.correct(normalized)
            item["sentence"] = corrected

        ###################################################
        # STEP 4 LLM CORRECTION
        ###################################################
        logger.info("STEP 4 LLM CORRECTION")
        
        # Regex thông minh bắt mọi loại tiền tố (HVQ_001 hay DOC đều được), nhóm 1 là số thứ tự câu ở cuối
        pattern = re.compile(
            r"\[{2,4}[A-Za-z0-9_]+?_(\d+)\]{2,4}\s*(.*?)(?=\[{2,4}[A-Za-z0-9_]+?_\d+\]{2,4}|$)", 
            flags=re.S
        )

        # Định nghĩa biến 'chunks' từ danh sách split_sentences
        chunks = self.chunk_builder.build(split_sentences, chunk_size=10)

        corrected_sentences = []
        
        # Đồng bộ biến tra cứu theo 'split_sentences' chính xác
        sentence_lookup = {s["sentence_id"].split("_")[-1]: s for s in split_sentences}

        for chunk in chunks:
            contexts = self.retriever.retrieve(chunk["search_text"], top_k=3)
            
            # CHÚ Ý SỬA TẠI ĐÂY: Gọi self.corrector thay vì self.bedrock
            # Biến self.corrector này sẽ tự động là Bedrock hoặc Qwen tùy theo file config.py của bạn
            corrected_text = self.corrector.correct(chunk["text"], contexts)

            matches = pattern.findall(corrected_text)
            
            if not matches:
                # Fallback cứu hộ toàn bộ chunk nếu LLM lỗi cấu trúc marker hoàn toàn
                for item in chunk["items"]:
                    logger.warning(f"Không tìm thấy kết quả LLM cho {item['sentence_id']}. Dùng bản sửa của TextCorrector.")
                    corrected_sentences.append({
                        "sentence_id": item["sentence_id"],
                        "sentence": item["sentence"]
                    })
                continue

            matched_numeric_ids = set()
            for num_id, text_match in matches:
                padded_id = num_id.strip()
                matched_numeric_ids.add(padded_id)
                
                # Ánh xạ ngược lại: Lấy số thứ tự dò ngược lại bản ghi gốc để lấy ID chuẩn HVQ_001_xxxxxx
                if padded_id in sentence_lookup:
                    orig_item = sentence_lookup[padded_id]
                    corrected_sentences.append({
                        "sentence_id": orig_item["sentence_id"], # Đảm bảo luôn giữ ID chuẩn của hệ thống (HVQ_001_...)
                        "sentence": text_match.strip()
                    })
                else:
                    logger.warning(f"LLM trả về ID số lạ không khớp hệ thống gốc: {padded_id}")

            # Kiểm tra cứu hộ riêng lẻ cho từng câu nếu LLM vô tình làm mất marker của câu đó
            for item in chunk["items"]:
                curr_num_id = item["sentence_id"].split("_")[-1]
                if curr_num_id not in matched_numeric_ids:
                    logger.warning(f"LLM làm mất marker câu {item['sentence_id']}. Tự động cứu hộ bằng TextCorrector.")
                    corrected_sentences.append({
                        "sentence_id": item["sentence_id"],
                        "sentence": item["sentence"]
                    })
        self.exporter.export_segmentation(
            corrected_sentences,
            work_id
        )
        ###################################################
        # STEP 5 NER
        ###################################################
        logger.info("STEP 5 NER")

        ner_results = []
        for item in corrected_sentences:
            result = self.ner.process(
                item["sentence_id"],
                item["sentence"]
            )
            ner_results.append(result)

        self.exporter.export_ner(
            ner_results,
            work_id
        )
        
        logger.info("Pipeline hoàn thành xuất sắc trong %.2f giây!", time.time() - start)


#########################################################
# MAIN
#########################################################
def main():
    
    pdf_files = [
        os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 1.pdf"),
        os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 2.pdf"),
        os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 3.pdf"),
        os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 4.pdf"),
    ]

    merged_pdf = os.path.join(config.INPUT_DIR, "HVQ_ALL.pdf")

    # Kiểm tra các file đầu vào
    for pdf in pdf_files:
        if not os.path.exists(pdf):
            raise FileNotFoundError(pdf)

    # Nếu file gộp đã tồn tại thì xóa
    if os.path.exists(merged_pdf):
        os.remove(merged_pdf)

    # Gộp PDF
    doc = fitz.open()

    for pdf in pdf_files:
        src = fitz.open(pdf)
        doc.insert_pdf(src)
        src.close()

    doc.save(merged_pdf)
    doc.close()

    print(f"Đã gộp {len(pdf_files)} file thành: {merged_pdf}")

    # Chạy pipeline
    work_id = "HVQ_039"

    pipeline = OCRPipeline()
    pipeline.run(merged_pdf, work_id)


#########################################################

if __name__ == "__main__":
    main()