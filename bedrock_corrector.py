"""
bedrock_corrector.py
OCR correction using OpenAI GPT-OSS on Amazon Bedrock
"""

import json
import re
import time
import logging
import boto3
from botocore.exceptions import ClientError

import config
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Bạn là một chuyên gia phục hồi và sửa lỗi OCR tiếng Việt cho tài liệu lịch sử Việt Nam.

MỤC TIÊU:
Sửa sạch toàn bộ lỗi chính tả, lỗi quét ký tự sai của công cụ OCR để đưa văn bản về tiếng Việt chuẩn có nghĩa nhất.

QUY TẮC CỰC KỲ QUAN TRỌNG:
1. Hãy sửa các lỗi quét sai ký tự hiển nhiên (Ví dụ: "cán bō thuțc" -> "cán bộ thuộc", "Khão cō hc" -> "Khảo cổ học", "VIỆT NĂM" -> "VIỆT NAM", "HÀN QUỐC - 19704 L" -> "HÀ NỘI - 1970", "JUUM lun" -> "luận").
2. Sử dụng tài liệu tham khảo (RAG) để xác định đúng tên cơ quan, tên riêng nếu có, nhưng KHÔNG bắt chước các từ bị lỗi chính tả hoặc từ vô nghĩa từ tài liệu RAG.
3. Không được viết lại câu, không thêm bớt ý, không tóm tắt câu. Giữ nguyên cấu trúc gốc của câu.
4. Giữ nguyên các marker ID dạng [[[HVQ_xxx_xxxxxx]]] tại đúng vị trí của chúng.
5. Chỉ trả về kết quả văn bản đã sửa. Không giải thích, không markdown code block, không suy luận dài dòng.
""".strip()


class BedrockCorrector:

    def __init__(
        self,
        max_tokens=2048,
        temperature=0,
        max_retries=3,
    ):

        self.model_id = config.BEDROCK_MODEL_ID
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=config.BEDROCK_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
            aws_session_token=config.AWS_SESSION_TOKEN or None,
        )

    def build_prompt(self, sentence, contexts):
        
        context_text = ""

        if contexts:
            snippets = []
            for c in contexts:
                if isinstance(c, dict):
                    snippets.append(c["text"])
                else:
                    snippets.append(str(c))
            context_text = "\n\n".join(snippets)
        else:
            context_text = "Không có tài liệu tham khảo phù hợp."

        return f"""
============================
TÀI LIỆU THAM KHẢO CHUẨN (RAG)
{context_text}

============================
VĂN BẢN OCR LỖI CẦN SỬA CHÍNH TẢ
{sentence}

============================
YÊU CẦU:
Hãy đối chiếu văn bản OCR lỗi với tài liệu tham khảo để sửa chính xác các lỗi gõ sai, mất dấu, dính từ, hoặc sai lệch ký tự.
Nếu tài liệu tham khảo không bao phủ hết, hãy dùng kiến thức tiếng Việt chuẩn của bạn để tự động khôi phục các từ bị lỗi OCR rõ ràng (ví dụ như khôi phục "DļNG NUÓC" thành "DỰNG NƯỚC", "Vițn" thành "Viện",...).

Đặc biệt lưu ý: Giữ nguyên 100% các ID marker dạng [[[...]]].
Chỉ trả về văn bản đã phục hồi lỗi hoàn chỉnh, không kèm giải thích hay bất kỳ ký tự nào khác.
"""

    def _invoke(self, prompt):
    
        body = {
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": self.temperature,
            # TĂNG LÊN 4096 để tránh bị lỗi "finish_reason": "length" khi mô hình suy luận sâu
            "max_completion_tokens": 4096 
        }

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"--- [Bedrock API] Đang gửi Request lần {attempt} tới model: {self.model_id} ---")

                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )

                response_body = json.loads(
                    response["body"].read()
                )

                result = response_body["choices"][0]["message"]["content"]

                # SỬA REGEX TẠI ĐÂY: Xử lý xóa bỏ phần reasoning linh hoạt
                # Trường hợp 1: Có đầy đủ cặp thẻ đóng mở <reasoning>...</reasoning>
                if "<reasoning>" in result and "</reasoning>" in result:
                    result = re.sub(r"<reasoning>.*?</reasoning>", "", result, flags=re.S).strip()
                # Trường hợp 2: Bị cắt ngang nửa chừng, chỉ có thẻ mở <reasoning> và text kéo dài đến hết chuỗi
                elif "<reasoning>" in result:
                    result = re.sub(r"<reasoning>.*$", "", result, flags=re.S).strip()

                result = result.replace("```", "").strip()
                return result

            except ClientError as e:
                last_error = e
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("ThrottlingException", "TooManyRequestsException"):
                    logger.warning(f"Retry {attempt}/{self.max_retries} do bị giới hạn API tốc độ gọi")
                    time.sleep(2 * attempt)
                    continue
                logger.error(f"Lỗi ClientError từ phía AWS: {e}")
                break

        raise RuntimeError(
            f"Gọi Bedrock thất bại sau {self.max_retries} lần: {last_error}"
        )

    def correct(self, sentence, contexts=None):
        if not sentence.strip():
            return sentence

        logger.info("\n" + "="*50 + "\n[Bedrock] ---> NHẬN ĐẦU VÀO OCR LỖI:\n" + sentence + "\n" + "="*50)

        prompt = self.build_prompt(sentence, contexts)
        try:
            result = self._invoke(prompt)
            if result:
                logger.info("\n" + "="*50 + "\n[Bedrock] <--- ĐÃ NHẬN ĐẦU RA SỬA LỖI:\n" + result + "\n" + "="*50)
                return result
        except Exception as e:
            logger.exception(f"[Bedrock LỖI CRITICAL] Gặp ngoại lệ khi gọi API:")

        return sentence