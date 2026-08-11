from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3

app = FastAPI()

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
    
    # 如果搜尋條件空白，就列出前 50 筆資料
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
