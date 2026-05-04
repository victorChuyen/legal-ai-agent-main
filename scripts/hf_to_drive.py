"""
HuggingFace Dataset Loader → Google Drive Streamer
Tải 153K+ văn bản pháp luật từ HuggingFace và stream lên Google Drive.

Nguồn dữ liệu:
1. th1nhng0/vietnamese-legal-documents: 153K metadata + 149K full-text + relationships
2. thangvip/vietnamese-legal-qa: 9,715 documents + 29,145 QA pairs
3. Quockhanh05/Vietnam_legal_embeddings: Embedding model cho search
"""

import os
import sys
import json
import time
import csv
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.config.categories import ROOT_FOLDER_ID, detect_category, detect_subfolder
from scripts.drive_stream_upload import get_drive_service, APPS_SCRIPT_URL

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MANIFEST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'manifest.csv')
MANIFEST_FIELDS = [
    "doc_id", "id", "title", "so_ky_hieu", "ngay_ban_hanh", "loai_van_ban",
    "ngay_co_hieu_luc", "ngay_het_hieu_luc", "nguon_thu_thap", "ngay_dang_cong_bao",
    "nganh", "linh_vuc", "co_quan_ban_hanh", "chuc_danh", "nguoi_ky", "pham_vi",
    "thong_tin_ap_dung", "tinh_trang_hieu_luc", "category", "subfolder", "status",
    "drive_file_id", "html_file_id", "pdf_file_id", "error_msg", "detail_url"
]


def upload_text_via_apps_script(filename, content, category, subfolder):
    """Upload text content qua Apps Script proxy."""
    payload = {
        'action': 'upload_text',
        'filename': filename,
        'content': content,
        'category': category,
        'subfolder': subfolder,
    }
    try:
        resp = requests.post(
            APPS_SCRIPT_URL, json=payload, timeout=120,
            headers={'Content-Type': 'application/json'}
        )
        data = resp.json()
        if data.get('status') == 'ok':
            return data.get('file_id')
    except Exception as e:
        print(f"    ❌ Upload error: {e}")
        return None


def upload_url_via_apps_script(filename, url, category, subfolder, mimetype='application/pdf'):
    """Proxy upload từ URL qua Apps Script (dành cho PDF/HTML)."""
    payload = {
        'action': 'upload_from_url',
        'url': url,
        'filename': filename,
        'category': category,
        'subfolder': subfolder,
        'mimetype': mimetype
    }
    try:
        resp = requests.post(
            APPS_SCRIPT_URL, json=payload, timeout=180,
            headers={'Content-Type': 'application/json'}
        )
        data = resp.json()
        if data.get('status') == 'ok':
            return data.get('file_id')
        else:
            # print(f"    ❌ Proxy URL Error: {data.get('message')}")
            return None
    except Exception:
        return None


def load_existing_doc_ids():
    """Đọc danh sách doc_id đã có trong manifest."""
    existing = set()
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row.get("doc_id", ""))
    return existing


