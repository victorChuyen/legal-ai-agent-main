"""
OAuth2 Setup - Xác thực Google Drive bằng tài khoản cá nhân.
Chạy MỘT LẦN DUY NHẤT để lấy token. Sau đó pipeline tự dùng token đã lưu.

Hướng dẫn:
1. Vào Google Cloud Console > APIs & Services > Credentials
2. Tạo OAuth 2.0 Client ID (Desktop app)
3. Tải file JSON về, đổi tên thành 'oauth_client.json', bỏ vào thư mục credentials/
4. Chạy: python scripts/oauth_setup.py
5. Trình duyệt mở ra, đăng nhập Google, cấp quyền Drive
6. Token tự động lưu vào credentials/token.json
"""

import os
import json
import sys

CREDENTIALS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials')
CLIENT_SECRET_FILE = os.path.join(CREDENTIALS_DIR, 'oauth_client.json')
TOKEN_FILE = os.path.join(CREDENTIALS_DIR, 'token.json')
SCOPES = ['https://www.googleapis.com/auth/drive']


def setup_oauth():
    """Thực hiện OAuth2 flow để lấy access token + refresh token."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Cần cài thêm thư viện. Đang cài...")
        os.system(f'"{sys.executable}" -m pip install google-auth-oauthlib')
        from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ❌ CHƯA CÓ FILE oauth_client.json                         ║
║                                                              ║
║  Hướng dẫn tạo:                                              ║
║  1. Vào https://console.cloud.google.com/apis/credentials    ║
║     (Project: legal-ai-agent-492309)                         ║
║  2. Bấm [+ CREATE CREDENTIALS] > OAuth client ID             ║
║  3. Application type: Desktop app                             ║
║  4. Bấm CREATE, rồi DOWNLOAD JSON                            ║
║  5. Đổi tên file thành: oauth_client.json                    ║
║  6. Bỏ vào: {CREDENTIALS_DIR}                                ║
║  7. Chạy lại script này                                      ║
╚══════════════════════════════════════════════════════════════╝
""")
        return False

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    # Lưu token
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes),
    }
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(token_data, f, indent=2)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ✅ XÁC THỰC THÀNH CÔNG!                                    ║
║  Token đã lưu tại: {TOKEN_FILE}                              ║
║  Pipeline có thể chạy tự động từ giờ.                        ║
╚══════════════════════════════════════════════════════════════╝
""")
    return True


if __name__ == "__main__":
    setup_oauth()
