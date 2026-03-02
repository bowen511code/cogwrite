"""
CI-friendly golden set format checker.

目的：
- 不依赖数据库/外部 API
- 只检查 eval/golden_set.jsonl 是否每行都是合法 JSON
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval" / "golden_set.jsonl"

def main():
    if not GOLDEN.exists():
        raise SystemExit(f"golden set not found: {GOLDEN}")

    n = 0
    for i, line in enumerate(GOLDEN.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except Exception as e:
            raise SystemExit(f"Invalid JSON at line {i}: {e}")
        n += 1

    print(f"golden_format_ok: {n} case(s)")

if __name__ == "__main__":
    main()
