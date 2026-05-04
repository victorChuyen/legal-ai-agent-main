"""
Crawl Manifest - Thu thập metadata văn bản pháp luật từ thuvienphapluat.vn.
Kết quả lưu vào manifest.csv với đầy đủ trường metadata.
"""

import os
import csv
import re
import time
import hashlib
import requests
import urllib3
from bs4 import BeautifulSoup

# Tắt SSL warning (thuvienphapluat.vn có cert lỗi trên một số máy Windows)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scripts.config.categories import detect_category, detect_subfolder

MANIFEST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'manifest.csv')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}

MANIFEST_FIELDS = [
    "doc_id", "title", "doc_type", "doc_number", "issued_by",
    "issued_date", "detail_url", "file_url", "category",
    "subfolder", "status", "drive_file_id", "error_msg"
]

# Các trang chủ đề trên TVPL để crawl danh sách
CRAWL_SOURCES = [
    {
        "name": "Lao động - Tiền lương",
        "base_url": "https://thuvienphapluat.vn/page/tim-van-ban.aspx?keyword=&area=0&match=False&type=0&status=0&signer=0&sort=1&lan=1&scan=0&org=0&fields=&page=",
        "category_hint": "02_Lao_Dong",
    },
]

# Danh sách văn bản ưu tiên cao (crawl chắc chắn thành công)
PRIORITY_DOCS = [
    {
        "title": "Bộ luật Lao động 2019",
        "doc_type": "Bộ luật",
        "doc_number": "45/2019/QH14",
        "issued_by": "Quốc hội",
        "issued_date": "2019-11-20",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Lao-dong-Tien-luong/Bo-Luat-lao-dong-2019-333670.aspx",
    },
    {
        "title": "Nghị định 145/2020/NĐ-CP hướng dẫn Bộ luật Lao động",
        "doc_type": "Nghị định",
        "doc_number": "145/2020/NĐ-CP",
        "issued_by": "Chính phủ",
        "issued_date": "2020-12-14",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Lao-dong-Tien-luong/Nghi-dinh-145-2020-ND-CP-huong-dan-Bo-luat-Lao-dong-ve-dieu-kien-lao-dong-460547.aspx",
    },
    {
        "title": "Luật Bảo hiểm xã hội 2024",
        "doc_type": "Luật",
        "doc_number": "41/2024/QH15",
        "issued_by": "Quốc hội",
        "issued_date": "2024-06-29",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Bao-hiem/Luat-Bao-hiem-xa-hoi-2024-574592.aspx",
    },
    {
        "title": "Luật Doanh nghiệp 2020",
        "doc_type": "Luật",
        "doc_number": "59/2020/QH14",
        "issued_by": "Quốc hội",
        "issued_date": "2020-06-17",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Luat-Doanh-nghiep-2020-362817.aspx",
    },
    {
        "title": "Luật Đất đai 2024",
        "doc_type": "Luật",
        "doc_number": "31/2024/QH15",
        "issued_by": "Quốc hội",
        "issued_date": "2024-01-18",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Luat-Dat-dai-2024-574790.aspx",
    },
    {
        "title": "Bộ luật Hình sự 2015 sửa đổi 2017",
        "doc_type": "Bộ luật",
        "doc_number": "100/2015/QH13",
        "issued_by": "Quốc hội",
        "issued_date": "2015-11-27",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Trach-nhiem-hinh-su/Bo-luat-hinh-su-2015-296661.aspx",
    },
    {
        "title": "Bộ luật Dân sự 2015",
        "doc_type": "Bộ luật",
        "doc_number": "91/2015/QH13",
        "issued_by": "Quốc hội",
        "issued_date": "2015-11-24",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx",
    },
    {
        "title": "Luật Thuế giá trị gia tăng 2024",
        "doc_type": "Luật",
        "doc_number": "48/2024/QH15",
        "issued_by": "Quốc hội",
        "issued_date": "2024-11-26",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Thue-Phi-Le-Phi/Luat-Thue-gia-tri-gia-tang-2024-617498.aspx",
    },
    {
        "title": "Luật Sở hữu trí tuệ 2005 sửa đổi 2022",
        "doc_type": "Luật",
        "doc_number": "50/2005/QH11",
        "issued_by": "Quốc hội",
        "issued_date": "2005-11-29",
        "detail_url": "https://thuvienphapluat.vn/van-ban/So-huu-tri-tue/Luat-So-huu-tri-tue-2005-60444.aspx",
    },
    {
        "title": "Luật Đầu tư 2020",
        "doc_type": "Luật",
        "doc_number": "61/2020/QH14",
        "issued_by": "Quốc hội",
        "issued_date": "2020-06-17",
        "detail_url": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Luat-Dau-tu-2020-362730.aspx",
    },
]


def generate_doc_id(title, doc_number):
    """Tạo doc_id duy nhất từ tiêu đề và số hiệu."""
    raw = f"{title}_{doc_number}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]


