# ==========================================================
# retriever.py
# RAG Retriever using BGE-M3 + FAISS
# ==========================================================

import os

# QUAN TRỌNG: phải set TRƯỚC khi import faiss/torch.
# Trên macOS, faiss và torch thường mỗi bên tự mang theo 1 bản runtime
# OpenMP (libomp.dylib) riêng. Khi cả 2 cùng nạp trong 1 process, chúng
# xung đột và gây "segmentation fault" ngay khi khởi tạo model
# (thường thấy rõ nhất ngay sau dòng "Loading BGE-M3..."). Biến này tắt
# việc OpenMP tự abort khi phát hiện bị nạp 2 lần.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import glob
import pickle

import faiss
import numpy as np

from tqdm import tqdm
from sentence_transformers import SentenceTransformer


class Retriever:

    def __init__(
        self,
        index_path="vector_db/faiss.index",
        metadata_path="vector_db/metadata.pkl",
        embedding_model="models/bge-m3",
        knowledge_dir="knowledge/history_books",
        chunk_size=450,
        overlap=100,
        use_fp16=False
    ):

        # embedding_model là tên tham số khớp với Main.py,
        # model_path giữ lại để tương thích ngược.
        self.model_path = embedding_model

        self.knowledge_dir = knowledge_dir

        self.index_path = index_path
        self.metadata_path = metadata_path

        self.chunk_size = chunk_size
        self.overlap = overlap

        print("Loading BGE-M3 (via sentence-transformers)...")

        # Dùng sentence-transformers thay vì FlagEmbedding.BGEM3FlagModel:
        # - Chỉ cần dense embedding (không dùng sparse/colbert của BGE-M3),
        #   nên không mất gì về mặt tính năng.
        # - FlagEmbedding tự quản lý việc load model theo cách riêng, dễ
        #   xung đột phiên bản torch mới và gây "segmentation fault" khi
        #   khởi tạo trên một số máy (đặc biệt macOS). SentenceTransformer
        #   dùng AutoModel/AutoTokenizer chuẩn từ transformers, ổn định hơn.
        self.model = SentenceTransformer(self.model_path)

        self.use_fp16 = use_fp16

        self.index = None
        self.metadata = []

        # Tự động load index nếu đã build sẵn, không bắt buộc
        if os.path.exists(index_path) and os.path.exists(metadata_path):
            try:
                self.load()
                print(f"Loaded existing index with {len(self.metadata)} chunks.")
            except Exception as e:
                print(f"Không load được index có sẵn ({e}), cần build_index().")

    # --------------------------------------------------------
    # Split long text
    # --------------------------------------------------------
    def split_text(self, text):

        text = text.replace("\r", "")
        text = text.replace("\t", " ")

        text = " ".join(text.split())

        chunks = []

        start = 0

        while start < len(text):

            end = start + self.chunk_size

            chunk = text[start:end]

            chunks.append(chunk)

            start += self.chunk_size - self.overlap

        return chunks

    # --------------------------------------------------------
    # Read all txt
    # --------------------------------------------------------
    def load_documents(self):

        docs = []

        files = glob.glob(
            os.path.join(
                self.knowledge_dir,
                "*.txt"
            )
        )

        for file in files:

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                text = f.read()

            chunks = self.split_text(text)

            for i, chunk in enumerate(chunks):

                docs.append({

                    "file": os.path.basename(file),

                    "chunk_id": i,

                    "text": chunk

                })

        return docs

    # --------------------------------------------------------
    # Embedding
    # --------------------------------------------------------
    def embed(self, texts):

        vectors = self.model.encode(
            texts,
            batch_size=8,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        vectors = np.asarray(
            vectors,
            dtype=np.float32
        )

        return vectors

    # --------------------------------------------------------
    # Build index
    # --------------------------------------------------------
    def build_index(self):

        print("Loading documents...")

        docs = self.load_documents()

        if not docs:
            raise RuntimeError(
                f"Không tìm thấy file .txt nào trong {self.knowledge_dir}"
            )

        texts = [x["text"] for x in docs]

        print("Embedding...")

        vectors = []

        batch = 64

        for i in tqdm(range(0, len(texts), batch)):

            vec = self.embed(texts[i:i + batch])

            vectors.append(vec)

        vectors = np.vstack(vectors)

        dim = vectors.shape[1]

        index = faiss.IndexFlatIP(dim)

        faiss.normalize_L2(vectors)

        index.add(vectors)

        self.index = index
        self.metadata = docs

        os.makedirs(
            os.path.dirname(self.index_path) or ".",
            exist_ok=True
        )

        faiss.write_index(index, self.index_path)

        with open(self.metadata_path, "wb") as f:
            pickle.dump(docs, f)

        print()
        print("Index built.")
        print("Chunks :", len(docs))

    # --------------------------------------------------------
    # Load index
    # --------------------------------------------------------
    def load(self):

        self.index = faiss.read_index(self.index_path)

        with open(self.metadata_path, "rb") as f:
            self.metadata = pickle.load(f)

    # --------------------------------------------------------
    # Retrieve (core)
    # --------------------------------------------------------
    def retrieve(self, query, top_k=5):

        if self.index is None:
            raise RuntimeError(
                "Retriever chưa có index. Gọi build_index() trước, "
                "hoặc kiểm tra lại index_path/metadata_path."
            )

        vec = self.embed([query])

        faiss.normalize_L2(vec)

        scores, ids = self.index.search(vec, top_k)

        results = []

        for score, idx in zip(scores[0], ids[0]):

            if idx < 0:
                continue

            item = dict(self.metadata[idx])
            item["score"] = float(score)

            results.append(item)

        return results

    # --------------------------------------------------------
    # search() - alias khớp với cách Main.py gọi
    # --------------------------------------------------------
    def search(self, query, top_k=5):
        return self.retrieve(query, top_k)

    # --------------------------------------------------------
    # Context (ghép các đoạn tìm được thành 1 chuỗi text)
    # --------------------------------------------------------
    def get_context(self, query, top_k=5):

        docs = self.retrieve(query, top_k)

        context = ""

        for doc in docs:
            context += doc["text"]
            context += "\n\n"

        return context.strip()
