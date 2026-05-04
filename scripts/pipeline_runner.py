"""
Pipeline Runner - Orchestrator đẩy văn bản từ manifest lên Google Drive.
Đọc manifest.csv > stream lên Drive > cập nhật trạng thái > backup.
"""

import os
import csv
import time
import shutil
import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.config.categories import ROOT_FOLDER_ID, detect_category, detect_subfolder
from scripts.drive_stream_upload import (
    get_drive_service,
    stream_url_to_drive,
    stream_html_to_drive,
    resolve_target_folder,
)

MANIFEST_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'manifest.csv')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backups')

MANIFEST_FIELDS = [
    "doc_id", "title", "doc_type", "doc_number", "issued_by",
    "issued_date", "detail_url", "file_url", "category",
    "subfolder", "status", "drive_file_id", "error_msg"
]

MAX_RETRIES = 3


def load_manifest():
    """Đọc toàn bộ manifest.csv."""
    if not os.path.exists(MANIFEST_FILE):
        print(f"❌ Không tìm thấy {MANIFEST_FILE}")
        print("   Chạy: python scripts/crawl_manifest.py trước")
        return []

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_manifest(rows):
    """Lưu lại toàn bộ manifest (với backup)."""
    if not rows:
        return

    # Backup trước khi ghi đè
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(MANIFEST_FILE):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"manifest_{ts}.csv")
        shutil.copy2(MANIFEST_FILE, backup_path)

    # Ghi file chính
    with open(MANIFEST_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def get_backoff_time(attempt):
    """Exponential backoff: 2s, 4s, 8s."""
    return min(2 ** attempt, 30)


def run_pipeline(limit=None):
    """Chạy pipeline đẩy văn bản lên Drive."""
    rows = load_manifest()
    if not rows:
        return

    # Kết nối Drive
    try:
        drive_service = get_drive_service()
    except Exception as e:
        print(f"❌ Lỗi kết nối Drive: {e}")
        print("\n💡 Giải pháp:")
        print("   1. Chạy: python scripts/oauth_setup.py")
        print("   2. Đăng nhập Google trên trình duyệt")
        print("   3. Chạy lại pipeline")
        return

    # Đếm pending
    pending = [r for r in rows if r.get('status', 'pending') in ('pending', 'error')]
    if limit:
        pending = pending[:limit]

    total_pending = len(pending)
    if total_pending == 0:
        print("✅ Không có văn bản nào cần xử lý!")
        return

    print(f"\n📊 Pipeline: {total_pending} văn bản cần đẩy lên Drive")
    print(f"📁 Root folder: {ROOT_FOLDER_ID}")
    print("=" * 60)

    processed = 0
    success_count = 0
    error_count = 0
    start_time = time.time()

    for idx, row in enumerate(rows):
        if limit and processed >= limit:
            break

        status = row.get("status", "pending")
        if status == "done":
            continue

        processed += 1
        title = row.get("title", "Untitled")
        detail_url = row.get("detail_url", "")
        file_url = row.get("file_url", "")
        category = row.get("category", "")
        subfolder = row.get("subfolder", "")

        # Auto-detect nếu chưa có category
        if not category:
            category = detect_category(title, row.get("doc_type", ""))
            row["category"] = category
        if not subfolder:
            subfolder = detect_subfolder(title, category)
            row["subfolder"] = subfolder

        print(f"\n[{processed}/{total_pending}] 📜 {title[:60]}...")
        print(f"  📂 {category}/{subfolder}")

        # Tìm/tạo folder đích trên Drive
        try:
            target_folder_id = resolve_target_folder(
                drive_service, ROOT_FOLDER_ID, category, subfolder
            )
        except Exception as e:
            print(f"  ❌ Lỗi tạo folder: {e}")
            row["status"] = "error"
            row["error_msg"] = f"Folder error: {e}"
            error_count += 1
            continue

        # Upload với retry
        drive_file_id = None
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if file_url:
                    drive_file_id = stream_url_to_drive(
                        drive_service, file_url, target_folder_id,
                        f"{title}.pdf", "application/pdf",
                        category=category, subfolder=subfolder
                    )
                elif detail_url:
                    drive_file_id = stream_html_to_drive(
                        drive_service, detail_url, target_folder_id, title,
                        category=category, subfolder=subfolder
                    )
                else:
                    last_error = "Không có URL"
                    break

                if drive_file_id:
                    break
                else:
                    last_error = "Upload trả về None"
                    print(f"  ⚠️ Thử lại {attempt}/{MAX_RETRIES}...")
                    time.sleep(get_backoff_time(attempt))

            except Exception as e:
                last_error = str(e)
                print(f"  ⚠️ Lỗi lần {attempt}/{MAX_RETRIES}: {e}")
                time.sleep(get_backoff_time(attempt))

        if drive_file_id:
            row["status"] = "done"
            row["drive_file_id"] = drive_file_id
            row["error_msg"] = ""
            success_count += 1
            print(f"  ✅ Thành công! (ID: {drive_file_id})")
        else:
            row["status"] = "error"
            row["error_msg"] = last_error[:200]
            error_count += 1
            print(f"  ❌ Thất bại: {last_error[:80]}")

        # Auto-save mỗi 5 văn bản
        if processed % 5 == 0:
            save_manifest(rows)
            print(f"\n  💾 Đã lưu checkpoint ({processed} văn bản)")

        # Nghỉ giữa các request
        time.sleep(1)

    # Lưu cuối cùng
    save_manifest(rows)

    # Báo cáo
    elapsed = time.time() - start_time
    print(f"""
{'='*60}
📊 KẾT QUẢ PIPELINE
{'='*60}
  Tổng xử lý:  {processed}
  ✅ Thành công: {success_count}
  ❌ Thất bại:   {error_count}
  ⏱️ Thời gian:  {elapsed:.1f}s ({elapsed/max(processed,1):.1f}s/văn bản)
  💾 Manifest:   {MANIFEST_FILE}
{'='*60}
""")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline đẩy văn bản pháp luật lên Google Drive")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số văn bản xử lý")
    args = parser.parse_args()

    print("🚀 Legal AI — Pipeline Runner")
    print("=" * 50)
    run_pipeline(limit=args.limit)
