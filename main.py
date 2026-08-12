from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import psycopg2

app = FastAPI()

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if DATABASE_URL:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    else:
        import sqlite3
        return sqlite3.connect("lab_chemicals.db")

def init_db():
    if not DATABASE_URL:
        import sqlite3
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
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chemicals (
            barcode VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            cas_no VARCHAR(255),
            smiles VARCHAR(255),
            safety_class VARCHAR(255),
            location VARCHAR(255),
            spec VARCHAR(255),
            note VARCHAR(255)
        );
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
    safety_class: Optional[str] = ""
    location: Optional[str] = ""
    spec: Optional[str] = ""
    note: Optional[str] = ""

@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.get("/api/search")
def search_chemical(q: str = Query("")):
    conn = get_db_connection()
    cursor = conn.cursor()
    keyword = f"%{q.strip()}%"
    
    if DATABASE_URL:
        if not q.strip():
            cursor.execute("SELECT barcode, name, cas_no, smiles, safety_class, location, spec, note FROM chemicals LIMIT 50")
        else:
            cursor.execute("""
                SELECT barcode, name, cas_no, smiles, safety_class, location, spec, note 
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
    cursor.close()
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
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if DATABASE_URL:
            cursor.execute("""
                INSERT INTO chemicals (barcode, name, cas_no, smiles, safety_class, location, spec, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (barcode) DO UPDATE SET
                    name = EXCLUDED.name,
                    cas_no = EXCLUDED.cas_no,
                    smiles = EXCLUDED.smiles,
                    safety_class = EXCLUDED.safety_class,
                    location = EXCLUDED.location,
                    spec = EXCLUDED.spec,
                    note = EXCLUDED.note;
            """, (chem.barcode, chem.name, chem.cas_no, chem.smiles, chem.safety_class, chem.location, chem.spec, chem.note))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO chemicals (barcode, name, cas_no, smiles, safety_class, location, spec, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (chem.barcode, chem.name, chem.cas_no, chem.smiles, chem.safety_class, chem.location, chem.spec, chem.note))
            
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        conn.close()
        return {"status": "error", "message": str(e)}

@app.delete("/api/delete_chemical/{barcode}")
def delete_chemical(barcode: str):
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
