/**
 * ============================================================
 * APPS SCRIPT - PROXY UPLOAD CHO LEGAL AI PIPELINE
 * ============================================================
 * 
 * HƯỚNG DẪN CÀI ĐẶT:
 * 1. Mở Google Sheet: https://docs.google.com/spreadsheets/d/1zsshlzSARPljp1o0Z1G1-oReywa4k2HE-y2mLkleqVA/edit
 * 2. Tiện ích mở rộng > Apps Script
 * 3. XÓA toàn bộ code cũ trong Code.gs
 * 4. DÁN toàn bộ đoạn code này vào
 * 5. Bấm Deploy > New Deployment > Web App
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 6. Bấm Deploy, copy URL mới
 * 7. Dán URL vào file scripts/config/categories.py dòng APPS_SCRIPT_URL
 */

const ROOT_FOLDER_ID = '1nPtObLJuMjolevyJVsnxZKqhwZpyx3fI';

const LEGAL_STRUCTURE = {
  "01_Doanh_Nghiep": ["Thanh_Lap_Doanh_Nghiep","Quan_Tri_Noi_Bo","Hop_Dong_Thuong_Mai","Giai_The_Pha_San"],
  "02_Lao_Dong": ["Hop_Dong_Lao_Dong","Bao_Hiem_Xa_Hoi","Ky_Luat_Lao_Dong","Tranh_Chap_Lao_Dong"],
  "03_Dat_Dai_Bat_Dong_San": ["Chuyen_Nhuong_QSD_Dat","Hop_Dong_Mua_Ban_BDS","Quy_Hoach_Xay_Dung","Tranh_Chap_Dat_Dai"],
  "04_Thue": ["Thue_GTGT","Thue_TNDN","Thue_TNCN","Uu_Dai_Thue"],
  "05_Dau_Tu_Nuoc_Ngoai": ["Giay_Phep_Dau_Tu","Hiep_Dinh_Thuong_Mai","Chuyen_Loi_Nhuan_Ve_Nuoc","M_A"],
  "06_So_Huu_Tri_Tue": ["Nhan_Hieu","Sang_Che","Ban_Quyen","Bien_Phap_Bao_Ve"],
  "07_To_Tung": ["Dan_Su","Hinh_Su","Hanh_Chinh","Trong_Tai_Thuong_Mai"],
  "08_Hinh_Su": ["Bo_Luat_Hinh_Su","To_Tung_Hinh_Su","Cac_Toi_Danh_Thuong_Gap"]
};

// ============ MAIN API HANDLERS ============

function doGet(e) {
  // GET: Trả về danh sách folder structure + IDs
  try {
    const action = (e && e.parameter && e.parameter.action) || 'status';
    
    if (action === 'folders') {
      return jsonResponse(getFolderStructure());
    }
    
    return jsonResponse({
      status: 'ok',
      message: 'Legal AI Drive Proxy is running',
      root_folder: ROOT_FOLDER_ID,
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    return jsonResponse({ status: 'error', message: err.toString() });
  }
}

function doPost(e) {
  // POST: Upload file lên Drive
  try {
    const payload = JSON.parse(e.postData.contents);
    const action = payload.action || 'upload_text';
    
    switch (action) {
      case 'upload_text':
        return jsonResponse(uploadTextFile(payload));
      case 'upload_from_url':
        return jsonResponse(uploadFromUrl(payload));
      case 'create_folder':
        return jsonResponse(createSubFolder(payload));
      case 'list_files':
        return jsonResponse(listFolderFiles(payload));
      default:
        return jsonResponse({ status: 'error', message: 'Unknown action: ' + action });
    }
  } catch (err) {
    return jsonResponse({ status: 'error', message: err.toString() });
  }
}

// ============ UPLOAD FUNCTIONS ============

function uploadTextFile(payload) {
  /**
   * Upload text content as a .txt file to Drive
   * payload: { filename, content, category, subfolder }
   */
  const filename = payload.filename || 'untitled.txt';
  const content = payload.content || '';
  const category = payload.category || '01_Doanh_Nghiep';
  const subfolder = payload.subfolder || '';
  
  // Resolve target folder
  const targetFolderId = resolveFolder(category, subfolder);
  const folder = DriveApp.getFolderById(targetFolderId);
  
  // Create file
  const file = folder.createFile(filename, content, MimeType.PLAIN_TEXT);
  
  // Log to sheet
  logUpload(filename, category, subfolder, file.getId(), 'text', content.length);
  
  return {
    status: 'ok',
    file_id: file.getId(),
    file_url: file.getUrl(),
    filename: filename,
    folder_id: targetFolderId,
    size_bytes: content.length
  };
}

function uploadFromUrl(payload) {
  /**
   * Fetch file from URL and save to Drive (binary/PDF/HTML)
   * payload: { url, filename, category, subfolder, mimetype }
   */
  const url = payload.url;
  const filename = payload.filename || 'downloaded_file';
  const category = payload.category || '01_Doanh_Nghiep';
  const subfolder = payload.subfolder || '';
  const mimetype = payload.mimetype || 'application/pdf';
  
  if (!url) return { status: 'error', message: 'URL is required' };

  try {
    // Fetch file from URL
    const response = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      followRedirects: true,
      validateHttpsCertificates: false
    });
    
    const code = response.getResponseCode();
    if (code !== 200) {
      return { status: 'error', message: 'HTTP ' + code + ' fetching URL: ' + url };
    }
    
    const blob = response.getBlob().setName(filename);
    if (mimetype) blob.setContentType(mimetype);
    
    // Save to Drive
    const targetFolderId = resolveFolder(category, subfolder);
    const folder = DriveApp.getFolderById(targetFolderId);
    
    // Clean up old version if it exists to avoid duplicates
    const existing = folder.getFilesByName(filename);
    if (existing.hasNext()) {
      existing.next().setTrashed(true);
    }
    
    const file = folder.createFile(blob);
    
    logUpload(filename, category, subfolder, file.getId(), 'url_proxy', blob.getBytes().length);
    
    return {
      status: 'ok',
      file_id: file.getId(),
      file_url: file.getUrl(),
      filename: filename,
      folder_id: targetFolderId,
      size_bytes: blob.getBytes().length
    };
  } catch (err) {
    return { status: 'error', message: 'Proxy Error: ' + err.toString() };
  }
}

