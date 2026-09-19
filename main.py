from fastapi import FastAPI, Query, Header, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import os
import io
import urllib.request
import json
import psycopg2

app = FastAPI()

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "labadmin2026")
GOOGLE_SHEET_WEBHOOK = os.environ.get("GOOGLE_SHEET_WEBHOOK", "")

def get_db_connection():
    if DATABASE_URL:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, sslmode='require')
    else:
        import sqlite3
        return sqlite3.connect("lab_chemicals.db")

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chemicals (
                barcode VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                cas_no VARCHAR(255),
                smiles VARCHAR(255),
                formula VARCHAR(255),
                mw VARCHAR(255),
                safety_class VARCHAR(255),
                location VARCHAR(255),
                spec VARCHAR(255),
                note VARCHAR(255)
            );
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chemicals (
                barcode TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                cas_no TEXT,
                smiles TEXT,
                formula TEXT,
                mw TEXT,
                safety_class TEXT,
                location TEXT,
                spec TEXT,
                note TEXT
            )
        """)
    conn.commit()
    cursor.close()
    conn.close()

init_db()

class Chemical(BaseModel):
    barcode: str
    name: str
    cas_no: Optional[str] = ""
    smiles: Optional[str] = ""
    formula: Optional[str] = ""
    mw: Optional[str] = ""
    safety_class: Optional[str] = ""
    location: Optional[str] = ""
    spec: Optional[str] = ""
    note: Optional[str] = ""

class UpdateLocationPayload(BaseModel):
    barcode: str
    location: str

def sync_to_google_sheet(payload_dict: dict):
    if not GOOGLE_SHEET_WEBHOOK:
        return
    try:
        req = urllib.request.Request(
            GOOGLE_SHEET_WEBHOOK,
            data=json.dumps(payload_dict).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Sync to Google Sheet failed: {e}")

@app.get("/")
def read_root():
    return FileResponse("index.html")

def verify_admin(x_admin_key: Optional[str] = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="權限不足：需要管理員權限")

@app.post("/api/verify_key")
def check_key(payload: dict):
    if payload.get("key") == ADMIN_KEY:
        return {"status": "success", "role": "admin"}
    return {"status": "error", "message": "密碼錯誤"}

@app.get("/api/search")
def search_chemical(q: str = Query("")):
    conn = get_db_connection()
    cursor = conn.cursor()
    keyword = f"%{q.strip()}%"
    
    if DATABASE_URL:
        if not q.strip():
            cursor.execute("SELECT barcode, name, cas_no, smiles, formula, mw, safety_class, location, spec, note FROM chemicals LIMIT 100")
        else:
            cursor.execute("""
                SELECT barcode, name, cas_no, smiles, formula, mw, safety_class, location, spec, note 
                FROM chemicals 
                WHERE barcode ILIKE %s 
                   OR name ILIKE %s 
                   OR cas_no ILIKE %s 
                   OR smiles ILIKE %s 
                   OR location ILIKE %s 
                   OR safety_class ILIKE %s
            """, (keyword, keyword, keyword, keyword, keyword, keyword))
    else:
        if not q.strip():
            cursor.execute("SELECT barcode, name, cas_no, smiles, formula, mw, safety_class, location, spec, note FROM chemicals LIMIT 100")
        else:
            cursor.execute("""
                SELECT barcode, name, cas_no, smiles, formula, mw, safety_class, location, spec, note 
                FROM chemicals 
                WHERE barcode LIKE ? 
                   OR name LIKE ? 
                   OR cas_no LIKE ? 
                   OR smiles LIKE ? 
                   OR location LIKE ? 
                   OR safety_class LIKE ?
            """, (keyword, keyword, keyword, keyword, keyword, keyword))
            
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "barcode": row[0] or "",
            "name": row[1] or "",
            "cas_no": row[2] if row[2] else "-",
            "smiles": row[3] if row[3] else "-",
            "formula": row[4] if row[4] else "-",
            "mw": row[5] if row[5] else "-",
            "safety_class": row[6] if row[6] else "-",
            "location": row[7] if row[7] else "-",
            "spec": row[8] if row[8] else "-",
            "note": row[9] if row[9] else "-"
        })
    return results

@app.post("/api/update_location")
def update_chemical_location(payload: UpdateLocationPayload, background_tasks: BackgroundTasks):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute("UPDATE chemicals SET location = %s WHERE barcode = %s RETURNING name, cas_no, smiles, formula, mw, safety_class, spec, note;", (payload.location, payload.barcode))
            row = cursor.fetchone()
        else:
            cursor.execute("UPDATE chemicals SET location = ? WHERE barcode = ?", (payload.location, payload.barcode))
            cursor.execute("SELECT name, cas_no, smiles, formula, mw, safety_class, spec, note FROM chemicals WHERE barcode = ?", (payload.barcode,))
            row = cursor.fetchone()
            
        conn.commit()
        cursor.close()
        conn.close()
        
        if row:
            chem_data = {
                "barcode": payload.barcode,
                "name": row[0],
                "cas_no": row[1] or "",
                "smiles": row[2] or "",
                "formula": row[3] or "",
                "mw": row[4] or "",
                "safety_class": row[5] or "",
                "location": payload.location,
                "spec": row[6] or "",
                "note": row[7] or ""
            }
            background_tasks.add_task(sync_to_google_sheet, chem_data)
            return {"status": "success", "name": row[0]}
        else:
            return {"status": "error", "message": "此條碼未建檔"}
    except Exception as e:
        conn.close()
        return {"status": "error", "message": str(e)}

@app.post("/api/save_chemical")
def save_chemical(chem: Chemical, background_tasks: BackgroundTasks, x_admin_key: Optional[str] = Header(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        cursor.execute("SELECT barcode FROM chemicals WHERE barcode = %s;", (chem.barcode,))
    else:
        cursor.execute("SELECT barcode FROM chemicals WHERE barcode = ?;", (chem.barcode,))
    exists = cursor.fetchone() is not None

    if not exists:
        if x_admin_key != ADMIN_KEY:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=403, detail="全新藥品建檔入庫需要管理員權限！請先登入管理員。")

    try:
        if DATABASE_URL:
            cursor.execute("""
                INSERT INTO chemicals (barcode, name, cas_no, smiles, formula, mw, safety_class, location, spec, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (barcode) DO UPDATE SET
                    name = EXCLUDED.name,
                    cas_no = EXCLUDED.cas_no,
                    smiles = EXCLUDED.smiles,
                    formula = EXCLUDED.formula,
                    mw = EXCLUDED.mw,
                    safety_class = EXCLUDED.safety_class,
                    location = EXCLUDED.location,
                    spec = EXCLUDED.spec,
                    note = EXCLUDED.note;
            """, (chem.barcode, chem.name, chem.cas_no, chem.smiles, chem.formula, chem.mw, chem.safety_class, chem.location, chem.spec, chem.note))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO chemicals (barcode, name, cas_no, smiles, formula, mw, safety_class, location, spec, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (chem.barcode, chem.name, chem.cas_no, chem.smiles, chem.formula, chem.mw, chem.safety_class, chem.location, chem.spec, chem.note))
            
        conn.commit()
        cursor.close()
        conn.close()
        
        # 背景非同步推送到 Google Sheet，不卡住使用者介面
        background_tasks.add_task(sync_to_google_sheet, chem.dict())
        
        return {"status": "success", "mode": "update" if exists else "insert"}
    except Exception as e:
        conn.close()
        return {"status": "error", "message": str(e)}

@app.delete("/api/delete_chemical/{barcode}")
def delete_chemical(barcode: str, x_admin_key: Optional[str] = Header(None)):
    verify_admin(x_admin_key)
    conn = get_db_connection()
    cursor = conn.cursor()
    if DATABASE_URL:
        cursor.execute("DELETE FROM chemicals WHERE barcode = %s", (barcode,))
    else:
        cursor.execute("DELETE FROM chemicals WHERE barcode = ?", (barcode,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "success"}

# 點擊即可直接下載最新 Excel 檔案 (.csv / .xlsx 通用相容)
@app.get("/api/export/excel")
def export_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT barcode, name, cas_no, formula, mw, safety_class, location, spec, note, smiles FROM chemicals ORDER BY barcode ASC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    # 寫入 UTF-8 BOM 確保 Microsoft Excel 打開時中文絕對不亂碼
    output.write('\ufeff')
    output.write("條碼,藥品名稱,CAS No.,分子式,分子量(g/mol),安衛分類,位置座標,規格,備註,SMILES\n")
    for r in rows:
        row_clean = [f'"{str(val or "").replace(chr(34), chr(34)+chr(34))}"' for val in r]
        output.write(",".join(row_clean) + "\n")
    
    mem = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    output.close()
    return StreamingResponse(
        mem,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=chemicals_inventory.csv"}
    )
