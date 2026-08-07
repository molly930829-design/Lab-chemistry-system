# main.py
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="實驗室藥品管理系統")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chemicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            safety_class TEXT NOT NULL,
            location_id TEXT NOT NULL,
            capacity TEXT,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

class ChemicalCreate(BaseModel):
    barcode: str
    name: str
    safety_class: str
    location_id: str
    capacity: Optional[str] = ""
    note: Optional[str] = ""

# 讓手機直接輸入 IP 就能載入網頁畫面
@app.get("/")
def read_index():
    return FileResponse("index.html")

@app.post("/api/chemicals")
def add_chemical(chem: ChemicalCreate):
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO chemicals (barcode, name, safety_class, location_id, capacity, note) VALUES (?, ?, ?, ?, ?, ?)",
            (chem.barcode, chem.name, chem.safety_class, chem.location_id, chem.capacity, chem.note)
        )
        conn.commit()
        return {"status": "success", "message": "藥品建檔成功！"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="條碼號碼已存在，不可重複建檔！")
    finally:
        conn.close()

@app.get("/api/chemicals/search")
def search_chemical(q: str):
    conn = sqlite3.connect("lab_chemicals.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT barcode, name, safety_class, location_id, capacity, note 
        FROM chemicals 
        WHERE barcode LIKE ? OR name LIKE ? OR location_id LIKE ? OR safety_class LIKE ?
    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "barcode": r[0],
            "name": r[1],
            "safety_class": r[2],
            "location_id": r[3],
            "capacity": r[4],
            "note": r[5]
        })
    return {"results": results}
