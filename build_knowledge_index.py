"""
build_knowledge_index.py

Script build vector_db/ (FAISS index + metadata) từ các file .txt
trong knowledge/history_books/, dùng cho Retriever (RAG) trong Main.py.

Cách dùng:

    # Nếu đã có sẵn file .txt trong knowledge/history_books/
    python build_knowledge_index.py

    # Nếu muốn nạp thẳng 1 file nguồn (vd bản OCR thô của
    # "Hùng Vương Dựng Nước") làm tri thức nền, script sẽ copy
    # file đó vào knowledge/history_books/ trước khi build:
    python build_knowledge_index.py --source output/HVQ_001_raw.txt

    # Tùy chỉnh đường dẫn khác:
    python build_knowledge_index.py \\
        --source output/HVQ_001_raw.txt \\
        --knowledge-dir knowledge/history_books \\
        --index-path vector_db/faiss.index \\
        --metadata-path vector_db/metadata.pkl \\
        --model-path models/bge-m3
"""

import os

# Phải set TRƯỚC khi import bất kỳ module nào đụng tới faiss/torch
# (xem giải thích chi tiết trong retriever.py) để tránh
# "segmentation fault" trên macOS khi build index.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import argparse
import shutil

import config
from retriever import Retriever


def parse_args():

    parser = argparse.ArgumentParser(
        description="Build FAISS index cho Retriever (BGE-M3 RAG)"
    )

    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help=(
            "Đường dẫn tới 1 file .txt nguồn (vd bản OCR/raw của "
            "'Hùng Vương Dựng Nước') sẽ được copy vào knowledge-dir "
            "trước khi build index. Có thể bỏ trống nếu knowledge-dir "
            "đã có sẵn file .txt."
        )
    )

    parser.add_argument(
        "--knowledge-dir",
        type=str,
        default=os.path.join(config.BASE_DIR, "knowledge", "history_books"),
        help="Thư mục chứa các file .txt tri thức nền (mặc định: knowledge/history_books)"
    )

    parser.add_argument(
        "--index-path",
        type=str,
        default=os.path.join(config.BASE_DIR, "vector_db", "faiss.index"),
        help="Đường dẫn ghi FAISS index (mặc định: vector_db/faiss.index)"
    )

    parser.add_argument(
        "--metadata-path",
        type=str,
        default=os.path.join(config.BASE_DIR, "vector_db", "metadata.pkl"),
        help="Đường dẫn ghi metadata (mặc định: vector_db/metadata.pkl)"
    )

    parser.add_argument(
        "--model-path",
        type=str,
        default=os.path.join(config.BASE_DIR, "models", "bge-m3"),
        help="Đường dẫn model embedding BGE-M3 (mặc định: models/bge-m3)"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=450,
        help="Số ký tự mỗi chunk khi chia nhỏ văn bản (mặc định: 450)"
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=100,
        help="Số ký tự chồng lấn giữa 2 chunk liên tiếp (mặc định: 100)"
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Build lại index dù đã tồn tại (mặc định: bỏ qua nếu đã có index)"
    )

    return parser.parse_args()


def ensure_source_copied(source_path, knowledge_dir):
    """
    Nếu người dùng truyền --source, copy file đó vào knowledge_dir
    (đổi tên .txt nếu cần) để Retriever.load_documents() đọc được.
    """

    os.makedirs(knowledge_dir, exist_ok=True)

    if source_path is None:
        return

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Không tìm thấy file nguồn: {source_path}")

    filename = os.path.basename(source_path)

    if not filename.lower().endswith(".txt"):
        filename = os.path.splitext(filename)[0] + ".txt"

    dest_path = os.path.join(knowledge_dir, filename)

    shutil.copyfile(source_path, dest_path)

    print(f"Đã copy '{source_path}' -> '{dest_path}'")


def main():

    args = parse_args()

    ensure_source_copied(args.source, args.knowledge_dir)

    txt_files = [
        f for f in os.listdir(args.knowledge_dir)
        if f.lower().endswith(".txt")
    ]

    if not txt_files:
        raise RuntimeError(
            f"Thư mục '{args.knowledge_dir}' chưa có file .txt nào. "
            "Hãy đặt file văn bản tri thức nền (vd bản OCR/raw của "
            "'Hùng Vương Dựng Nước') vào đó, hoặc truyền --source <file.txt>."
        )

    print(f"Tìm thấy {len(txt_files)} file .txt trong '{args.knowledge_dir}':")
    for f in txt_files:
        print(f"  - {f}")

    if (
        not args.rebuild
        and os.path.exists(args.index_path)
        and os.path.exists(args.metadata_path)
    ):
        print(
            f"Index đã tồn tại tại '{args.index_path}'. "
            "Bỏ qua build (dùng --rebuild để build lại)."
        )
        return

    retriever = Retriever(
        index_path=args.index_path,
        metadata_path=args.metadata_path,
        embedding_model=args.model_path,
        knowledge_dir=args.knowledge_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap
    )

    retriever.build_index()

    print()
    print("=" * 50)
    print("Hoàn tất build index.")
    print("Index    :", args.index_path)
    print("Metadata :", args.metadata_path)
    print("=" * 50)


if __name__ == "__main__":
    main()
