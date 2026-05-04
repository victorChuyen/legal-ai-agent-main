"""
Cấu trúc chuyên mục pháp lý cho Legal AI Agent.
Mapping theo đúng cấu trúc Google Drive đã tạo từ Apps Script.
Root Folder ID: 1nPtObLJuMjolevyJVsnxZKqhwZpyx3fI
"""

ROOT_FOLDER_ID = "1nPtObLJuMjolevyJVsnxZKqhwZpyx3fI"

# Cấu trúc folder Drive ánh xạ chính xác từ Apps Script
LEGAL_STRUCTURE = {
    "01_Doanh_Nghiep": {
        "subfolders": [
            "Thanh_Lap_Doanh_Nghiep",
            "Quan_Tri_Noi_Bo",
            "Hop_Dong_Thuong_Mai",
            "Giai_The_Pha_San"
        ],
        "keywords": ["doanh nghiệp", "công ty", "thành lập", "cổ phần", "đăng ký kinh doanh",
                      "giải thể", "phá sản", "hợp đồng thương mại", "quản trị", "điều lệ"]
    },
    "02_Lao_Dong": {
        "subfolders": [
            "Hop_Dong_Lao_Dong",
            "Bao_Hiem_Xa_Hoi",
            "Ky_Luat_Lao_Dong",
            "Tranh_Chap_Lao_Dong"
        ],
        "keywords": ["lao động", "thử việc", "lương", "bảo hiểm xã hội", "nghỉ phép",
                      "tăng ca", "hợp đồng lao động", "sa thải", "kỷ luật", "tranh chấp lao động"]
    },
    "03_Dat_Dai_Bat_Dong_San": {
        "subfolders": [
            "Chuyen_Nhuong_QSD_Dat",
            "Hop_Dong_Mua_Ban_BDS",
            "Quy_Hoach_Xay_Dung",
            "Tranh_Chap_Dat_Dai"
        ],
        "keywords": ["đất đai", "sổ đỏ", "sổ hồng", "quyền sử dụng đất", "bất động sản",
                      "xây dựng", "quy hoạch", "chuyển nhượng", "bồi thường", "giải phóng mặt bằng"]
    },
    "04_Thue": {
        "subfolders": [
            "Thue_GTGT",
            "Thue_TNDN",
            "Thue_TNCN",
            "Uu_Dai_Thue"
        ],
        "keywords": ["thuế", "gtgt", "tndn", "tncn", "giá trị gia tăng",
                      "quyết toán", "kê khai", "ưu đãi thuế", "hóa đơn"]
    },
    "05_Dau_Tu_Nuoc_Ngoai": {
        "subfolders": [
            "Giay_Phep_Dau_Tu",
            "Hiep_Dinh_Thuong_Mai",
            "Chuyen_Loi_Nhuan_Ve_Nuoc",
            "M_A"
        ],
        "keywords": ["đầu tư nước ngoài", "fdi", "giấy phép đầu tư", "hiệp định",
                      "chuyển lợi nhuận", "mua bán sáp nhập", "m&a"]
    },
    "06_So_Huu_Tri_Tue": {
        "subfolders": [
            "Nhan_Hieu",
            "Sang_Che",
            "Ban_Quyen",
            "Bien_Phap_Bao_Ve"
        ],
        "keywords": ["sở hữu trí tuệ", "nhãn hiệu", "sáng chế", "bản quyền",
                      "thương hiệu", "kiểu dáng", "bí mật kinh doanh"]
    },
    "07_To_Tung": {
        "subfolders": [
            "Dan_Su",
            "Hinh_Su",
            "Hanh_Chinh",
            "Trong_Tai_Thuong_Mai"
        ],
        "keywords": ["tố tụng", "dân sự", "khiếu nại", "tố cáo", "trọng tài",
                      "hành chính", "khởi kiện", "thủ tục"]
    },
    "08_Hinh_Su": {
        "subfolders": [
            "Bo_Luat_Hinh_Su",
            "To_Tung_Hinh_Su",
            "Cac_Toi_Danh_Thuong_Gap"
        ],
        "keywords": ["hình sự", "tội phạm", "truy tố", "tù", "phạt tiền", "tội danh"]
    }
}


