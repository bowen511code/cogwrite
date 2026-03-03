![CI](https://github.com/bowen511code/cogwrite/actions/workflows/ci.yml/badge.svg)
# CogWrite — 认知科学×AI 自媒体写作助手

输入选题与资料，输出结构化提纲、金句、可追溯引用与互动问题的写作助手。

## 目标
- 做出一个可运行的 AI 写作助手（MVP 可用）
- 全流程按 DevOps：scoping → data → modeling → deployment
- 用评测与指标量化提升：写作效率、写作质量、引用可靠性、成本/延迟

## 核心功能（MVP）
- Outline：生成提纲
- Punchlines：生成金句（开头/转折/收尾）
- Interactive Questions：生成互动问题（投票/开放题/自测）
- Citations：引用可追溯（source_id + evidence_snippet），证据不足则标注

## 技术栈（计划）
- LLM 调用：API/SDK、streaming、timeout/retry/fallback
- Prompt 模板化：prompt library、版本管理
- 结构化输出：JSON schema + 校验修复
- RAG：chunking + embedding + 向量检索 + 引用回指
- 评测：golden set + rubric + 回归测试
- DevOps：GitHub Actions（CI）、Docker/Docker Compose（部署）

## 里程碑
- [ ] Scoping 文档：PRD / SuccessMetrics / RiskPolicy
- [ ] Data：资料入库 + chunking + 索引
- [ ] Modeling：分步生成 + 引用门控 + schema 校验
- [ ] Evaluation：golden set + regression report
- [ ] Deployment：docker compose 一键运行 + CI pipeline

## 本地运行（开发模式）

### 1) 启动数据库（Postgres + pgvector）
```bash
docker compose -f infra/docker-compose.yml up -d
```

### 2) 启动数据库（Postgres + pgvector）
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
### 3) 启动 API 服务
```bash
uvicorn app.main:app --reload --port 8000
```
### 4) 访问接口文档（Swagger UI)
http://127.0.0.1:8000/docs

### 5) 命令行生成示例（CLI）
> 注意：脚本以模块方式运行，避免 `No module named 'scripts'` 的导入问题。
```bash
python -m scripts.generate_draft --topic "如何把间隔重复和提取练习结合起来用于学习与写作？" --top-k 2
```
### 6) 证据门控阈值说明
> 系统采用证据门控（EVIDENCE_MIN_SIM）：当 Top-1 chunk 相似度低于阈值时返回 no_evidence，避免无依据生成。
