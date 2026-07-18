"""
eval_sample_page3.py
Đo Character Error Rate (CER) giữa output pipeline và ground truth đã
xác nhận bằng mắt (đối chiếu ảnh gốc), cho 1 đoạn cụ thể (trang 3 sách
"Hùng Vương Dựng Nước" tập 1).

Dùng để đo khách quan mức cải thiện mỗi khi sửa code (dictionary, LLM
correction, tiền xử lý ảnh...) thay vì chỉ đánh giá cảm tính.

CER = số phép chỉnh sửa ký tự cần thiết (Levenshtein distance)
      chia cho độ dài chuỗi ground truth. CER càng thấp càng tốt
      (0.0 = hoàn hảo, 1.0 = sai hoàn toàn).

Cách dùng:
    python eval_sample_page3.py "đường dẫn tới file .txt chứa output cần đo"
"""

import sys


GROUND_TRUTH = (
    "Các tác giả của những bài nghiên cứu và tham luận in trong "
    "HÙNG VƯƠNG DỰNG NƯỚC tập I là cán bộ thuộc nhiều cơ quan, như "
    "Viện Khảo cổ học, Viện Sử học, Viện Bảo tàng lịch sử, Trường đại "
    "học Tổng hợp, Vụ Bảo tồn bảo tàng, Viện Mỹ thuật mỹ nghệ, Viện "
    "Dân tộc học, Viện Văn học, Viện Kinh tế học, Hội Hình thái người, "
    "Đoàn Địa chất 58, Ban Tuyên giáo Tỉnh ủy Vĩnh Phú."
)


def levenshtein(a, b):

    if len(a) < len(b):
        a, b = b, a

    previous_row = list(range(len(b) + 1))

    for i, ca in enumerate(a, 1):

        current_row = [i]

        for j, cb in enumerate(b, 1):

            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (ca != cb)

            current_row.append(min(insertions, deletions, substitutions))

        previous_row = current_row

    return previous_row[-1]


def normalize_for_compare(text):
    # Chuẩn hoá khoảng trắng để không tính nhầm lỗi do xuống dòng/
    # khoảng trắng thừa (vốn không phải lỗi nhận diện ký tự thật)
    return " ".join(text.split())


def cer(hypothesis, reference):

    hyp = normalize_for_compare(hypothesis)
    ref = normalize_for_compare(reference)

    distance = levenshtein(hyp, ref)

    return distance / len(ref) if ref else 0.0


def main():

    if len(sys.argv) < 2:
        print("Cách dùng: python eval_sample_page3.py <file.txt>")
        print()
        print("Hoặc dán trực tiếp text cần đo qua stdin:")
        print('  echo "text cần đo" | python eval_sample_page3.py -')
        sys.exit(1)

    if sys.argv[1] == "-":
        hypothesis = sys.stdin.read()
    else:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            hypothesis = f.read()

    error_rate = cer(hypothesis, GROUND_TRUTH)

    print(f"Ground truth : {len(normalize_for_compare(GROUND_TRUTH))} ký tự")
    print(f"Hypothesis   : {len(normalize_for_compare(hypothesis))} ký tự")
    print(f"CER          : {error_rate:.4f} ({error_rate * 100:.2f}%)")
    print()

    if error_rate == 0:
        print("=> HOÀN HẢO, khớp 100% với ground truth")
    elif error_rate < 0.05:
        print("=> Rất tốt (dưới 5% lỗi)")
    elif error_rate < 0.15:
        print("=> Khá tốt (5-15% lỗi)")
    elif error_rate < 0.30:
        print("=> Còn nhiều lỗi (15-30%)")
    else:
        print("=> Chất lượng kém (trên 30% lỗi)")


if __name__ == "__main__":
    main()
