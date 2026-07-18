# ==========================================================
# dictionary.py
# Historical Dictionary for OCR Correction
# ==========================================================

# ----------------------------------------------------------
# Common OCR mistakes (word-level, upper-case keys)
# ----------------------------------------------------------

OCR_REPLACE = {
    "HQI": "HỘI",
    "NGHI": "NGHỊ",
    "KHÁO": "KHẢO",
    "CÔ": "CỔ",
    "HQC": "HỌC",
    "LICH": "LỊCH",
    "SU": "SỬ",
    "HUNG": "HÙNG",
    "VUONG": "VƯƠNG",
    "DUNG": "DỰNG",
    "NUOC": "NƯỚC",
    "TAP": "TẬP",
    "VIEN": "VIỆN",
    "HA NOI": "HÀ NỘI",
 
    "VIÊC": "VIỆC",
    "THÒI": "THỜI",
    "KY": "KỲ",
    "PHAM": "PHẠM",
    "DONG": "ĐỒNG",
 
    "THOI": "THỜI",
    "VAN": "VĂN",
    "KHAO": "KHẢO",
    "CO": "CỔ",
    "HOC": "HỌC",
    "TAI": "TẠI",
    "HA": "HÀ",
    "NOI": "NỘI",
    "NGAY": "NGÀY",
    "THANG": "THÁNG",
    "NAM": "NĂM",
    "NHA": "NHÀ",
    "XUAT": "XUẤT",
    "BAN": "BẢN",
    "XA": "XÃ",
    "TO": "TỔ",
    "CHUC": "CHỨC",
 
    # ------------------------------------------------------
    # Bộ lỗi dấu thanh riêng của lần OCR "Hùng Vương Dựng Nước"
    # CHỈ giữ các entry ít rủi ro va chạm nghĩa (không trùng với từ
    # thông dụng khác khi bỏ dấu). Các entry như "TINH" (tỉnh/tính/tinh),
    # "VIEN" (viện/viên/viền), "THUOC" (thuộc/thuốc), "TOC" (tộc/tóc),
    # "TUYEN" (tuyên/tuyến), "VINH" (vĩnh/vinh/vịnh), "BO" (bộ/bò/bó)
    # bị bỏ vì đây là dictionary áp dụng cho TOÀN SÁCH — nếu gán cứng
    # sẽ sửa nhầm những từ khác vốn đã đúng ở các trang khác. Những
    # trường hợp này nên để bước LLM+RAG (có ngữ cảnh) xử lý thay vì
    # word-level dictionary.
    # ------------------------------------------------------
    "NGUOI": "NGƯỜI",
    "DJA": "ĐỊA",
    "HGP": "HỢP",
    "HQI": "HỘI",
    "NGHI": "NGHỊ",
    "KHÁO": "KHẢO",
    "CÔ": "CỔ",
    "HQC": "HỌC",
    "LICH": "LỊCH",
    "SU": "SỬ",
    "HUNG": "HÙNG",
    "VUONG": "VƯƠNG",
    "DUNG": "DỰNG",
    "NUOC": "NƯỚC",
    "TAP": "TẬP",
    "VIEN": "VIỆN",
    "HA NOI": "HÀ NỘI",

    "VIÊC": "VIỆC",
    "THÒI": "THỜI",
    "KY": "KỲ",
    "PHAM": "PHẠM",
    "DONG": "ĐỒNG",

    "THOI": "THỜI",
    "VAN": "VĂN",
    "KHAO": "KHẢO",
    "CO": "CỔ",
    "HOC": "HỌC",
    "TAI": "TẠI",
    "HA": "HÀ",
    "NOI": "NỘI",
    "NGAY": "NGÀY",
    "THANG": "THÁNG",
    "NAM": "NĂM",
    "NHA": "NHÀ",
    "XUAT": "XUẤT",
    "BAN": "BẢN",
    "XA": "XÃ",
    "TO": "TỔ",
    "CHUC": "CHỨC",
    
    # Bổ sung từ thực tế văn bản mới
    "MY": "MỸ",
    "THUAT": "THUẬT",
    "NGHE": "NGHỆ",
    "DAN": "DÂN",
    "TOC": "TỘC",
    "KINH": "KINH",
    "TE": "TẾ",
    "HINH": "HÌNH",
    "THAI": "THÁI",
    "NGUOI": "NGƯỜI",
    "DOAN": "ĐOÀN",
    "DIA": "ĐỊA",
    "CHAT": "CHẤT",
    "TUYEN": "TUYÊN",
    "GIAO": "GIÁO",
    "TINH": "TỈNH",
    "UY": "ỦY",
    "VINH": "VĨNH",
    "PHU": "PHÚ",
    "DU'NG": "DỰNG",
    "DU'NG": "DỰNG",
    "NU'Ó'C": "NƯỚC",
    "VU'O'NG": "VƯƠNG",
    "NUÓG": "NƯỚC",
    "tp": "tập",
    "Vițn": "Viện",
    "Khão": "Khảo",
    "hc": "học",
    "Vin": "Viện",
    "TÖ CHÚC": "TỔ CHỨC",
    "H A N Q": "HÀ NỘI",
    "SĆ": "Sử",
    "TRUÙNG": "TRƯỜNG",
    "HQI": "HỘI",
    "CÖ": "CỔ",
    "VIN": "VIN",

    "HU'NG": "HÙNG",
    "LA.C": "LẠC",
    "QUA^N": "QUÂN",

    "CO^": "CƠ",
    "VA(N": "VĂN",
    "DO^NG": "ĐÔNG",

    "PHU`NG": "PHÙNG",
}

