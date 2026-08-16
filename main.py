from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
import psycopg2

app = FastAPI()

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "labadmin2026") # 預設管理員密碼

def get_db_connection():
    if DATABASE_URL:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, sslmode='require')
    else:
        import sqlite3
        return sqlite3.connect("lab_chemicals.db")

# 自動升級資料表欄位（修復 500 錯誤）
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
        # 自動為舊資料庫補上 formula 與 mw 欄位
        cursor.execute("ALTER TABLE chemicals ADD COLUMN IF NOT EXISTS formula VARCHAR(255);")
        cursor.execute("ALTER TABLE chemicals ADD COLUMN IF NOT EXISTS mw VARCHAR(255);")
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
        try:
            cursor.execute("ALTER TABLE chemicals ADD COLUMN formula TEXT;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE chemicals ADD COLUMN mw TEXT;")
        except Exception:
            pass
            
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

@app.get("/")
def read_root():
    return FileResponse("index.html")

def verify_admin(x_admin_key: Optional[str] = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="權限不足")

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
def update_chemical_location(payload: UpdateLocationPayload):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute("UPDATE chemicals SET location = %s WHERE barcode = %s RETURNING name;", (payload.location, payload.barcode))
            row = cursor.fetchone()
        else:
            cursor.execute("UPDATE chemicals SET location = ? WHERE barcode = ?", (payload.location, payload.barcode))
            cursor.execute("SELECT name FROM chemicals WHERE barcode = ?", (payload.barcode,))
            row = cursor.fetchone()
            
        conn.commit()
        cursor.close()
        conn.close()
        
        if row:
            return {"status": "success", "name": row[0]}
        else:
            return {"status": "error", "message": "此條碼未建檔"}
    except Exception as e:
        conn.close()
        return {"status": "error", "message": str(e)}

@app.post("/api/add_chemical")
def add_chemical(chem: Chemical, x_admin_key: Optional[str] = Header(None)):
    verify_admin(x_admin_key)
    conn = get_db_connection()
    cursor = conn.cursor()
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
        return {"status": "success"}
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

@app.get("/api/backup/json")
def backup_database_json(x_admin_key: Optional[str] = Header(None)):
    verify_admin(x_admin_key)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT barcode, name, cas_no, smiles, formula, mw, safety_class, location, spec, note FROM chemicals")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    backup_data = []
    for r in rows:
        backup_data.append({
            "barcode": r[0],
            "name": r[1],
            "cas_no": r[2],
            "smiles": r[3],
            "formula": r[4],
            "mw": r[5],
            "safety_class": r[6],
            "location": r[7],
            "spec": r[8],
            "note": r[9]
        })
    return JSONResponse(
        content=backup_data,
        headers={"Content-Disposition": "attachment; filename=lab_chemicals_backup.json"}
    )
