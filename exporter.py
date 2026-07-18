# ==========================================================
# exporter.py
# Export Pipeline Results
# ==========================================================

import os
import json
import csv

from docx import Document
from docx.shared import Pt

import config


class Exporter:

    def __init__(self, output_dir=None):

        self.output_dir = output_dir or config.OUTPUT_DIR

        os.makedirs(self.output_dir, exist_ok=True)

    def _path(self, work_id, suffix):
        return os.path.join(self.output_dir, work_id + suffix)

    # ------------------------------------------------------
    # STEP 1: RAW OCR TEXT  -> {work_id}_raw.txt
    # ------------------------------------------------------
    def export_raw(self, text, work_id):

        path = self._path(work_id, config.RAW_SUFFIX)

        with open(path, "w", encoding=config.ENCODING) as f:
            f.write(text)

        return path

    # ------------------------------------------------------
    # STEP 4: SEGMENTATION -> {work_id}_seg.tsv
    # Format mỗi dòng: sentence_id \t sentence
    # ------------------------------------------------------
    def export_segmentation(self, corrected_sentences, work_id):

        path = self._path(work_id, config.SEG_SUFFIX)

        with open(path, "w", encoding=config.ENCODING) as f:

            for item in corrected_sentences:

                f.write(f"{item['sentence_id']}\t{item['sentence']}\n")

        return path

    # ------------------------------------------------------
    # STEP 5: NER -> {work_id}_ner.json
    # Format: [{"sentence_id":..., "sentence":..., "entities":[...]}]
    # ------------------------------------------------------
    def export_ner(self, ner_results, work_id):

        path = self._path(work_id, config.NER_SUFFIX)

        with open(path, "w", encoding=config.ENCODING) as f:

            json.dump(
                ner_results,
                f,
                ensure_ascii=False,
                indent=config.JSON_INDENT
            )

        return path

    # ------------------------------------------------------
    # Tiện ích thêm: xuất CSV danh sách entities (tuỳ chọn)
    # ------------------------------------------------------
    def export_entities_csv(self, ner_results, work_id):

        path = os.path.join(
            self.output_dir,
            work_id + "_entities.csv"
        )

        with open(path, "w", newline="", encoding="utf-8-sig") as csvfile:

            writer = csv.writer(csvfile)

            writer.writerow(["sentence_id", "text", "label", "score"])

            for doc in ner_results:

                for entity in doc["entities"]:

                    writer.writerow([
                        doc.get("sentence_id", ""),
                        entity["text"],
                        entity["label"],
                        entity.get("score", "")
                    ])

        return path

    # ------------------------------------------------------
    # Tiện ích thêm: xuất bản Word cuối cùng (tuỳ chọn)
    # ------------------------------------------------------
    def export_docx(self, corrected_sentences, work_id):

        document = Document()

        style = document.styles["Normal"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(13)

        for item in corrected_sentences:
            document.add_paragraph(item["sentence"])

        path = os.path.join(self.output_dir, work_id + ".docx")

        document.save(path)

        return path

    # ------------------------------------------------------
    # Xuất tất cả cùng lúc (tuỳ chọn, dùng ngoài Main.py nếu cần)
    # ------------------------------------------------------
    def export_all(self, raw_text, corrected_sentences, ner_results, work_id):

        raw_path = self.export_raw(raw_text, work_id)
        seg_path = self.export_segmentation(corrected_sentences, work_id)
        ner_path = self.export_ner(ner_results, work_id)
        csv_path = self.export_entities_csv(ner_results, work_id)
        docx_path = self.export_docx(corrected_sentences, work_id)

        print()
        print("=" * 50)
        print("Export completed")
        print(raw_path)
        print(seg_path)
        print(ner_path)
        print(csv_path)
        print(docx_path)
        print("=" * 50)

        return {
            "raw": raw_path,
            "seg": seg_path,
            "ner": ner_path,
            "csv": csv_path,
            "docx": docx_path
        }
