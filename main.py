from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os

app = FastAPI()

def init_db():
    db_file = "lab_chemicals.db"
    
    # 檢查資料庫是否缺少 cas_no 欄位，若是則刪除舊檔重新建立，徹底解決 HTTP 500 錯誤
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(chemicals)")
            cols = [col[1] for col in cursor.fetchall()]
            conn.close()
            if "cas_no" not in cols or "smiles" not in cols:
                os.remove(db_file)
        except Exception:
            try:
                conn.close()
            except:
                pass
            os.remove(db_file)

    # 建立全新且含有完整欄位的資料庫
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chemicals (
            barcode TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cas_no TEXT,
            smiles TEXT,
            safety_class TEXT,
            location TEXT,
            spec TEXT,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

class Chemical(BaseModel):
    barcode: str
    name: str
    cas_no: Optional[str] = ""
    smiles: Optional[str] = ""
    safety_class: Optional[str] = ""
    location: Optional[str] = ""
    spec: Optional[str] = ""
    note: Optional[str] = ""

@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.get("/api/search")
def search_chemical(q: str = Query("")):
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    keyword = f"%{q.strip()}%"
    
    if not q.strip():
        cursor.execute("SELECT barcode, name, cas_no, smiles, safety_class, location, spec, note FROM chemicals LIMIT 50")
    else:
        cursor.execute("""
            SELECT barcode, name, cas_no, smiles, safety_class, location, spec, note 
            FROM chemicals 
            WHERE barcode LIKE ? 
               OR name LIKE ? 
               OR cas_no LIKE ? 
               OR smiles LIKE ? 
               OR location LIKE ? 
               OR safety_class LIKE ?
        """, (keyword, keyword, keyword, keyword, keyword, keyword))
    
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "barcode": row[0] or "",
            "name": row[1] or "",
            "cas_no": row[2] if row[2] else "-",
            "smiles": row[3] if row[3] else "-",
            "safety_class": row[4] if row[4] else "-",
            "location": row[5] if row[5] else "-",
            "spec": row[6] if row[6] else "-",
            "note": row[7] if row[7] else "-"
        })
    return results

@app.post("/api/add_chemical")
def add_chemical(chem: Chemical):
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO chemicals (barcode, name, cas_no, smiles, safety_class, location, spec, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (chem.barcode, chem.name, chem.cas_no, chem.smiles, chem.safety_class, chem.location, chem.spec, chem.note))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        conn.close()
        return {"status": "error", "message": str(e)}

@app.delete("/api/delete_chemical/{barcode}")
def delete_chemical(barcode: str):
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chemicals WHERE barcode = ?", (barcode,))
    conn.commit()
    conn.close()
    return {"status": "success"}
