import io
import logging
import cv2
import fitz
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
import unicodedata
logger = logging.getLogger(__name__)


class OCRProcessor:

    def __init__(
        self,
        dpi=600,
        lang="vi",
        score_threshold=0.1
    ):

        self.dpi = dpi
        self.score_threshold = score_threshold

        logger.info("Loading PaddleOCR...")

        self.ocr = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True
        )

        logger.info("PaddleOCR loaded.")
    #Preprocess
    def preprocess(self, image):
        
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        # tăng tương phản
        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8,8)
        )

        gray = clahe.apply(gray)

        # khử nhiễu nhẹ
        gray = cv2.fastNlMeansDenoising(gray)

        # sharpen
        kernel = np.array([
            [-1,-1,-1],
            [-1, 9,-1],
            [-1,-1,-1]
        ])

        gray = cv2.filter2D(gray,-1,kernel)

        # PaddleOCR 3.x yêu cầu ảnh 3 channel
        rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

        return rgb
    # -----------------------------------------------------
    # PDF -> Image
    # -----------------------------------------------------

    def pdf_to_images(self,pdf_path):
    
        doc = fitz.open(pdf_path)

        pages=[]

        for page in doc:

            pix = page.get_pixmap(
                dpi=self.dpi,
                alpha=False
            )

            img = Image.open(io.BytesIO(pix.tobytes("png")))

            img=np.array(img)

            img=self.preprocess(img)

            pages.append(img)

        doc.close()

        return pages
    # -----------------------------------------------------
    # OCR One Page
    # -----------------------------------------------------

    def ocr_page(self,image):
    
        result=self.ocr.predict(image)

        if len(result)==0:
            return []

        result=result[0]

        polys=result["dt_polys"]
        texts=result["rec_texts"]
        scores=result["rec_scores"]

        lines=[]

        for poly,text,score in zip(polys,texts,scores):

            if score<self.score_threshold:
                continue
            text = unicodedata.normalize("NFC", text.strip())

            x=int(poly[:,0].min())
            y=int(poly[:,1].min())

            lines.append({
                "x":x,
                "y":y,
                "text":text.strip(),
                "score":float(score)
            })
        line_tol = 15

        rows = []

        for item in lines:

            found = False

            for row in rows:

                if abs(item["y"] - row["y"]) <= line_tol:

                    row["items"].append(item)

                    found = True

                    break

            if not found:

                rows.append({
                    "y": item["y"],
                    "items": [item]
                })

        rows.sort(key=lambda r:r["y"])

        merged = []

        for row in rows:

            row["items"].sort(key=lambda x:x["x"])

            merged.append({

                "x":row["items"][0]["x"],

                "y":row["y"],

                "text":" ".join(
                    i["text"]
                    for i in row["items"]
                ),

                "score":sum(
                    i["score"]
                    for i in row["items"]
                )/len(row["items"])
            })

        return merged


    # -----------------------------------------------------
    # OCR PDF
    # -----------------------------------------------------

    def extract_text(self,pdf_path):
    
        pages=self.pdf_to_images(pdf_path)

        output=[]

        total=len(pages)

        for i,page in enumerate(pages,1):

            logger.info("OCR %d/%d",i,total)

            lines=self.ocr_page(page)

            for line in lines:
                output.append(line["text"])

            output.append("")

        return "\n".join(output)