def load_existing_manifest():
    """Đọc manifest hiện tại để tránh duplicate."""
    existing = set()
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row.get("detail_url", ""))
    return existing


def init_manifest():
    """Khởi tạo file manifest nếu chưa có."""
    if not os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
        print(f"📄 Đã tạo manifest mới: {MANIFEST_FILE}")


def append_to_manifest(docs):
    """Thêm documents vào manifest (Append mode)."""
    if not docs:
        return
    with open(MANIFEST_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction='ignore')
        for doc in docs:
            writer.writerow(doc)
    print(f"  💾 Đã thêm {len(docs)} văn bản vào manifest")


def crawl_tvpl_search_page(page_url):
    """Crawl 1 trang kết quả tìm kiếm từ thuvienphapluat.vn."""
    docs = []
    try:
        res = requests.get(page_url, headers=HEADERS, timeout=30, verify=False)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")

        # Selector cho kết quả tìm kiếm TVPL
        items = soup.select("div.search-result-item, div.nq-item, p.nqTitle")
        for item in items:
            link = item.find("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not href.startswith("http"):
                href = f"https://thuvienphapluat.vn{href}"

            if not title or "/van-ban/" not in href:
                continue

            # Xác định loại văn bản từ tiêu đề
            doc_type = "Văn bản"
            for dtype in ["Nghị định", "Thông tư", "Luật", "Bộ luật", "Quyết định", "Nghị quyết", "Pháp lệnh"]:
                if dtype.lower() in title.lower():
                    doc_type = dtype
                    break

            # Tìm số hiệu
            doc_number = ""
            num_match = re.search(r'(\d+/\d{4}/[A-ZĐa-zđ\-]+)', title)
            if num_match:
                doc_number = num_match.group(1)

            category = detect_category(title, doc_type)
            subfolder = detect_subfolder(title, category)

            docs.append({
                "doc_id": generate_doc_id(title, doc_number or href),
                "title": title,
                "doc_type": doc_type,
                "doc_number": doc_number,
                "issued_by": "",
                "issued_date": "",
                "detail_url": href,
                "file_url": "",
                "category": category,
                "subfolder": subfolder,
                "status": "pending",
                "drive_file_id": "",
                "error_msg": "",
            })

    except Exception as e:
        print(f"  ⚠️ Lỗi crawl {page_url}: {e}")

    return docs


def build_priority_manifest():
    """Tạo manifest từ danh sách văn bản ưu tiên (luôn chính xác)."""
    existing = load_existing_manifest()
    docs = []

    for doc_info in PRIORITY_DOCS:
        if doc_info["detail_url"] in existing:
            continue

        category = detect_category(doc_info["title"], doc_info["doc_type"])
        subfolder = detect_subfolder(doc_info["title"], category)

        docs.append({
            "doc_id": generate_doc_id(doc_info["title"], doc_info["doc_number"]),
            "title": doc_info["title"],
            "doc_type": doc_info["doc_type"],
            "doc_number": doc_info["doc_number"],
            "issued_by": doc_info["issued_by"],
            "issued_date": doc_info["issued_date"],
            "detail_url": doc_info["detail_url"],
            "file_url": "",
            "category": category,
            "subfolder": subfolder,
            "status": "pending",
            "drive_file_id": "",
            "error_msg": "",
        })

    return docs


def run_crawl(max_pages=2):
    """Chạy crawl: ưu tiên danh sách cứng trước, sau đó crawl thêm từ web."""
    init_manifest()

    # Bước 1: Danh sách ưu tiên
    print("📋 Đang nạp danh sách văn bản ưu tiên...")
    priority_docs = build_priority_manifest()
    append_to_manifest(priority_docs)
    print(f"  ✅ {len(priority_docs)} văn bản ưu tiên")

    # Bước 2: Crawl thêm từ TVPL (nếu website cho phép)
    existing = load_existing_manifest()
    for source in CRAWL_SOURCES:
        print(f"\n🔍 Đang crawl: {source['name']}")
        for page in range(1, max_pages + 1):
            url = f"{source['base_url']}{page}"
            print(f"  📄 Trang {page}...")
            docs = crawl_tvpl_search_page(url)

            # Lọc bỏ duplicate
            new_docs = [d for d in docs if d["detail_url"] not in existing]
            if new_docs:
                append_to_manifest(new_docs)
                for d in new_docs:
                    existing.add(d["detail_url"])

            time.sleep(2)  # Lịch sự với server

    # Thống kê
    total = len(load_existing_manifest())
    print(f"\n📊 Tổng cộng manifest: {total} văn bản")


if __name__ == "__main__":
    print("🏛️ Legal AI — Crawl Manifest Builder")
    print("=" * 50)
    run_crawl(max_pages=3)
    print("\n✅ Hoàn tất crawl manifest!")
