"""
CogWrite - Chunk Sources Script

作用：
- 从 Postgres 的 sources 表读取正文 content
- 按“近似字符长度”切成多个 chunk（MVP 先用简单切法）
- 将 chunk 写入 chunks 表（chunk_id, source_id, chunk_index, content）

说明：
- MVP 阶段我们先用简单规则：按固定长度切 + 少量重叠 overlap
- 进阶再换成更智能的切法（按段落/句子/标题）
"""

import os
from pathlib import Path
import psycopg2

# -------------------------
# 1) 切块参数（MVP）
# -------------------------
CHUNK_SIZE = 350      # 每块大约 350 个字符（中文/英文都适用，先粗略）
CHUNK_OVERLAP = 60    # 相邻 chunk 重叠 60 个字符，避免关键信息被切断


def get_conn():
    """连接 Postgres（优先读环境变量，没配就用默认 docker-compose 配置）"""
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "cogwrite")
    password = os.getenv("DB_PASSWORD", "cogwrite")
    dbname = os.getenv("DB_NAME", "cogwrite")
    return psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)


def make_chunks(text: str):
    """
    将文本切成多个 chunk（简单版）。
    返回：list[str]
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + CHUNK_SIZE, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        # 下一段从 end - overlap 开始（保证重叠）
        if end == n:
            break
        start = max(end - CHUNK_OVERLAP, 0)

    return chunks


def main():
    conn = get_conn()
    cur = conn.cursor()

    # 读取所有 sources
    cur.execute("SELECT source_id, content FROM sources ORDER BY published_at DESC;")
    sources = cur.fetchall()

    if not sources:
        print("[!] sources table is empty. Run ingest_sources.py first.")
        cur.close()
        conn.close()
        return

    # 写入 chunks：用 upsert 避免重复
    upsert_sql = """
    INSERT INTO chunks (chunk_id, source_id, chunk_index, content)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (chunk_id) DO UPDATE SET
      content = EXCLUDED.content;
    """

    total_chunks = 0

    for source_id, content in sources:
        # 先清理旧 chunks（保证每次运行是“重新生成一套”）
        # MVP 简化：直接删掉该 source 的旧 chunks，再写新的
        cur.execute("DELETE FROM chunks WHERE source_id = %s;", (source_id,))

        parts = make_chunks(content)
        for idx, part in enumerate(parts):
            chunk_id = f"{source_id}__{idx:04d}"
            cur.execute(upsert_sql, (chunk_id, source_id, idx, part))
            total_chunks += 1

        print(f"[ok] {source_id}: {len(parts)} chunk(s)")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone. Wrote {total_chunks} chunk(s) into chunks table.")


if __name__ == "__main__":
    main()