function createSubFolder(payload) {
  const parentId = payload.parent_id || ROOT_FOLDER_ID;
  const name = payload.name;
  const parent = DriveApp.getFolderById(parentId);
  const folder = getOrCreateFolder(parent, name);
  return { status: 'ok', folder_id: folder.getId(), name: name };
}

function listFolderFiles(payload) {
  const folderId = payload.folder_id || ROOT_FOLDER_ID;
  const folder = DriveApp.getFolderById(folderId);
  const files = folder.getFiles();
  const result = [];
  while (files.hasNext()) {
    const f = files.next();
    result.push({ id: f.getId(), name: f.getName(), size: f.getSize() });
  }
  return { status: 'ok', files: result, count: result.length };
}

// ============ FOLDER HELPERS ============

function resolveFolder(category, subfolder) {
  const root = DriveApp.getFolderById(ROOT_FOLDER_ID);
  let catFolder = getOrCreateFolder(root, category);
  
  if (subfolder) {
    let subFolder = getOrCreateFolder(catFolder, subfolder);
    // Create year folder
    const year = new Date().getFullYear().toString();
    let yearFolder = getOrCreateFolder(subFolder, year);
    return yearFolder.getId();
  }
  
  return catFolder.getId();
}

function getOrCreateFolder(parentFolder, folderName) {
  const existing = parentFolder.getFoldersByName(folderName);
  if (existing.hasNext()) return existing.next();
  return parentFolder.createFolder(folderName);
}

function getFolderStructure() {
  const root = DriveApp.getFolderById(ROOT_FOLDER_ID);
  const structure = {};
  
  for (const [cat, subs] of Object.entries(LEGAL_STRUCTURE)) {
    const catFolders = root.getFoldersByName(cat);
    if (catFolders.hasNext()) {
      const catFolder = catFolders.next();
      structure[cat] = { id: catFolder.getId(), subfolders: {} };
      for (const sub of subs) {
        const subFolders = catFolder.getFoldersByName(sub);
        if (subFolders.hasNext()) {
          structure[cat].subfolders[sub] = subFolders.next().getId();
        }
      }
    }
  }
  
  return { status: 'ok', structure: structure };
}

// ============ LOGGING ============

function logUpload(filename, category, subfolder, fileId, method, sizeBytes) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName('Upload_Log');
    if (!sheet) {
      sheet = ss.insertSheet('Upload_Log');
      sheet.appendRow(['Timestamp', 'Filename', 'Category', 'Subfolder', 'FileID', 'Method', 'Size(bytes)']);
    }
    sheet.appendRow([
      new Date().toLocaleString('vi-VN'),
      filename, category, subfolder, fileId, method, sizeBytes
    ]);
  } catch (e) {
    Logger.log('Log error: ' + e);
  }
}

// ============ UTILITIES ============

function jsonResponse(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

// ============ INIT ============
function createLegalFolderStructure() {
  const root = DriveApp.getFolderById(ROOT_FOLDER_ID);
  for (const [chuyenMuc, ngachList] of Object.entries(LEGAL_STRUCTURE)) {
    let mainFolder = getOrCreateFolder(root, chuyenMuc);
    Logger.log('✅ ' + chuyenMuc);
    for (const ngach of ngachList) {
      getOrCreateFolder(mainFolder, ngach);
      const year = new Date().getFullYear().toString();
      const ngachFolder = getOrCreateFolder(mainFolder, ngach);
      getOrCreateFolder(ngachFolder, year);
    }
  }
  SpreadsheetApp.getActiveSpreadsheet().getActiveSheet()
    .getRange('A1').setValue('✅ Đã tạo xong cấu trúc lúc ' + new Date().toLocaleString('vi-VN'));
}
