"""
CogWrite - Ingest Sources Script

作用：
- 读取 data/sources/*.md 的资料文件
- 解析文件头部的元信息（title/author/url/published_at）
- 将正文 content 和元信息一起 upsert 到 Postgres 的 sources 表

为什么要做成脚本？
- 避免手写 SQL 插入长文本（容易被引号/换行坑）
- 让“资料文件 → 数据库”变成一键可复现的 data pipeline
"""

import os
from pathlib import Path
from datetime import date
import psycopg2


# -------------------------
# 1) 路径定位（可移植性关键）
# -------------------------
# __file__ 是当前脚本文件的路径（scripts/ingest_sources.py）
# resolve() 转为绝对路径；parents[1] 回到项目根目录（cogwrite/）
ROOT = Path(__file__).resolve().parents[1]

# 用 Path 的 / 来拼接路径：ROOT/data/sources
SOURCES_DIR = ROOT / "data" / "sources"


# -------------------------
# 2) 数据库连接（配置优先走环境变量）
# -------------------------
def get_conn():
    """
    建立并返回一个 PostgreSQL 连接。

    为什么用环境变量？
    - 本地开发：默认用 docker-compose 的账号密码
    - 部署/他人使用：只需要改环境变量，不需要改代码
    """
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "cogwrite")
    password = os.getenv("DB_PASSWORD", "cogwrite")
    dbname = os.getenv("DB_NAME", "cogwrite")
    return psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname
    )


# -------------------------
# 3) 解析 md 文件：元信息 + 正文
# -------------------------
def parse_md(path: Path):
    """
    解析一个 sources/*.md 文件。

    约定格式（非常简单）：
    - 文件开头是“元信息区”，每行一个 key: value
    - 遇到第一个空行后，后面全部视为正文 content

    返回：
    - meta: dict，例如 {"title": "...", "author": "..."}
    - body: str，正文内容（后续会写入 sources.content）
    """
    lines = path.read_text(encoding="utf-8").splitlines()

    meta = {}
    body_lines = []

    in_meta = True  # 还在元信息区吗？

    for line in lines:
        if in_meta:
            # 空行：元信息结束，正文开始
            if line.strip() == "":
                in_meta = False
                continue

            # 形如 "title: xxx" 的行
            if ":" in line:
                k, v = line.split(":", 1)  # 只 split 第一个冒号，避免 value 里也有冒号
                meta[k.strip()] = v.strip()
            else:
                # 如果某行不符合 key:value 格式，就认为元信息结束
                in_meta = False
                body_lines.append(line)
        else:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    return meta, body


# -------------------------
# 4) 主流程：扫描文件 → upsert 到 DB
# -------------------------
def main():
    # 找到所有 md 文件（按文件名排序，便于输出稳定）
    md_files = sorted(SOURCES_DIR.glob("*.md"))
    if not md_files:
        print(f"[!] No .md files found in: {SOURCES_DIR}")
        return

    # 建立数据库连接
    conn = get_conn()
    cur = conn.cursor()

    # Upsert SQL：如果 source_id 已存在就更新，否则插入
    # 好处：你反复运行脚本不会重复插入，且能自动同步最新内容
    upsert_sql = """
    INSERT INTO sources (source_id, title, url, author, published_at, content)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_id) DO UPDATE SET
      title = EXCLUDED.title,
      url = EXCLUDED.url,
      author = EXCLUDED.author,
      published_at = EXCLUDED.published_at,
      content = EXCLUDED.content;
    """

    n = 0

    for p in md_files:
        # 用文件名（不含 .md）作为唯一编号 source_id
        # 例：cs_ai_002.md -> source_id="cs_ai_002"
        source_id = p.stem

        meta, body = parse_md(p)

        # 元信息缺失时给默认值，保证脚本健壮
        title = meta.get("title", source_id)
        url = meta.get("url")
        author = meta.get("author")

        # published_at 如果存在，要求是 YYYY-MM-DD（ISO 格式），便于解析
        published_at_raw = meta.get("published_at")
        published_at = date.fromisoformat(published_at_raw) if published_at_raw else None

        # 如果正文为空，就跳过（避免数据库里出现空资料）
        if not body:
            print(f"[skip] {p.name}: empty content")
            continue

        # 执行 upsert
        cur.execute(upsert_sql, (source_id, title, url, author, published_at, body))
        n += 1
        print(f"[ok] upserted {source_id} ({p.name})")

    # 提交事务：把所有写入真正落盘
    conn.commit()

    # 关闭资源（好习惯：避免连接泄漏）
    cur.close()
    conn.close()

    print(f"\nDone. Upserted {n} source(s).")


if __name__ == "__main__":
    main()
