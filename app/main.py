import os
import psycopg2
from fastapi import FastAPI

app = FastAPI(title="CogWrite")

def get_conn():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "cogwrite")
    password = os.getenv("DB_PASSWORD", "cogwrite")
    dbname = os.getenv("DB_NAME", "cogwrite")
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/db/health")
def db_health():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    one = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"db": "ok", "select_1": one}

@app.get("/sources")
def list_sources():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT source_id, title, author, published_at FROM sources ORDER BY published_at DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"source_id": r[0], "title": r[1], "author": r[2], "published_at": str(r[3]) if r[3] else None}
        for r in rows
    ]
