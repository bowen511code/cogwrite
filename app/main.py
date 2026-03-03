import os
from dotenv import load_dotenv
load_dotenv()
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

@app.get("/sources/{source_id}")
def get_source(source_id: str):
    """
    按 source_id 返回单篇资料（包含正文 content）。
    后续 chunking/RAG 都需要拿到 content。
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT source_id, title, url, author, published_at, content FROM sources WHERE source_id = %s;",
        (source_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return {"error": "not_found", "source_id": source_id}

    return {
        "source_id": row[0],
        "title": row[1],
        "url": row[2],
        "author": row[3],
        "published_at": str(row[4]) if row[4] else None,
        "content": row[5],
    }

@app.get("/chunks/{source_id}")
def list_chunks(source_id: str):
    """
    返回某个 source 的所有 chunks（用于检查 chunking 效果）。
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT chunk_id, chunk_index, content FROM chunks WHERE source_id = %s ORDER BY chunk_index ASC;",
        (source_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {"chunk_id": r[0], "chunk_index": r[1], "content": r[2]}
        for r in rows
    ]

from pydantic import BaseModel

class GenerateRequest(BaseModel):
    topic: str
    top_k: int = 3

@app.post("/generate")
def generate_api(req: GenerateRequest):
    from scripts.generate_draft import generate, NoEvidenceError

    try:
        draft, chunks = generate(req.topic, req.top_k)
    except NoEvidenceError as e:
        return {
            "error": "no_evidence",
            "message": str(e),
            "topic": req.topic,
            "top_k": req.top_k,
        }
    except Exception as e:
        return {
            "error": "generation_failed",
            "message": str(e),
            "topic": req.topic,
            "top_k": req.top_k,
        }

    if not chunks:
        return {
            "error": "no_evidence",
            "message": "No relevant chunks retrieved. Add more sources or adjust query.",
            "topic": req.topic,
            "top_k": req.top_k,
        }

    return {
        "topic": req.topic,
        "top_k": req.top_k,
        "chunks": chunks,
        "draft": draft.model_dump(),
    }