def append_manifest_row(row):
    """Thêm 1 row vào manifest."""
    file_exists = os.path.exists(MANIFEST_FILE)
    with open(MANIFEST_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction='ignore')
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def clean_html_to_text(html_content):
    """Chuyển HTML sang text sạch."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "lxml")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        return soup.get_text(separator="\n", strip=True)
    except Exception:
        # Fallback: regex strip tags
        text = re.sub(r'<[^>]+>', '\n', html_content)
        return re.sub(r'\n{3,}', '\n\n', text).strip()


def stream_hf_legal_documents(limit=None, batch_size=50):
    """
    Tải dataset th1nhng0/vietnamese-legal-documents từ HuggingFace
    và stream lên Google Drive qua Apps Script.
    
    Dataset chứa:
    - metadata: 153K documents (id, title, so_ky_hieu, loai_van_ban, co_quan_ban_hanh, ...)
    - content: 149K full-text HTML
    - relationships: cross-references
    """
    print("=" * 60)
    print("📚 NGUỒN 1: th1nhng0/vietnamese-legal-documents")
    print("   153,000+ metadata + 149,000+ full-text")
    print("=" * 60)

    try:
        from datasets import load_dataset
    except ImportError:
        print("📦 Đang cài thư viện datasets...")
        os.system(f'"{sys.executable}" -m pip install datasets')
        from datasets import load_dataset

    # Load metadata only (14MB, fits in RAM)
    print("\n📥 Đang tải metadata từ HuggingFace...")
    meta = load_dataset("th1nhng0/vietnamese-legal-documents", "metadata", split="data")
    print(f"   ✅ {len(meta)} văn bản metadata")

    # SKIP content parquet (2GB, tràn RAM)
    # Thay vào đó: fetch nội dung trực tiếp từ vbpl.vn cho từng doc
    print("   📋 Sẽ fetch nội dung từng văn bản từ vbpl.vn (tiết kiệm RAM)")

    # Check existing
    existing_ids = load_existing_doc_ids()
    print(f"   📋 Đã có {len(existing_ids)} văn bản trong manifest")

    # Process
    processed = 0
    uploaded = 0
    errors = 0
    start_time = time.time()

    total = min(len(meta), limit) if limit else len(meta)
    print(f"\n🚀 Bắt đầu xử lý {total} văn bản...")
    print("-" * 60)

    for i, doc in enumerate(meta):
        if limit and processed >= limit:
            break

        doc_id_hf = str(doc.get('id', ''))
        if f"hf_{doc_id_hf}" in existing_ids:
            continue

        # Trích xuất đầy đủ metadata
        m = {
            "id": doc_id_hf,
            "title": doc.get('title', '') or 'Untitled',
            "so_ky_hieu": doc.get('so_ky_hieu', ''),
            "ngay_ban_hanh": doc.get('ngay_ban_hanh', ''),
            "loai_van_ban": doc.get('loai_van_ban', ''),
            "ngay_co_hieu_luc": doc.get('ngay_co_hieu_luc', ''),
            "ngay_het_hieu_luc": doc.get('ngay_het_hieu_luc', ''),
            "nguon_thu_thap": doc.get('nguon_thu_thap', ''),
            "ngay_dang_cong_bao": doc.get('ngay_dang_cong_bao', ''),
            "nganh": doc.get('nganh', ''),
            "linh_vuc": doc.get('linh_vuc', ''),
            "co_quan_ban_hanh": doc.get('co_quan_ban_hanh', ''),
            "chuc_danh": doc.get('chuc_danh', ''),
            "nguoi_ky": doc.get('nguoi_ky', ''),
            "pham_vi": doc.get('pham_vi', ''),
            "thong_tin_ap_dung": doc.get('thong_tin_ap_dung', ''),
            "tinh_trang_hieu_luc": doc.get('tinh_trang_hieu_luc', ''),
        }

        # Phân loại
        category = detect_category(f"{m['title']} {m['linh_vuc']}", m['loai_van_ban'])
        subfolder = detect_subfolder(f"{m['title']} {m['linh_vuc']}", category)

        processed += 1

        # 1. Fetch nội dung & Detect PDF
        vbpl_url = f"https://vbpl.vn/bo-tu-phap/Pages/vbpq-toanvan.aspx?ItemID={doc_id_hf}"
        print_url = f"https://vbpl.vn/bo-tu-phap/Pages/vbpq-print.aspx?ItemID={doc_id_hf}"
        pdf_page_url = f"https://vbpl.vn/bo-tu-phap/Pages/vbpq-vanbangoc.aspx?ItemID={doc_id_hf}"
        
        text_content = ""
        html_raw = ""
        pdf_url = None
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            # Lấy nội dung text (Toàn văn)
            resp = requests.get(vbpl_url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                text_content = clean_html_to_text(resp.text)
                
            # Lấy HTML sạch (Print View)
            resp_print = requests.get(print_url, headers=headers, timeout=15, verify=False)
            if resp_print.status_code == 200:
                html_raw = resp_print.text

            # Tìm PDF Link từ trang Văn bản gốc
            resp_pdf = requests.get(pdf_page_url, headers=headers, timeout=15, verify=False)
            if resp_pdf.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp_pdf.text, "lxml")
                # Tìm thẻ a có chứa .pdf
                pdf_link_tags = soup.find_all("a", href=re.compile(r'\.pdf', re.I))
                if pdf_link_tags:
                    href = pdf_link_tags[0].get('href')
                    if href.startswith('http'):
                        pdf_url = href
                    else:
                        pdf_url = f"https://vbpl.vn{href}"
        except Exception:
            pass

        # Fallback: tạo file metadata-only nếu không fetch được
        if len(text_content) < 100:
            text_content = f"[Nội dung chưa được tải - xem tại: {vbpl_url}]"

        # Header cho file (Đầy đủ các trường)
        header_lines = [f"{k.upper().replace('_', ' ')}: {v}" for k, v in m.items()]
        header_lines.append(f"NGUỒN: {vbpl_url}")
        header_text = "\n".join(header_lines)

        full_text = f"{header_text}\n{'=' * 60}\n\n{text_content}"

        # --- UPLOAD 3 PHIÊN BẢN ---
        safe_name = re.sub(r'[^\w\s\-.]', '_', f"{m['so_ky_hieu']}_{m['title']}"[:100])
        
        # 1. Upload TXT
        txt_id = upload_text_via_apps_script(f"{safe_name}.txt", full_text, category, subfolder)
        
        # 2. Upload HTML (nếu có)
        html_id = ""
        if html_raw:
            html_id = upload_text_via_apps_script(f"{safe_name}.html", html_raw, category, subfolder)
            
        # 3. Upload PDF (nếu tìm thấy link)
        pdf_id = ""
        if pdf_url:
            pdf_id = upload_url_via_apps_script(f"{safe_name}.pdf", pdf_url, category, subfolder)

        if txt_id:
            uploaded += 1
            status = "done"
            if uploaded % 5 == 0:
                elapsed = time.time() - start_time
                rate = uploaded / elapsed * 60
                print(f"  [{uploaded}] ✅ {m['title'][:40]}... ({rate:.1f} văn bản/phút)")
        else:
            status = "error"

        # Ghi manifest
        manifest_row = {
            "doc_id": f"hf_{doc_id_hf}",
            "category": category,
            "subfolder": subfolder,
            "status": status,
            "drive_file_id": txt_id or "",
            "html_file_id": html_id or "",
            "pdf_file_id": pdf_id or "",
            "error_msg": "" if txt_id else "TXT Upload failed",
            "detail_url": vbpl_url
        }
        manifest_row.update(m)
        append_manifest_row(manifest_row)

        # Rate limiting
        time.sleep(0.5)

    elapsed = time.time() - start_time
    print(f"""
{'=' * 60}
📊 KẾT QUẢ - vietnamese-legal-documents
{'=' * 60}
  Tổng xử lý:  {processed}
  ✅ Upload OK:  {uploaded}
  ❌ Lỗi:        {errors}
  ⏱️ Thời gian:  {elapsed:.0f}s
{'=' * 60}
""")
    return uploaded


def stream_hf_legal_qa(limit=None):
    """
    Tải dataset thangvip/vietnamese-legal-qa
    9,715 documents + 29,145 QA pairs → upload lên Drive.
    """
    print("=" * 60)
    print("📚 NGUỒN 2: thangvip/vietnamese-legal-qa")
    print("   9,715 documents + 29,145 QA pairs")
    print("=" * 60)

    try:
        from datasets import load_dataset
    except ImportError:
        os.system(f'"{sys.executable}" -m pip install datasets')
        from datasets import load_dataset

    print("\n📥 Đang tải QA dataset...")
    ds = load_dataset("thangvip/vietnamese-legal-qa", split="train")
    print(f"   ✅ {len(ds)} documents")

    existing_ids = load_existing_doc_ids()
    uploaded = 0
    start_time = time.time()
    total = min(len(ds), limit) if limit else len(ds)

    for i, doc in enumerate(ds):
        if limit and i >= limit:
            break

        doc_name = doc.get('doc_name', '')
        doc_id = f"qa_{i}"

        if doc_id in existing_ids:
            continue

        doc_type = doc.get('doc_type_name', '')
        article_content = doc.get('article_content', '')
        qa_pairs = doc.get('generated_qa_pairs', [])

        if not article_content:
            continue

        category = detect_category(f"{doc_name}", doc_type)
        subfolder = detect_subfolder(doc_name, category)

        # Build rich content
        qa_text = ""
        if qa_pairs:
            qa_text = "\n\n--- CÂU HỎI & TRẢ LỜI ---\n"
            for j, qa in enumerate(qa_pairs):
                q = qa.get('question', '') if isinstance(qa, dict) else ''
                a = qa.get('answer', '') if isinstance(qa, dict) else ''
                qtype = qa.get('question_type', '') if isinstance(qa, dict) else ''
                diff = qa.get('difficulty', '') if isinstance(qa, dict) else ''
                qa_text += f"\nQ{j+1} [{qtype}/{diff}]: {q}\nA{j+1}: {a}\n"

        full_text = (
            f"VĂN BẢN: {doc_name}\n"
            f"LOẠI: {doc_type}\n"
            f"{'=' * 60}\n\n"
            f"{article_content}\n"
            f"{qa_text}"
        )

        safe_name = re.sub(r'[^\w\s\-.]', '_', doc_name[:80])
        file_id = upload_text_via_apps_script(f"QA_{safe_name}.txt", full_text, category, subfolder)

        if file_id:
            uploaded += 1
            if uploaded % 10 == 0:
                print(f"  [{uploaded}] ✅ {doc_name[:50]}...")

        append_manifest_row({
            "doc_id": doc_id,
            "id": f"qa_{i}",
            "title": f"[QA] {doc_name}",
            "so_ky_hieu": "",
            "ngay_ban_hanh": "",
            "loai_van_ban": doc_type,
            "ngay_co_hieu_luc": "",
            "ngay_het_hieu_luc": "",
            "nguon_thu_thap": "",
            "ngay_dang_cong_bao": "",
            "nganh": "",
            "linh_vuc": "",
            "co_quan_ban_hanh": "",
            "chuc_danh": "",
            "nguoi_ky": "",
            "pham_vi": "",
            "thong_tin_ap_dung": "",
            "tinh_trang_hieu_luc": "",
            "category": category,
            "subfolder": subfolder,
            "status": "done" if file_id else "error",
            "drive_file_id": file_id or "",
            "error_msg": "" if file_id else "Upload failed",
            "detail_url": ""
        })

        time.sleep(0.5)

    elapsed = time.time() - start_time
    print(f"\n✅ QA Dataset: {uploaded} uploaded in {elapsed:.0f}s")
    return uploaded


def run_all(doc_limit=None, qa_limit=None):
    """Chạy tất cả nguồn dữ liệu."""
    print("🏛️ LEGAL AI — HUGGINGFACE DATA PIPELINE")
    print("=" * 60)

    # Test kết nối
    try:
        svc = get_drive_service()
        if svc == 'apps_script':
            print("✅ Apps Script proxy kết nối OK")
        else:
            print("✅ Drive API kết nối OK")
    except Exception as e:
        print(f"❌ Không kết nối được: {e}")
        return

    total = 0

    # Nguồn 1: Legal Documents (153K)
    total += stream_hf_legal_documents(limit=doc_limit)

    # Nguồn 2: Legal QA (9.7K)
    total += stream_hf_legal_qa(limit=qa_limit)

    print(f"\n🎉 HOÀN TẤT: Tổng {total} files đã upload lên Google Drive!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Load HuggingFace legal datasets → Google Drive")
    parser.add_argument("--doc-limit", type=int, default=None, help="Giới hạn số văn bản từ legal-documents")
    parser.add_argument("--qa-limit", type=int, default=None, help="Giới hạn số văn bản từ legal-qa")
    args = parser.parse_args()

    run_all(doc_limit=args.doc_limit, qa_limit=args.qa_limit)
