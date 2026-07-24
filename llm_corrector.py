"""
llm_corrector.py
LLM-based OCR correction using Qwen2.5-3B-Instruct + RAG context (BGE-M3 retriever)
"""

import re
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


SYSTEM_PROMPT = (
    """
Bạn là công cụ hiệu đính OCR tiếng Việt cho sách lịch sử.

Mục tiêu:
- Chỉ sửa lỗi OCR.
- Không viết lại câu.

Quy tắc bắt buộc:

1. Giữ nguyên số lượng câu.
2. Giữ nguyên thứ tự các từ.
3. Không thêm từ.
4. Không bỏ từ.
5. Không thay đổi cách diễn đạt.
6. Chỉ được sửa:
   - ký tự OCR sai
   - dấu tiếng Việt
   - chữ hoa/chữ thường
   - khoảng trắng
   - dấu câu
7. Nếu không chắc chắn, giữ nguyên từ gốc.
8. Chỉ sử dụng ngữ cảnh tham khảo để xác định cách viết đúng của từ, không dùng để viết lại câu.

Đầu ra:
- Chỉ trả về đúng câu đã sửa.
- Không giải thích.
- Không markdown.
- Không thêm ký tự nào khác.
"""
)


class LLMCorrector:

    def __init__(
        self,
        model_path="models/qwen2.5",
        device=None,
        max_new_tokens=128
    ):

        self.model_path = model_path
        self.max_new_tokens = max_new_tokens

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        self.device = device

        print(f"LLMCorrector dùng device: {self.device}")

        print("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

        print("Loading LLM...")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if self.device != "cpu" else torch.float32
        ).to(self.device)

        self.model.eval()

        self._eos_token_ids = self._resolve_eos_token_ids()

    # ------------------------------------------------------
    # Xác định đúng (các) token kết thúc lượt trả lời
    # ------------------------------------------------------
    def _resolve_eos_token_ids(self):
        """
        Qwen dùng token đặc biệt <|im_end|> để đánh dấu hết lượt trong
        chat template, KHÁC với tokenizer.eos_token_id "mặc định" mà
        generate() dùng nếu không chỉ định rõ. Nếu không truyền đúng
        eos_token_id này, model sẽ generate() vượt quá hết lượt trả lời
        và "tưởng tượng" tiếp ra các lượt hội thoại giả (user/assistant)
        cho tới khi chạm max_new_tokens.
        """

        ids = set()

        if self.tokenizer.eos_token_id is not None:
            ids.add(self.tokenizer.eos_token_id)

        im_end_id = self.tokenizer.convert_tokens_to_ids("<|im_end|>")

        if (
            im_end_id is not None
            and im_end_id != self.tokenizer.unk_token_id
        ):
            ids.add(im_end_id)

        return list(ids) if ids else None

    # ------------------------------------------------------
    # Phát hiện output bị suy biến (lặp 1 ký tự/token liên tục)
    # ------------------------------------------------------
    def _looks_degenerate(self, text):

        if len(text) < 8:
            return False

        most_common_count = max(text.count(c) for c in set(text))

        return (most_common_count / len(text)) > 0.5

    # ------------------------------------------------------
    # Build chat prompt
    # ------------------------------------------------------
    def build_messages(self, sentence, contexts):

        context_text = ""

        if contexts:

            if isinstance(contexts, list):

                snippets = []

                for c in contexts:

                    if isinstance(c, dict):
                        snippets.append(c.get("text", ""))
                    else:
                        snippets.append(str(c))

                context_text = "\n".join(s for s in snippets if s)

            else:
                context_text = str(contexts)

        if context_text:
            user_content = (
                f"Ngữ cảnh tham khảo:\n{context_text}\n\n"
                f"Câu OCR cần sửa:\n{sentence}\n\n"
                f"Câu đã sửa (chỉ trả về đúng 1 dòng, không giải thích):"
            )
        else:
            user_content = (
                f"Câu OCR cần sửa:\n{sentence}\n\n"
                f"Câu đã sửa (chỉ trả về đúng 1 dòng, không giải thích):"
            )

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

    # ------------------------------------------------------
    # Correct one sentence
    # ------------------------------------------------------
    def correct(self, sentence, contexts=None):

        if not sentence or not sentence.strip():
            return sentence

        messages = self.build_messages(sentence, contexts)

        prompt_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(
            prompt_text,
            return_tensors="pt"
        ).to(self.device)

        generate_kwargs = dict(
            max_new_tokens=self.max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
            # Chống lặp vô hạn kiểu "!!!!!!!!" khi model bí với câu OCR
            # quá nát để hiểu.
            repetition_penalty=1.15,
            no_repeat_ngram_size=4,
        )

        if self._eos_token_ids:
            generate_kwargs["eos_token_id"] = self._eos_token_ids

        with torch.no_grad():

            output_ids = self.model.generate(
                **inputs,
                **generate_kwargs
            )

        generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]

        result = self.tokenizer.decode(
            generated_ids,
            skip_special_tokens=True
        ).strip()

        # Lá chắn cuối: nếu model vẫn lỡ sinh thêm hội thoại giả
        # (bắt đầu bằng "user", "Human:", xuống dòng...), chỉ giữ
        # đúng dòng đầu tiên - đó mới là câu trả lời thật.
        result = result.split("\n")[0].strip()

        # Bỏ dấu nháy thừa nếu model tự bọc câu trả lời trong ngoặc kép
        result = re.sub(r'^[\"\'“”]|[\"\'“”]$', "", result).strip()

        # Nếu output rỗng hoặc bị suy biến (lặp 1 ký tự liên tục),
        # coi như sửa thất bại, giữ nguyên câu OCR gốc thay vì trả về
        # rác - an toàn hơn cho bước NER phía sau.
        if not result or self._looks_degenerate(result):
            return sentence

        return result