# ----------------------------------------------------------
# Common symbol/garbage OCR artifacts -> replacement
# (used by text_corrector.py before dictionary_correct)
# ----------------------------------------------------------

SYMBOL_REPLACE = {

    "|": "",
    "~": "",
    "¬": "",
    "•": "",
    "·": "",
    "…": "...",
    "``": '"',
    "''": '"',
    " ,": ",",
    " .": ".",
}

# ----------------------------------------------------------
# Historical keywords
# ----------------------------------------------------------

HISTORY_TERMS = [

    "Hùng Vương",
    "Văn Lang",
    "Âu Lạc",
    "An Dương Vương",
    "Lạc Việt",
    "Lạc hầu",
    "Lạc tướng",
    "Đông Sơn",
    "Phùng Nguyên",
    "Gò Mun",
    "Đồng Đậu",
    "Trống đồng",
    "Vua Hùng",
    "Nhà nước Văn Lang",
    "Khảo cổ học",
    "Lịch sử",
    "Viện Khảo cổ học",
    "Viện Sử học"

]

# ----------------------------------------------------------
# Historical people -> PER
# ----------------------------------------------------------

PERSONS = [

    "Hồ Chí Minh",
    "Phạm Văn Đồng",
    "Trần Quốc Vượng",
    "Hà Văn Tấn",
    "Đào Duy Anh",
    "Nguyễn Văn Huyên",
    "An Dương Vương",
    "Phạm Huy Thông",
    "Diệp Đình Hoa",
    "Đào Tử Khai",
    "Nguyễn Duy Tỳ",
    "Kinh Dương Vương",
    "Lạc Long Quân"

]

# ----------------------------------------------------------
# Historical locations -> LOC
# ----------------------------------------------------------

LOCATIONS = [

    "Phú Thọ",
    "Hà Nội",
    "Việt Nam",
    "Phong Châu",
    "Việt Trì",
    "Bạch Hạc",
    "Cổ Loa",
    "Đông Sơn",
    "Vĩnh Phú",
    "Gò Bông",
    "Phùng Nguyên",
    "Lâm Thao"

]

# ----------------------------------------------------------
# Organizations -> ORG
# ----------------------------------------------------------

ORGANIZATIONS = [

    "Viện Khảo cổ học",
    "Viện Sử học",
    "Ủy ban Khoa học Xã hội Việt Nam",
    "Bảo tàng Lịch sử",
    "Trường Đại học Tổng hợp",
    
    # Bổ sung các tổ chức mới trích xuất
    "Viện Bảo tàng Lịch sử",
    "Vụ Bảo tồn Bảo tàng",
    "Viện Mỹ thuật Mỹ nghệ",
    "Viện Dân tộc học",
    "Viện Văn học",
    "Viện Kinh tế học",
    "Hội Hình thái người",
    "Đoàn Địa chất 58",
    "Ban Tuyên giáo Tỉnh ủy Vĩnh Phú"
]

# ----------------------------------------------------------
# Frequently corrected phrases (multi-word, upper-case keys)
# ----------------------------------------------------------

PHRASE_MAP = {

    "HQI NGHI": "HỘI NGHỊ",
    "KHÁO CÔ HQC": "KHẢO CỔ HỌC",
    "THÒI KY": "THỜI KỲ",
    "LICH SU": "LỊCH SỬ",
    "HUNG VUONG": "HÙNG VƯƠNG",
    
    "DUNG NUOC": "DỰNG NƯỚC",
    "PHAM VAN DONG": "PHẠM VĂN ĐỒNG",
    "VIEN KHAO CO HOC": "VIỆN KHẢO CỔ HỌC",
    "VIEN SU HOC": "VIỆN SỬ HỌC",
    "UY BAN KHOA HOC XA HOI": "ỦY BAN KHOA HỌC XÃ HỘI",
    
    # Bổ sung map cụm từ viết hoa không dấu của các tổ chức mới
    "VIEN BAO TANG LICH SU": "VIỆN BẢO TÀNG LỊCH SỬ",
    "TRUONG DAI HOC TONG HOP": "TRƯỜNG ĐẠI HỌC TỔNG HỢP",
    "VU BAO TON BAO TANG": "VỤ BẢO TỒN BẢO TÀNG",
    "VIEN MY THUAT MY NGHE": "VIỆN MỸ THUẬT MỸ NGHỆ",
    "VIEN DAN TOC HOC": "VIỆN DÂN TỘC HỌC",
    "VIEN VAN HOC": "VIỆN VĂN HỌC",
    "VIEN KINH TE HOC": "VIỆN KINH TẾ HỌC",
    "HOI HINH THAI NGUOI": "HỘI HÌNH THÁI NGƯỜI",
    "DOAN DIA CHAT 58": "ĐOÀN ĐỊA CHẤT 58",
    "BAN TUYEN GIAO TINH UY VINH PHU": "BAN TUYÊN GIÁO TỈNH ỦY VĨNH PHÚ"
}

# ----------------------------------------------------------
# Stopwords
# ----------------------------------------------------------

STOPWORDS = {

    "và", "là", "của", "có", "được", "những", "các",
    "trong", "với", "đến", "cho", "ở", "một", "này", "đó"

}