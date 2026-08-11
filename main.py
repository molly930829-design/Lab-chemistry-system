from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3

app = FastAPI()

def init_db():
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    
    # 建立基礎表格
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chemicals (
            barcode TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            safety_class TEXT,
            location TEXT,
            spec TEXT,
            note TEXT
        )
    """)
    
    # 自動補齊舊資料庫缺少的新欄位（避免 500 錯誤）
    cursor.execute("PRAGMA table_info(chemicals)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "cas_no" not in columns:
        cursor.execute("ALTER TABLE chemicals ADD COLUMN cas_no TEXT")
    if "smiles" not in columns:
        cursor.execute("ALTER TABLE chemicals ADD COLUMN smiles TEXT")
        
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
    
    try:
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
                "cas_no": row[2] or "-",
                "smiles": row[3] or "-",
                "safety_class": row[4] or "-",
                "location": row[5] or "-",
                "spec": row[6] or "-",
                "note": row[7] or "-"
            })
        return results
    except Exception as e:
        conn.close()
        raise e

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
