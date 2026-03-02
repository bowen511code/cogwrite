"""
CogWrite - Generate Draft Script

目标（MVP）：
1) 输入 topic
2) 用向量检索拿 Top-K chunks（证据包）
3) 用 Jinja2 渲染 prompts/system.j2 + prompts/generate.j2
4) 调用 LLM 生成严格 JSON
5) 用 Pydantic 校验输出结构（不通过就报错，后续可加修复 fallback）

依赖：
- openai
- python-dotenv
- psycopg2-binary
- jinja2
- pydantic
"""

import json
import os
from pathlib import Path
from typing import List, Literal, Optional

import psycopg2
from dotenv import load_dotenv
from jinja2 import Template
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

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
# 2) DB 连接 + 向量检索
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

def retrieve_topk_chunks(topic: str, top_k: int = 3):
    """
    用 embedding + pgvector 检索最相关的 Top-K chunks。
    返回：list[dict]，每条包含 source_id, chunk_id, content
    """
    api_key = os.getenv("EMBEDDING_API_KEY")
    emb_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    if not api_key:
        raise RuntimeError("EMBEDDING_API_KEY missing in .env")

    client = OpenAI(api_key=api_key)
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
      c.content
    FROM embeddings e
    JOIN chunks c ON c.chunk_id = e.chunk_id
    ORDER BY e.embedding <=> %s::vector ASC
    LIMIT %s;
    """
    cur.execute(sql, (qvec_str, top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {"chunk_id": r[0], "source_id": r[1], "chunk_index": r[2], "content": r[3]}
        for r in rows
    ]


# -------------------------
# 3) Prompt 模板渲染（模板化与版本管理）
# -------------------------
def load_template(path: Path) -> Template:
    return Template(path.read_text(encoding="utf-8"))

def build_messages(topic: str, chunks: list):
    """
    读取 prompts/system.j2 和 prompts/generate.j2，并渲染为最终提示词文本。
    为了便于模型消费，把 chunks 以 JSON 字符串形式塞进去。
    """
    system_t = load_template(PROMPTS_DIR / "system.j2")
    gen_t = load_template(PROMPTS_DIR / "generate.j2")

    chunks_json = json.dumps(chunks, ensure_ascii=False, indent=2)

    system_text = system_t.render()
    user_text = gen_t.render(topic=topic, chunks_json=chunks_json)

    # OpenAI chat 格式 messages
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_text},
    ]


# -------------------------
# 4) 调用生成模型并校验结构
# -------------------------
def generate(topic: str, top_k: int = 3):
    gen_api_key = os.getenv("GEN_API_KEY") or os.getenv("EMBEDDING_API_KEY")
    gen_model = os.getenv("GEN_MODEL", "gpt-4.1-mini")  # 可按需改
    if not gen_api_key:
        raise RuntimeError("GEN_API_KEY missing (or reuse EMBEDDING_API_KEY)")

    chunks = retrieve_topk_chunks(topic, top_k=top_k)
    messages = build_messages(topic, chunks)

    client = OpenAI(api_key=gen_api_key)
    resp = client.chat.completions.create(
        model=gen_model,
        messages=messages,
        temperature=0.3,
    )
    text = resp.choices[0].message.content

    # 尝试把模型输出当 JSON 解析
    data = json.loads(text)

    # Pydantic 校验结构（不通过会抛 ValidationError）
    draft = GeneratedDraft.model_validate(data)
    return draft, chunks


def main():
    topic = os.getenv("TOPIC", "如何把间隔重复和提取练习结合起来用于学习与写作？")
    top_k = int(os.getenv("TOP_K", "3"))

    try:
        draft, chunks = generate(topic, top_k=top_k)
    except json.JSONDecodeError:
        print("[!] Model output is not valid JSON. Consider adding a JSON-repair fallback.")
        raise
    except ValidationError as e:
        print("[!] JSON parsed but failed schema validation:")
        print(e)
        raise

    print("=== Topic ===")
    print(topic)
    print("\n=== Retrieved Chunks (TopK) ===")
    print(json.dumps(chunks, ensure_ascii=False, indent=2))
    print("\n=== Generated Draft (validated) ===")
    print(draft.model_dump_json(ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
