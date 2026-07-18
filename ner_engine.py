# ==========================================================
# ner_engine.py
# Vietnamese NER + Historical Dictionary
# Output labels: PER, LOC, ORG, TITLE, TME, NUM, DYNASTY
# ==========================================================

import re
from transformers import pipeline

import config
from dictionary import PERSONS, LOCATIONS, ORGANIZATIONS


# Chuẩn hoá nhãn trả về từ model transformer (PERSON/LOCATION/...)
# về đúng bộ nhãn rút gọn mà pipeline cần.
LABEL_MAP = {
    "PERSON": "PER",
    "PER": "PER",
    "LOCATION": "LOC",
    "LOC": "LOC",
    "ORGANIZATION": "ORG",
    "ORG": "ORG",
}


class NERProcessor:

    def __init__(
        self,
        model_name="NlpHUST/ner-vietnamese-electra-base"
    ):

        print("Loading NER model...")

        self.ner = pipeline(
            "token-classification",
            model=model_name,
            tokenizer=model_name,
            aggregation_strategy="simple"
        )

        # Từ dài trước để tránh match nhầm (vd "phó chủ tịch" trước "chủ tịch")
        self.title_words = sorted(
            config.TITLE_WORDS,
            key=len,
            reverse=True
        ) if config.ENABLE_TITLE else []

        self.dynasties = sorted(
            config.DYNASTIES,
            key=len,
            reverse=True
        ) if config.ENABLE_DYNASTY else []

        self.time_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in config.TIME_PATTERNS
        ] if config.ENABLE_TIME else []

        self.num_pattern = re.compile(r"\d+([.,]\d+)?") if config.ENABLE_NUM else None

    # ------------------------------------------------------
    # Dictionary Matching -> PER / LOC / ORG
    # ------------------------------------------------------
    def dictionary_matching(self, text):

        entities = []

        for item in PERSONS:
            if item in text:
                entities.append({"text": item, "label": "PER"})

        for item in LOCATIONS:
            if item in text:
                entities.append({"text": item, "label": "LOC"})

        for item in ORGANIZATIONS:
            if item in text:
                entities.append({"text": item, "label": "ORG"})

        return entities

    # ------------------------------------------------------
    # TITLE (chức danh) -> TITLE
    # ------------------------------------------------------
    def title_matching(self, text):

        entities = []
        lower_text = text.lower()

        for word in self.title_words:

            idx = lower_text.find(word.lower())

            if idx != -1:
                entities.append({
                    "text": text[idx:idx + len(word)],
                    "label": "TITLE"
                })

        return entities

    # ------------------------------------------------------
    # DYNASTY (triều đại) -> DYNASTY
    # ------------------------------------------------------
    def dynasty_matching(self, text):

        entities = []

        for name in self.dynasties:
            if name in text:
                entities.append({"text": name, "label": "DYNASTY"})

        return entities

    # ------------------------------------------------------
    # TME (biểu thức thời gian) -> TME
    # ------------------------------------------------------
    def time_matching(self, text):

        entities = []

        for pattern in self.time_patterns:
            for m in pattern.finditer(text):
                entities.append({"text": m.group(0), "label": "TME"})

        return entities

    # ------------------------------------------------------
    # NUM (số không nằm trong TME) -> NUM
    # ------------------------------------------------------
    def num_matching(self, text, time_spans):

        entities = []

        if self.num_pattern is None:
            return entities

        for m in self.num_pattern.finditer(text):

            start, end = m.start(), m.end()

            overlap = any(
                start < s_end and end > s_start
                for s_start, s_end in time_spans
            )

            if not overlap:
                entities.append({"text": m.group(0), "label": "NUM"})

        return entities

    # ------------------------------------------------------
    # Transformer NER -> PER / LOC / ORG
    # ------------------------------------------------------
    def transformer_ner(self, text):

        raw_results = self.ner(text)

        entities = []

        for r in raw_results:

            label = LABEL_MAP.get(r["entity_group"].upper())

            if label is None:
                continue

            entities.append({
                "text": r["word"],
                "label": label,
                "score": round(float(r["score"]), 4)
            })

        return entities

    # ------------------------------------------------------
    # Merge duplicated entities (giữ bản ghi đầu tiên)
    # ------------------------------------------------------
    def merge(self, entities):

        seen = set()
        output = []

        for item in entities:

            key = (item["text"], item["label"])

            if key in seen:
                continue

            seen.add(key)
            output.append(item)

        return output

    # ------------------------------------------------------
    # Process 1 câu -> dict đúng format yêu cầu
    # ------------------------------------------------------
    def process(self, sentence_id, sentence):

        entities = []

        entities += self.transformer_ner(sentence)
        entities += self.dictionary_matching(sentence)
        entities += self.title_matching(sentence)
        entities += self.dynasty_matching(sentence)

        time_entities = self.time_matching(sentence)
        entities += time_entities

        time_spans = [
            (
                sentence.find(e["text"]),
                sentence.find(e["text"]) + len(e["text"])
            )
            for e in time_entities
            if sentence.find(e["text"]) != -1
        ]

        entities += self.num_matching(sentence, time_spans)

        entities = self.merge(entities)

        return {
            "sentence_id": sentence_id,
            "sentence": sentence,
            "entities": entities
        }
