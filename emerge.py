import fitz

pdf_files = [
    os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 1.pdf"),
    os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 2.pdf"),
    os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 3.pdf"),
    os.path.join(config.INPUT_DIR, "Hùng Vương Dựng Nước tập 4.pdf"),
]

merged_pdf = os.path.join(config.INPUT_DIR, "HVQ_ALL.pdf")

doc = fitz.open()

for f in pdf_files:
    src = fitz.open(f)
    doc.insert_pdf(src)
    src.close()

doc.save(merged_pdf)
doc.close()