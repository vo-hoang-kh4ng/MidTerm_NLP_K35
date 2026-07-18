"""
text_corrector.py
OCR Post-processing (rule/dictionary based, chạy trước bước LLM correction)
"""

import re

from dictionary import OCR_REPLACE, SYMBOL_REPLACE, PHRASE_MAP


class TextCorrector:

    def __init__(self):

        self.replace_dict = OCR_REPLACE
        self.symbol_dict = SYMBOL_REPLACE
        self.phrase_map = PHRASE_MAP

    def normalize_space(self, text):

        text = text.replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)

        return text.strip()

    def replace_symbols(self, text):

        for old, new in self.symbol_dict.items():
            text = text.replace(old, new)

        return text

    def join_split_characters(self, text):
        """
        Nối các "từ" mà OCR tách thành từng CHỮ CÁI ĐƠN LẺ riêng biệt.
        """
        lines = text.split("\n")
        result_lines = []

        for line in lines:

            tokens = line.split(" ")
            merged = []
            buffer = []

            for tok in tokens:

                if len(tok) == 1 and tok.isalpha():
                    buffer.append(tok)
                    continue

                if len(buffer) >= 2:
                    merged.append("".join(buffer))
                else:
                    merged.extend(buffer)

                buffer = []
                merged.append(tok)

            if len(buffer) >= 2:
                merged.append("".join(buffer))
            else:
                merged.extend(buffer)

            result_lines.append(" ".join(merged))

        return "\n".join(result_lines)

    def split_stuck_uppercase_words(self, text):
        """
        BỔ SUNG: Sửa lỗi dính chữ viết hoa cực kỳ phổ biến trong sách scan.
        Ví dụ: "NHÀXUATBANKHOA" -> "NHÀ XUẤT BẢN KHOA"
        """
        stuck_maps = {
            r"NHÀXUẤTBẢNKHOAHỌCXÃHỘI": "NHÀ XUẤT BẢN KHOA HỌC XÃ HỘI",
            r"NHÀXUATBANKHOA": "NHÀ XUẤT BẢN KHOA HỌC XÃ HỘI",
            r"NHÀXUẤTBẢN": "NHÀ XUẤT BẢN",
            r"KHOAHỌCXÃHỘI": "KHOA HỌC XÃ HỘI",
            r"KHẢOCỔHỌC": "KHẢO CỔ HỌC",
            r"HÙNGVƯƠNG": "HÙNG VƯƠNG",
            r"DỰNGNƯỚC": "DỰNG NƯỚC",
        }
        for pattern, replacement in stuck_maps.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            
        # Tách tự động dựa trên biên chữ hoa viết liền kề chữ thường (vd: "ViệnKhảoCổ" -> "Viện Khảo Cổ")
        text = re.sub(r"([a-zđàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ])([A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸY])", r"\1 \2", text)
        return text

    def phrase_correct(self, text):
        """
        Thay cụm từ theo PHRASE_MAP, GIỮ ĐÚNG case gốc của cụm từ trong văn bản.
        """
        # BỔ SUNG: Khai báo cứng các cụm từ lỗi nặng bị rã chữ đặc trưng của tài liệu này
        local_phrases = {
            "lich s": "lịch sử",
            "Vin S hc": "Viện Sử học",
            "Vin s hoc": "Viện Sử học",
            "tp I": "tập I",
            "tp 1": "tập 1",
            "DļNG NUÓC": "DỰNG NƯỚC",
            "Vițn Khão cō hc": "Viện Khảo cổ học",
            "Vin Båo tàng": "Viện Bảo tàng",
            "Trưòng đi hęc": "Trường Đại học",
            "Tông hợp": "Tổng hợp",
            "V Bão tōn bão tàng": "Viện Bảo tồn Bảo tàng",
            "Viln Mū thut mū nghě": "Viện Mỹ thuật Mỹ nghệ",
            "Vin Dân tőc hc": "Viện Dân tộc học",
            "Vin Vǎn hc": "Viện Văn học",
            "Vin Kinh té học": "Viện Kinh tế học",
            "Hi Hình thái nguòi": "Hội Hình thái người",
            "Đoàn Đa chát": "Đoàn Địa chất",
            "Tuyên giáo Tỉnh y": "Tuyên giáo Tỉnh uỷ",
            "Vīnh Phú": "Vĩnh Phú",
            "H A N Q1": "HÀ NỘI",
            "PHÁT BIÊU": "PHÁT BIỂU",
            "PHÕI HQP": "PHỐI HỢP",
            "VI VIN SĆ HOC": "VỚI VIỆN SỬ HỌC",
            "TÔNG HP": "TỔNG HỢP"
        }

        # Áp dụng bộ sửa cụm từ ưu tiên trước
        for wrong, right in local_phrases.items():
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            def replacer(match, right=right):
                original = match.group(0)
                if original.isupper():
                    return right.upper()
                elif original.islower():
                    return right.lower()
                elif original[0].isupper():
                    return right.capitalize()
                return right
            text = pattern.sub(replacer, text)

        # Áp dụng PHRASE_MAP từ dictionary.py sau
        for wrong, right in self.phrase_map.items():
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            def replacer(match, right=right):
                original = match.group(0)
                if original.isupper():
                    return right.upper()
                elif original.islower():
                    return right.lower()
                elif original[0].isupper():
                    return right.capitalize()
                return right
            text = pattern.sub(replacer, text)

        return text

    def dictionary_correct(self, text):
        """
        Thay thế từ đơn lẻ theo OCR_REPLACE từ dictionary.py.
        """
        # BỔ SUNG: Khai báo bổ sung trực tiếp các từ đơn lẻ bị lỗi quét font/ký tự lạ
        local_single_words = {
            "Vițn": "Viện",
            "Khão": "Khảo",
            "cō": "cổ",
            "hc": "học",
            "Vin": "Viện",
            "Viln": "Viện",
            "thut": "thuật",
            "nghě": "nghệ",
            "trưòng": "trường",
            "đị": "đại",
            "hęc": "học",
            "bão": "bảo",
            "tōn": "tồn",
            "lich": "lịch",
            "nhur": "như",
            "bân": "ban",
            "y": "uỷ",
            "uỷ": "uỷ",
            "Vīnh": "Vĩnh",
            "VIÊT": "VIỆT"
        }

        # 1. Chạy qua bộ lọc sửa lỗi đơn lẻ cục bộ trước
        words = text.split(" ")
        corrected = []
        for w in words:
            # Loại bỏ dấu câu bám ở rìa từ để khớp chính xác
            clean_word = re.sub(r"^[^\w\s]+|[^\w\s]+$", "", w)
            if clean_word in local_single_words:
                w = w.replace(clean_word, local_single_words[clean_word])
            elif clean_word.lower() in local_single_words:
                replaced = local_single_words[clean_word.lower()]
                if clean_word.istitle():
                    replaced = replaced.capitalize()
                elif clean_word.isupper():
                    replaced = replaced.upper()
                w = w.replace(clean_word, replaced)
            corrected.append(w)
            
        text = " ".join(corrected)

        # 2. Chạy qua bộ lọc OCR_REPLACE mặc định của dictionary.py
        punct_chars = ",.;:!?()[]\"'"
        words_step2 = text.split()
        final_corrected = []

        for w in words_step2:
            stripped = w.strip(punct_chars)
            if not stripped:
                final_corrected.append(w)
                continue

            lead_len = len(w) - len(w.lstrip(punct_chars))
            trail_len = len(w) - len(w.rstrip(punct_chars))

            leading = w[:lead_len]
            trailing = w[len(w) - trail_len:] if trail_len else ""

            key = stripped.upper()

            if key in self.replace_dict:
                replacement = self.replace_dict[key]
                if stripped.isupper():
                    replacement = replacement.upper()
                elif stripped.islower():
                    replacement = replacement.lower()
                elif stripped[0].isupper():
                    replacement = replacement.capitalize()

                final_corrected.append(leading + replacement + trailing)
            else:
                final_corrected.append(w)

        return " ".join(final_corrected)

    def fix_punctuation(self, text):
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)
        text = re.sub(r"([.,;:!?])([^\s])", r"\1 \2", text)
        return text

    def correct(self, text):
        text = self.normalize_space(text)
        text = self.replace_symbols(text)
        text = self.split_stuck_uppercase_words(text) # <-- Chạy tách dính đầu tiên
        text = self.join_split_characters(text)
        text = self.phrase_correct(text)             # <-- Chạy sửa cụm từ trước để xử lý "lich s", "Vien s hoc"
        text = self.dictionary_correct(text)         # <-- Chạy sửa từ đơn lẻ sau
        text = self.fix_punctuation(text)
        return text