def detect_category(title, doc_type=""):
    """Phát hiện chuyên mục dựa trên tiêu đề và loại văn bản."""
    text = f"{title} {doc_type}".lower()
    
    best_match = None
    best_score = 0
    
    for cat_key, cat_data in LEGAL_STRUCTURE.items():
        score = sum(1 for kw in cat_data["keywords"] if kw in text)
        if score > best_score:
            best_score = score
            best_match = cat_key
    
    return best_match if best_match else "01_Doanh_Nghiep"


def detect_subfolder(title, category_key):
    """Phát hiện thư mục ngách phù hợp nhất trong chuyên mục."""
    subfolders = LEGAL_STRUCTURE.get(category_key, {}).get("subfolders", [])
    if not subfolders:
        return None
    
    text = title.lower()
    # Logic đơn giản: map keyword sang subfolder
    subfolder_keywords = {
        # Doanh nghiệp
        "Thanh_Lap_Doanh_Nghiep": ["thành lập", "đăng ký"],
        "Quan_Tri_Noi_Bo": ["quản trị", "điều lệ", "nội bộ"],
        "Hop_Dong_Thuong_Mai": ["hợp đồng", "thương mại"],
        "Giai_The_Pha_San": ["giải thể", "phá sản"],
        # Lao động
        "Hop_Dong_Lao_Dong": ["hợp đồng lao động", "thử việc"],
        "Bao_Hiem_Xa_Hoi": ["bảo hiểm", "bhxh"],
        "Ky_Luat_Lao_Dong": ["kỷ luật", "sa thải"],
        "Tranh_Chap_Lao_Dong": ["tranh chấp"],
        # Đất đai
        "Chuyen_Nhuong_QSD_Dat": ["chuyển nhượng", "quyền sử dụng"],
        "Hop_Dong_Mua_Ban_BDS": ["mua bán", "bất động sản"],
        "Quy_Hoach_Xay_Dung": ["quy hoạch", "xây dựng"],
        "Tranh_Chap_Dat_Dai": ["tranh chấp đất"],
        # Thuế
        "Thue_GTGT": ["gtgt", "giá trị gia tăng"],
        "Thue_TNDN": ["tndn", "thu nhập doanh nghiệp"],
        "Thue_TNCN": ["tncn", "thu nhập cá nhân"],
        "Uu_Dai_Thue": ["ưu đãi"],
        # Đầu tư
        "Giay_Phep_Dau_Tu": ["giấy phép", "đầu tư"],
        "Hiep_Dinh_Thuong_Mai": ["hiệp định"],
        "Chuyen_Loi_Nhuan_Ve_Nuoc": ["chuyển lợi nhuận"],
        "M_A": ["sáp nhập", "m&a"],
        # SHTT
        "Nhan_Hieu": ["nhãn hiệu", "thương hiệu"],
        "Sang_Che": ["sáng chế"],
        "Ban_Quyen": ["bản quyền"],
        "Bien_Phap_Bao_Ve": ["bảo vệ"],
        # Tố tụng
        "Dan_Su": ["dân sự"],
        "Hinh_Su": ["hình sự"],
        "Hanh_Chinh": ["hành chính"],
        "Trong_Tai_Thuong_Mai": ["trọng tài"],
        # Hình sự
        "Bo_Luat_Hinh_Su": ["bộ luật hình sự"],
        "To_Tung_Hinh_Su": ["tố tụng hình sự"],
        "Cac_Toi_Danh_Thuong_Gap": ["tội danh", "tội phạm"],
    }
    
    for sf in subfolders:
        keywords = subfolder_keywords.get(sf, [])
        if any(kw in text for kw in keywords):
            return sf
    
    # Mặc định: subfolder đầu tiên
    return subfolders[0]
