"""
config.py
Global configuration for Digitization Pipeline
"""

import os

from dotenv import load_dotenv

# Tự động đọc file .env (nếu có) trong cùng thư mục và set vào
# os.environ. Không báo lỗi nếu file .env không tồn tại - lúc đó các
# biến vẫn lấy giá trị mặc định (hard-code) phía dưới, hoặc từ biến
# môi trường hệ thống nếu người dùng đã export sẵn.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# =====================================================
# PROJECT PATHS
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_DIR = os.path.join(BASE_DIR, "input")

OUTPUT_DIR = os.path.join(BASE_DIR, "output")

LOG_DIR = os.path.join(BASE_DIR, "logs")

# =====================================================
# OCR
# =====================================================

# PDF Render DPI
# Tăng lên 300 (từ 200) vì sách scan cũ (1970) có dấu thanh tiếng Việt
# rất nhỏ, DPI thấp dễ khiến PaddleOCR bỏ sót hoặc nhận sai dấu.
OCR_DPI = 300

# ----------------------------------------------------------
# Hybrid Extractor: ngưỡng để quyết định 1 trang PDF có "text layer
# dùng được" hay không (nếu có -> lấy trực tiếp, không cần OCR; nếu
# không -> fallback render ảnh + OCR trang đó).
# ----------------------------------------------------------

# Số ký tự CHỮ CÁI tối thiểu trong text layer của 1 trang để coi là
# "có nội dung thật" (không phải trang trắng / chỉ có số trang lẻ loi)
MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER = 20

# Tỷ lệ tối thiểu (ký tự chữ cái / tổng ký tự non-whitespace) để coi
# text layer không phải toàn ký tự rác/lỗi encoding
MIN_ALPHA_RATIO_FOR_TEXT_LAYER = 0.3

# Sai số toạ độ y (đơn vị point PDF, 1 point = 1/72 inch) để coi 2
# item (span text thật hoặc dòng OCR từ ảnh) là CÙNG 1 DÒNG khi ráp
# lại. Cỡ chữ sách thường ~10-12pt nên 4.0 là mức khởi điểm hợp lý;
# tăng lên nếu thấy item cùng dòng thật bị tách thành nhiều dòng khác
# nhau trong output, giảm xuống nếu thấy 2 dòng khác nhau bị gộp nhầm.
LINE_Y_TOLERANCE = 4.0

# OCR Language
OCR_LANG = "vi"

# PaddleOCR Models (None = dùng model mặc định)
TEXT_DETECTION_MODEL = None
TEXT_RECOGNITION_MODEL = None

# OCR Threshold
OCR_SCORE_THRESHOLD = 0.60

# Có giữ text confidence thấp không
KEEP_LOW_SCORE = False

# =====================================================
# PDF
# =====================================================

MAX_PAGE = None          # None = đọc toàn bộ

START_PAGE = 0

# =====================================================
# SEGMENTATION
# =====================================================

MIN_SENTENCE_LENGTH = 3

REMOVE_EMPTY_SENTENCE = True

# =====================================================
# NER
# =====================================================

ENABLE_PER = True
ENABLE_LOC = True
ENABLE_ORG = True
ENABLE_TITLE = True
ENABLE_TIME = True
ENABLE_NUM = True
ENABLE_DYNASTY = True

# =====================================================
# OUTPUT
# =====================================================

RAW_SUFFIX = "_raw.txt"

SEG_SUFFIX = "_seg.tsv"

NER_SUFFIX = "_ner.json"

ENCODING = "utf-8"

JSON_INDENT = 2

# =====================================================
# LOGGING
# =====================================================

LOG_LEVEL = "INFO"

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"

# =====================================================
# PERFORMANCE
# =====================================================

ENABLE_GC = True

NUM_WORKERS = 1

BATCH_SIZE = 1

# =====================================================
# TEXT CORRECTION
# =====================================================

ENABLE_TEXT_CORRECTION = True

ENABLE_NORMALIZE_SPACE = True

ENABLE_FIX_PUNCTUATION = True

ENABLE_FIX_COMMON_OCR_ERROR = True

# =====================================================
# LLM CORRECTION BACKEND
# =====================================================

# Đọc từ .env - xem .env.example để biết các biến hỗ trợ.
# False: dùng Qwen2.5 chạy local (llm_corrector.py)
# True: dùng AWS Bedrock (bedrock_corrector.py) - né hoàn toàn vấn đề
#       GPU/MPS/CPU local (segfault, treo...), nhưng cần tài khoản AWS,
#       tốn phí theo token, cần mạng khi chạy.
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
USE_BEDROCK = os.environ.get("USE_BEDROCK", "true").strip().lower() == "true"

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "openai.gpt-oss-120b-1:0"
)

BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "ap-northeast-1")

# =====================================================
# TITLE DICTIONARY
# =====================================================

TITLE_WORDS = {

    "vua",

    "hoàng đế",

    "quốc vương",

    "thái tử",

    "hoàng hậu",

    "công chúa",

    "ông",

    "bà",

    "ngài",

    "tướng",

    "đại tướng",

    "chủ tịch",

    "phó chủ tịch",

    "giám đốc",

    "tổng giám đốc",

    "ceo",

    "bộ trưởng"
}

# =====================================================
# DYNASTY DICTIONARY
# =====================================================

DYNASTIES = {

    "nhà Hùng",

    "nhà Thục",

    "nhà Triệu",

    "nhà Đinh",

    "nhà Tiền Lê",

    "nhà Lý",

    "nhà Trần",

    "nhà Hồ",

    "nhà Hậu Lê",

    "nhà Mạc",

    "nhà Tây Sơn",

    "nhà Nguyễn",

    "nhà Minh",

    "nhà Thanh",

    "nhà Đường",

    "nhà Tống"
}

# =====================================================
# TIME PATTERNS
# =====================================================

TIME_PATTERNS = [

    r"ngày\s+\d{1,2}",

    r"tháng\s+\d{1,2}",

    r"năm\s+\d{4}",

    r"\d{1,2}[/-]\d{1,2}[/-]\d{4}",

    r"thế kỷ\s+[IVXLCDM0-9]+",

    r"thời kỳ\s+[A-Za-zÀ-ỹ ]+"
]