import os
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import psycopg2
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_KEY = os.getenv("ADMIN_KEY", "labadmin2026")

def get_db_connection():
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="未設定 DATABASE_URL 環境變數")
    return psycopg2.connect(DATABASE_URL)

class ChemicalPayload(BaseModel):
    barcode: str
    name: str
    chinese_name: str = "-"
    cas_no: str = "-"
    smiles: str = "-"
    formula: str = "-"
    mw: str = "-"
    safety_class: str = "-"
    location: str = "-"
    spec: str = "-"
    vendor: str = "-"
    note: str = "-"

class LocationUpdatePayload(BaseModel):
    barcode: str
    location: str

class VerifyPayload(BaseModel):
    key: str

@app.get("/", response_class=HTMLResponse)
def serve_index():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>系統運作中，未找到 index.html</h1>"

@app.post("/api/verify_key")
def verify_key(payload: VerifyPayload):
    if payload.key == ADMIN_KEY:
        return {"status": "success", "message": "驗證通過"}
    raise HTTPException(status_code=401, detail="密碼錯誤")

@app.get("/api/search")
def search_chemicals(q: str = ""):
    conn = get_db_connection()
    cursor = conn.cursor()
    query_str = q.strip()
    
    # 放寬至 2000 筆，並以 barcode ASC 嚴格遞增排序
    if not query_str:
        sql = """
            SELECT barcode, name, chinese_name, cas_no, smiles, formula, mw, 
                   safety_class, location, spec, vendor, note 
            FROM chemicals 
            ORDER BY barcode ASC 
            LIMIT 2000;
        """
        cursor.execute(sql)
    else:
        sql = """
            SELECT barcode, name, chinese_name, cas_no, smiles, formula, mw, 
                   safety_class, location, spec, vendor, note 
            FROM chemicals 
            WHERE barcode ILIKE %s 
               OR name ILIKE %s 
               OR chinese_name ILIKE %s 
               OR cas_no ILIKE %s 
               OR location ILIKE %s 
               OR vendor ILIKE %s 
            ORDER BY barcode ASC 
            LIMIT 2000;
        """
        pat = f"%{query_str}%"
        cursor.execute(sql, (pat, pat, pat, pat, pat, pat))
        
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "barcode": r[0],
            "name": r[1] or "-",
            "chinese_name": r[2] or "-",
            "cas_no": r[3] or "-",
            "smiles": r[4] or "-",
            "formula": r[5] or "-",
            "mw": str(r[6]) if r[6] is not None else "-",
            "safety_class": r[7] or "-",
            "location": r[8] or "-",
            "spec": r[9] or "-",
            "vendor": r[10] or "-",
            "note": r[11] or "-"
        })
    return results

@app.post("/api/update_location")
def update_location(payload: LocationUpdatePayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM chemicals WHERE barcode = %s", (payload.barcode,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="查無此條碼藥品")
    
    chem_name = row[0]
    cursor.execute("UPDATE chemicals SET location = %s WHERE barcode = %s", (payload.location, payload.barcode))
    conn.commit()
    cursor.close()
    conn.close()

    return {"status": "success", "name": chem_name, "location": payload.location}

@app.post("/api/save_chemical")
def save_chemical(payload: ChemicalPayload, x_admin_key: str = Header(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT barcode FROM chemicals WHERE barcode = %s", (payload.barcode,))
    exists = cursor.fetchone()

    if not exists and x_admin_key != ADMIN_KEY:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="全新藥品入庫建檔需要管理員權限")

    mw_val = None
    try:
        if payload.mw and payload.mw != "-":
            mw_val = float(payload.mw)
    except:
        pass

    if exists:
        sql = """
            UPDATE chemicals 
            SET name = %s, chinese_name = %s, cas_no = %s, smiles = %s, formula = %s, 
                mw = %s, safety_class = %s, location = %s, spec = %s, vendor = %s, note = %s 
            WHERE barcode = %s;
        """
        cursor.execute(sql, (
            payload.name, payload.chinese_name, payload.cas_no, payload.smiles, payload.formula,
            mw_val, payload.safety_class, payload.location, payload.spec, payload.vendor, payload.note,
            payload.barcode
        ))
        mode = "update"
    else:
        sql = """
            INSERT INTO chemicals (barcode, name, chinese_name, cas_no, smiles, formula, mw, safety_class, location, spec, vendor, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        cursor.execute(sql, (
            payload.barcode, payload.name, payload.chinese_name, payload.cas_no, payload.smiles, payload.formula,
            mw_val, payload.safety_class, payload.location, payload.spec, payload.vendor, payload.note
        ))
        mode = "insert"

    conn.commit()
    cursor.close()
    conn.close()

    return {"status": "success", "mode": mode}

@app.delete("/api/delete_chemical/{barcode}")
def delete_chemical(barcode: str, x_admin_key: str = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="刪除藥品需要管理員權限")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chemicals WHERE barcode = %s", (barcode,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "success", "barcode": barcode}

@app.get("/api/export/excel")
def export_excel():
    conn = get_db_connection()
    df = pd.read_sql("SELECT barcode AS 條碼, name AS 英文名稱, chinese_name AS 中文名稱, cas_no AS CAS, formula AS 分子式, mw AS 分子量, safety_class AS 安衛分類, location AS 擺放位置, spec AS 規格, vendor AS 廠商, note AS 備註 FROM chemicals ORDER BY barcode ASC", conn)
    conn.close()
    
    file_path = "chemicals_export.xlsx"
    df.to_excel(file_path, index=False)
    return FileResponse(file_path, filename="實驗室藥品清冊.xlsx")
