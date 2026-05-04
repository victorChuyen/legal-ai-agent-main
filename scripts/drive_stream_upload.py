"""
Drive Stream Upload - Upload văn bản pháp luật lên Google Drive.
Sử dụng Google Apps Script làm proxy để bypass quota Service Account.
Fallback: OAuth2 nếu có token.
"""

import io
import os
import json
import base64
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============ CONFIG ============
CREDENTIALS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials')
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, 'token.json')

# URL Apps Script Web App - CẬP NHẬT SAU KHI DEPLOY
APPS_SCRIPT_URL = os.environ.get(
    'APPS_SCRIPT_URL',
    'https://script.google.com/macros/s/AKfycbzGvTITk18phA2Xdc1cc1Vf8fGmWhlQi83M-U9abJURRuu-umiL09CSznCw8CO8tmK5/exec'
)


def get_drive_service():
    """
    Trả về 'apps_script' nếu có URL, hoặc Google Drive API service nếu có OAuth token.
    """
    # Ưu tiên Apps Script proxy
    if APPS_SCRIPT_URL and 'script.google.com' in APPS_SCRIPT_URL:
        # Test kết nối
        try:
            resp = requests.get(APPS_SCRIPT_URL, timeout=15)
            data = resp.json()
            if data.get('status') == 'ok':
                print(f"🔑 Đã kết nối Apps Script Proxy")
                print(f"   Root: {data.get('root_folder', 'N/A')}")
                return 'apps_script'
        except Exception:
            pass

    # Fallback: OAuth2 token
    if os.path.exists(TOKEN_FILE):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri'),
            client_id=token_data.get('client_id'),
            client_secret=token_data.get('client_secret'),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_data['token'] = creds.token
            with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)

        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        print("🔑 Đã kết nối Drive bằng OAuth2")
        return service

    raise ConnectionError(
        "Không thể kết nối Drive!\n"
        "Cần deploy Apps Script hoặc chạy oauth_setup.py"
    )


def stream_url_to_drive(service, file_url, folder_id, filename, mimetype="application/pdf",
                         category="", subfolder=""):
    """Stream file từ URL lên Drive."""
    if service == 'apps_script':
        return _apps_script_upload_url(file_url, filename, category, subfolder, mimetype)
    else:
        return _api_upload_url(service, file_url, folder_id, filename, mimetype)


def stream_html_to_drive(service, detail_url, folder_id, filename,
                          category="", subfolder=""):
    """Crawl HTML, bóc text, đẩy lên Drive dạng .txt."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        }
        response = requests.get(detail_url, headers=headers, timeout=60, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        content_div = (
            soup.find("div", class_="content1")
            or soup.find("div", id="toanvancontent")
            or soup.find("div", class_="toanvancontent")
            or soup.find("div", class_="MainContent")
        )

        if content_div:
            for br in content_div.find_all("br"):
                br.replace_with("\n")
            text_content = content_div.get_text(separator="\n", strip=True)
        else:
            text_content = soup.body.get_text(separator="\n", strip=True) if soup.body else ""

        title_tag = soup.title.string if soup.title else filename
        full_text = f"TIÊU ĐỀ: {title_tag}\nNGUỒN: {detail_url}\n{'='*60}\n\n{text_content}"

        # Upload
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '_' for c in filename)
        safe_name = safe_name[:100]

        if service == 'apps_script':
            return _apps_script_upload_text(f"{safe_name}.txt", full_text, category, subfolder)
        else:
            return _api_upload_text(service, folder_id, f"{safe_name}.txt", full_text)

    except Exception as e:
        print(f"  ❌ Lỗi HTML upload: {e}")
        return None


def resolve_target_folder(service, root_id, category, subfolder=None):
    """Resolve folder ID - chỉ cần cho API mode, Apps Script tự xử lý."""
    if service == 'apps_script':
        return None  # Apps Script tự resolve
    else:
        from googleapiclient.http import MediaIoBaseUpload
        # API mode: tìm/tạo folder
        cat_id = _find_or_create_folder(service, category, root_id)
        if subfolder:
            sub_id = _find_or_create_folder(service, subfolder, cat_id)
            import datetime
            year = str(datetime.datetime.now().year)
            year_id = _find_or_create_folder(service, year, sub_id)
            return year_id
        return cat_id


# ============ APPS SCRIPT PROXY ============

def _apps_script_upload_text(filename, content, category, subfolder):
    """Upload text qua Apps Script proxy."""
    payload = {
        'action': 'upload_text',
        'filename': filename,
        'content': content,
        'category': category,
        'subfolder': subfolder,
    }

    resp = requests.post(
        APPS_SCRIPT_URL,
        json=payload,
        timeout=120,
        headers={'Content-Type': 'application/json'}
    )

    data = resp.json()
    if data.get('status') == 'ok':
        return data.get('file_id')
    else:
        print(f"  ❌ Apps Script error: {data.get('message')}")
        return None


def _apps_script_upload_url(file_url, filename, category, subfolder, mimetype):
    """Upload file từ URL qua Apps Script proxy (Apps Script tự fetch URL)."""
    payload = {
        'action': 'upload_from_url',
        'url': file_url,
        'filename': filename,
        'category': category,
        'subfolder': subfolder,
        'mimetype': mimetype,
    }

    resp = requests.post(
        APPS_SCRIPT_URL,
        json=payload,
        timeout=120,
        headers={'Content-Type': 'application/json'}
    )

    data = resp.json()
    if data.get('status') == 'ok':
        return data.get('file_id')
    else:
        print(f"  ❌ Apps Script error: {data.get('message')}")
        return None


# ============ DIRECT API (OAuth2) ============

def _api_upload_text(service, folder_id, filename, content):
    """Upload text trực tiếp qua Drive API."""
    from googleapiclient.http import MediaIoBaseUpload
    file_data = io.BytesIO(content.encode("utf-8"))
    metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaIoBaseUpload(file_data, mimetype="text/plain; charset=utf-8", resumable=True)
    result = service.files().create(body=metadata, media_body=media, fields='id',
                                     supportsAllDrives=True).execute()
    return result.get('id')


def _api_upload_url(service, file_url, folder_id, filename, mimetype):
    """Upload file từ URL trực tiếp qua Drive API."""
    from googleapiclient.http import MediaIoBaseUpload
    resp = requests.get(file_url, stream=True, timeout=60, verify=False,
                        headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    content = resp.raw.read()
    file_data = io.BytesIO(content)
    metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaIoBaseUpload(file_data, mimetype=mimetype, resumable=True)
    result = service.files().create(body=metadata, media_body=media, fields='id',
                                     supportsAllDrives=True).execute()
    return result.get('id')


def _find_or_create_folder(service, name, parent_id):
    """Tìm hoặc tạo folder qua API."""
    q = f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    r = service.files().list(q=q, fields="files(id)", supportsAllDrives=True).execute()
    files = r.get('files', [])
    if files:
        return files[0]['id']
    meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
    f = service.files().create(body=meta, fields='id', supportsAllDrives=True).execute()
    return f['id']


if __name__ == "__main__":
    print("🔧 Testing Drive connection...")
    try:
        svc = get_drive_service()
        if svc == 'apps_script':
            print("✅ Apps Script proxy ready!")
        else:
            print("✅ Drive API ready!")
    except Exception as e:
        print(f"❌ {e}")
