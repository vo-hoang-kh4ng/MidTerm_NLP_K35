"""
sentence_split.py
Sentence Segmentation for Digitization Pipeline
"""

import re
from underthesea import sent_tokenize

import config


class SentenceSplitter:

    def __init__(
        self,
        min_length=None,
        remove_empty=None
    ):

        self.min_length = (
            min_length
            if min_length is not None
            else config.MIN_SENTENCE_LENGTH
        )

        self.remove_empty = (
            remove_empty
            if remove_empty is not None
            else config.REMOVE_EMPTY_SENTENCE
        )
    def is_title(line):
        
        letters = [c for c in line if c.isalpha()]

        if len(letters) < 5:
            return False

        upper = sum(c.isupper() for c in letters)

        return (
            upper / len(letters) > 0.8
            and len(line) < 80
        )
    def split(self, text, work_id="DOC"):
        """
        Trả về:
        [
            {"sentence_id": "HVQ_001_000001", "sentence": "..."},
            {"sentence_id": "HVQ_001_000002", "sentence": "..."},
            ...
        ]
        """

        sentences = sent_tokenize(text)

        results = []
        idx = 1

        for sentence in sentences:

            sentence = sentence.strip()
            sentence = re.sub(r"\s+", " ", sentence)

            if self.remove_empty and len(sentence) == 0:
                continue

            if len(sentence) < self.min_length:
                continue

            sentence_id = f"{work_id}_{idx:06d}"

            results.append({
                "sentence_id": sentence_id,
                "sentence": sentence
            })

            idx += 1

        return results


# ----------------------------------------------------------
# Cho phép chạy trực tiếp file này để test nhanh
# ----------------------------------------------------------
if __name__ == "__main__":

    sample_text = (
        "Ngày 23, làm lễ mở đọc chiếu thư của nhà Minh ở điện Kính Thiên. "
        "Hùng Vương dựng nước là đề tài nghiên cứu quan trọng."
    )

    splitter = SentenceSplitter()

    docs = splitter.split(sample_text, work_id="TEST")

    for doc in docs:
        print(doc["sentence_id"])
        print(doc["sentence"])
        print("=" * 50)
