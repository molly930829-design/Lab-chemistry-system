from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3

app = FastAPI()

# 初始化資料庫表格（自動新增 cas_no 與 smiles 欄位）
def init_db():
    conn = sqlite3.connect("lab_chemicals.db")
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

# 藥品資料結構
class Chemical(BaseModel):
    barcode: str
    name: str
    cas_no: Optional[str] = None
    smiles: Optional[str] = None
    safety_class: Optional[str] = None
    location: Optional[str] = None
    spec: Optional[str] = None
    note: Optional[str] = None

# 提供靜態首頁
@app.get("/")
def read_root():
    return FileResponse("index.html")

# 模糊搜尋 API (支援 條碼/名稱/CAS/SMILES/位置/安衛)
@app.get("/api/search")
def search_chemical(q: str = Query(..., min_length=1)):
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    
    # 使用 % 實現模糊搜尋（例如輸入 butyl 會匹配 tert-butyl acetate）
    keyword = f"%{q.strip()}%"
    
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
            "barcode": row[0],
            "name": row[1],
            "cas_no": row[2] or "-",
            "smiles": row[3] or "-",
            "safety_class": row[4] or "-",
            "location": row[5] or "-",
            "spec": row[6] or "-",
            "note": row[7] or "-"
        })
    return results

# 新增藥品 API
@app.post("/api/add_chemical")
def add_chemical(chem: Chemical):
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO chemicals (barcode, name, cas_no, smiles, safety_class, location, spec, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (chem.barcode, chem.name, chem.cas_no, chem.smiles, chem.safety_class, chem.location, chem.spec, chem.note))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except sqlite3.IntegrityError:
        conn.close()
        return {"status": "error", "message": "條碼已存在"}
