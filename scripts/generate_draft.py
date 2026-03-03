"""
CogWrite - Generate Draft Script (teaching version, CLI)

功能（MVP）：
1) 输入 topic
2) 向量检索 Top-K chunks（证据包）
3) Jinja2 渲染 prompts/system.j2 + prompts/generate.j2
4) 调用 LLM 生成严格 JSON
5) Pydantic 校验输出结构

网络鲁棒性（可配置开关）：
- OPENAI_TIMEOUT / OPENAI_CONNECT_TIMEOUT / OPENAI_FORCE_IPV4 / OPENAI_PROXY
这些由 scripts/openai_client.py 统一处理。
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Literal

import psycopg2
from dotenv import load_dotenv
from jinja2 import Template
from pydantic import BaseModel, Field, ValidationError

from scripts.openai_client import make_openai_client

class NoEvidenceError(Exception):
    """Top-K 证据相关性不足时抛出，用于 API 层返回 no_evidence。"""
    pass

# 加载本地 .env（不提交到 GitHub）
load_dotenv(".env")

ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = ROOT / "prompts"


# -------------------------
# 1) Pydantic 输出 schema（结构化输出与校验）
# -------------------------
class OutlineSection(BaseModel):
    section_title: str
    bullets: List[str]

class Punchline(BaseModel):
    type: Literal["hook", "transition", "ending"]
    text: str

class InteractiveQuestion(BaseModel):
    type: Literal["mcq", "open", "self_test"]
    text: str

class Citation(BaseModel):
    claim: str
    source_id: str
    chunk_id: str
    evidence_snippet: str

class GeneratedDraft(BaseModel):
    outline: List[OutlineSection]
    punchlines: List[Punchline]
    interactive_questions: List[InteractiveQuestion]
    citations: List[Citation] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)


# -------------------------
# 2) DB + 向量检索（RAG 的 Retrieval）
# -------------------------
def get_conn():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "cogwrite")
    password = os.getenv("DB_PASSWORD", "cogwrite")
    dbname = os.getenv("DB_NAME", "cogwrite")
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)

def vec_to_pgvector_str(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

def retrieve_topk_chunks(topic: str, top_k: int):
    api_key = os.getenv("EMBEDDING_API_KEY")
    emb_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    if not api_key:
        raise RuntimeError("EMBEDDING_API_KEY missing in .env")

    client = make_openai_client(api_key)
    resp = client.embeddings.create(model=emb_model, input=topic)
    qvec = resp.data[0].embedding
    qvec_str = vec_to_pgvector_str(qvec)

    conn = get_conn()
    cur = conn.cursor()
    sql = """
    SELECT
      e.chunk_id,
      c.source_id,
      c.chunk_index,
      c.content,
      (e.embedding <=> %s::vector) AS cosine_distance
    FROM embeddings e
    JOIN chunks c ON c.chunk_id = e.chunk_id
    ORDER BY (e.embedding <=> %s::vector) ASC
    LIMIT %s;
    """
    cur.execute(sql, (qvec_str, qvec_str, top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    out = []
    for r in rows:
        dist = float(r[4])
        sim = 1.0 - dist
        out.append({
            "chunk_id": r[0],
            "source_id": r[1],
            "chunk_index": r[2],
            "content": r[3],
            "cosine_distance": dist,
            "similarity": sim,
        })
    return out


# -------------------------
# 3) Prompt 模板渲染（模板化与版本管理）
# -------------------------
def load_template(path: Path) -> Template:
    return Template(path.read_text(encoding="utf-8"))

def build_messages(topic: str, chunks: list):
    system_t = load_template(PROMPTS_DIR / "system.j2")
    gen_t = load_template(PROMPTS_DIR / "generate.j2")

    chunks_json = json.dumps(chunks, ensure_ascii=False, indent=2)

    system_text = system_t.render()
    user_text = gen_t.render(topic=topic, chunks_json=chunks_json)

    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_text},
    ]


# -------------------------
# 4) 调用生成模型（AG）并校验 JSON
# -------------------------
def generate(topic: str, top_k: int):
    gen_api_key = os.getenv("GEN_API_KEY") or os.getenv("EMBEDDING_API_KEY")
    gen_model = os.getenv("GEN_MODEL", "gpt-4.1-mini")
    if not gen_api_key:
        raise RuntimeError("GEN_API_KEY missing (or reuse EMBEDDING_API_KEY)")

    chunks = retrieve_topk_chunks(topic, top_k=top_k)
    min_sim = float(os.getenv("EVIDENCE_MIN_SIM", "0.5"))
    best_sim = chunks[0].get("similarity", 0.0) if chunks else 0.0
    if (not chunks) or (best_sim < min_sim):
        raise NoEvidenceError(f"no_evidence: best_similarity={best_sim:.3f} < {min_sim:.3f}")
    messages = build_messages(topic, chunks)

    client = make_openai_client(gen_api_key)
    resp = client.chat.completions.create(
        model=gen_model,
        messages=messages,
        temperature=0.3,
    )
    text = resp.choices[0].message.content

    data = json.loads(text)
    draft = GeneratedDraft.model_validate(data)
    return draft, chunks


def main():
    parser = argparse.ArgumentParser(description="CogWrite RAG draft generator")
    parser.add_argument("--topic", type=str, required=True, help="写作选题/问题")
    parser.add_argument("--top-k", type=int, default=3, help="检索 Top-K chunks 数量")
    args = parser.parse_args()

    try:
        draft, chunks = generate(args.topic, args.top_k)
    except json.JSONDecodeError:
        print("[!] 模型输出不是合法 JSON。下一步可以加 JSON 修复 fallback。")
        raise
    except ValidationError as e:
        print("[!] JSON 解析成功但 schema 校验失败：")
        print(e)
        raise

    print("=== Retrieved Chunks (TopK) ===")
    print(json.dumps(chunks, ensure_ascii=False, indent=2))
    print("\n=== Generated Draft (validated) ===")
    print(draft.model_dump_json(ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
