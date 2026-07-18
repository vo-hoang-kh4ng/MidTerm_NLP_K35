import re
import unicodedata


class TextNormalizer:

    def __init__(self):

        self.char_map = {

            "“": '"',
            "”": '"',
            "„": '"',

            "‘": "'",
            "’": "'",
            "‚": "'",

            "–": "-",
            "—": "-",
            "−": "-",

            "•": "",
            "·": "",

            "\u00A0": " ",
            "\t": " ",
            "\r": "\n"
        }

    # ---------------------------------------------
    # Unicode NFC
    # ---------------------------------------------
    def unicode_normalize(
        self,
        text
    ):

        return unicodedata.normalize(
            "NFC",
            text
        )

    # ---------------------------------------------
    # Replace strange characters
    # ---------------------------------------------
    def replace_special_characters(
        self,
        text
    ):

        for old, new in self.char_map.items():

            text = text.replace(
                old,
                new
            )

        return text

    # ---------------------------------------------
    # Remove invisible characters
    # ---------------------------------------------
    def remove_control_characters(
        self,
        text
    ):

        text = "".join(

            c

            for c in text

            if unicodedata.category(c)[0] != "C"

            or c == "\n"

        )

        return text

    # ---------------------------------------------
    # Merge spaces
    # ---------------------------------------------
    def normalize_spaces(
        self,
        text
    ):

        text = re.sub(
            r"[ ]+",
            " ",
            text
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        return text.strip()

    # ---------------------------------------------
    # Remove OCR garbage
    # ---------------------------------------------
    def remove_noise(
        self,
        text
    ):

        text = re.sub(
            r"[□■◆▲▼◄►◎◇○●※]+",
            "",
            text
        )

        text = re.sub(
            r"[=]{4,}",
            "",
            text
        )

        text = re.sub(
            r"[_]{4,}",
            "",
            text
        )

        return text

    # ---------------------------------------------
    # Normalize punctuation spacing
    # ---------------------------------------------
    def normalize_punctuation(
        self,
        text
    ):

        text = re.sub(
            r"\s+([,.;:!?])",
            r"\1",
            text
        )

        text = re.sub(
            r"([,.;:!?])([^\s])",
            r"\1 \2",
            text
        )

        return text

    # ---------------------------------------------
    # Main
    # ---------------------------------------------
    def normalize(
        self,
        text
    ):

        text = self.unicode_normalize(
            text
        )

        text = self.replace_special_characters(
            text
        )

        text = self.remove_control_characters(
            text
        )

        text = self.remove_noise(
            text
        )

        text = self.normalize_spaces(
            text
        )

        text = self.normalize_punctuation(
            text
        )

        return text