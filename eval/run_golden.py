"""
CogWrite 最小回归测试脚本（golden set runner）

作用：
- 读取 eval/golden_set.jsonl
- 对每条用例运行同一条 RAG 生成链路（检索 Top-K → 生成结构化 JSON → Pydantic 校验）
- 做最基础的 sanity check：
  1) 生成过程不报错（说明 JSON 能解析且通过 schema 校验）
  2) citations 里是否包含期望的 source_id（如果用例指定了 expect_citation_source_id）

说明：
- 这是 MVP 级别的“快速冒烟测试”，不是完整评分（rubric）系统
- 后续可以增加更多指标：结构质量、互动性评分、无依据断言率等
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# 让 Python 能找到项目根目录下的 scripts/ 模块
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

# 复用 scripts/generate_draft.py 里的 generate() 函数
from scripts.generate_draft import generate  # noqa: E402

# 加载本地 .env（注意：.env 不会被提交到 GitHub）
load_dotenv(str(ROOT / ".env"))

# golden set 文件路径
GOLDEN = ROOT / "eval" / "golden_set.jsonl"


def main():
    if not GOLDEN.exists():
        print(f"[!] 找不到 golden set 文件：{GOLDEN}")
        return

    total = 0
    passed = 0

    # JSONL：一行一个 JSON，用 splitlines() 一行行读取
    for line in GOLDEN.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue

        case = json.loads(line)
        cid = case["id"]
        topic = case["topic"]
        top_k = int(case.get("top_k", 3))
        expect_source = case.get("expect_citation_source_id")

        total += 1
        print(f"\n=== 用例 {cid} ===")
        print(f"Topic: {topic}")

        # 运行生成链路（如果失败会抛异常）
        try:
            draft, chunks = generate(topic, top_k=top_k)
        except Exception as e:
            print(f"[FAIL] 运行异常：{e}")
            continue

        ok = True

        # 检查 citations 是否包含期望的 source_id（如果用例要求）
        if expect_source:
            cited_sources = {c.source_id for c in draft.citations}
            if expect_source not in cited_sources:
                ok = False
                print(f"[FAIL] 期望 citations 包含 source_id={expect_source}，但实际是：{sorted(cited_sources)}")

        if ok:
            passed += 1
            print("[PASS]")

    print(f"\n汇总：{passed}/{total} 通过")


if __name__ == "__main__":
    main()
