"""
CogWrite - Search Chunks Script

作用：
- 对用户 query 生成 embedding
- 用 pgvector 在 embeddings 表中做相似度检索
- 返回最相关的 Top-K chunks（用于 RAG 证据检索）

说明：
- 这里使用 cosine distance（向量余弦距离）
- pgvector 中的 <=> 操作符：cosine distance（数值越小越相近）
"""

import os
from dotenv import load_dotenv
import psycopg2
from openai import OpenAI

load_dotenv(".env")

def get_conn():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "cogwrite")
    password = os.getenv("DB_PASSWORD", "cogwrite")
    dbname = os.getenv("DB_NAME", "cogwrite")
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)

def vec_to_pgvector_str(vec):
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

def main():
    api_key = os.getenv("EMBEDDING_API_KEY")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    if not api_key:
        print("[!] EMBEDDING_API_KEY missing in .env")
        return

    query = os.getenv("QUERY", "如何把间隔重复和提取练习结合起来？")
    top_k = int(os.getenv("TOP_K", "3"))

    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(model=model, input=query)
    qvec = resp.data[0].embedding
    qvec_str = vec_to_pgvector_str(qvec)

    conn = get_conn()
    cur = conn.cursor()

    # cosine distance：越小越相近；为了好读，我们同时输出 similarity = 1 - distance
    sql = """
    SELECT
      e.chunk_id,
      (e.embedding <=> %s::vector) AS cosine_distance,
      c.source_id,
      c.chunk_index,
      c.content
    FROM embeddings e
    JOIN chunks c ON c.chunk_id = e.chunk_id
    ORDER BY e.embedding <=> %s::vector ASC
    LIMIT %s;
    """

    cur.execute(sql, (qvec_str, qvec_str, top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    print(f"Query: {query}\nTopK: {top_k}\n")
    for chunk_id, dist, source_id, chunk_index, content in rows:
        sim = 1.0 - float(dist)
        preview = content.replace("\n", " ")[:140]
        print(f"- {chunk_id} | source={source_id} idx={chunk_index} | similarity≈{sim:.4f}")
        print(f"  {preview}...\n")

if __name__ == "__main__":
    main()
