"""
CogWrite - Embed Chunks Script

作用：
- 从 Postgres 的 chunks 表读取 (chunk_id, content)
- 调用 OpenAI Embeddings API 得到向量
- 写入 embeddings 表：embeddings(chunk_id, embedding)

说明：
- 这里使用 .env 提供的配置：EMBEDDING_MODEL / EMBEDDING_API_KEY
- MVP 阶段先跑通链路：chunk -> embedding -> DB
"""

import os
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

# 1) 读取本地 .env（把里面的键值加载到当前进程环境变量里）
load_dotenv(".env")

def get_conn():
    """连接 Postgres（默认值对应 docker-compose）"""
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "cogwrite")
    password = os.getenv("DB_PASSWORD", "cogwrite")
    dbname = os.getenv("DB_NAME", "cogwrite")
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)

def vec_to_pgvector_str(vec):
    """
    把 Python list[float] 转成 pgvector 能识别的文本格式，例如：
    [0.1, -0.2, 0.3, ...]
    注意：这是字符串形式，后面会在 SQL 里用 ::vector 转型
    """
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

def main():
    # 2) 读取 embedding 配置
    api_key = os.getenv("EMBEDDING_API_KEY")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    if not api_key:
        print("[!] EMBEDDING_API_KEY is missing. Please set it in .env.")
        return

    client = OpenAI(api_key=api_key)

    conn = get_conn()
    cur = conn.cursor()

    # 3) 取出所有 chunks
    cur.execute("SELECT chunk_id, content FROM chunks ORDER BY chunk_id ASC;")
    rows = cur.fetchall()
    if not rows:
        print("[!] chunks table is empty. Run chunk_sources.py first.")
        cur.close()
        conn.close()
        return

    # 4) upsert embeddings
    upsert_sql = """
    INSERT INTO embeddings (chunk_id, embedding)
    VALUES (%s, %s::vector)
    ON CONFLICT (chunk_id) DO UPDATE SET
      embedding = EXCLUDED.embedding;
    """

    n = 0
    for chunk_id, content in rows:
        # 调用 Embeddings API：input 是文本，输出是向量
        resp = client.embeddings.create(model=model, input=content)
        vec = resp.data[0].embedding  # list[float]

        vec_str = vec_to_pgvector_str(vec)
        cur.execute(upsert_sql, (chunk_id, vec_str))
        n += 1
        print(f"[ok] embedded {chunk_id} (dim={len(vec)})")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. Embedded {n} chunk(s) into embeddings table.")

if __name__ == "__main__":
    main()
