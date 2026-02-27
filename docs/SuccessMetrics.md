# Success Metrics — CogWrite

本项目用可量化指标衡量“写作效率、写作质量、引用可靠性、稳定性、成本/延迟”。

## 1) 写作效率（Efficiency）
- T_draft：生成首稿所需时间（秒）
- N_iter：达到“可发布稿”的平均迭代次数（次）
- Throughput：单位时间生成稿件数（篇/小时）

## 2) 写作质量（Quality）
用 rubric（1-5 分）对每篇输出打分：
- Structure：结构清晰度（提纲是否合理、层次是否清楚）
- Readability：可读性（语言流畅、逻辑连贯）
- Actionability：可行动性（是否给出可操作建议/练习）
- Engagement：互动性（问题是否具体、能引发讨论）

## 3) 引用可靠性（Grounding）
- CitationCoverage：关键结论中带证据引用的比例（%）
- UnsupportedClaimRate：无证据断言比例（%）
- CitationPrecision（抽样）：引用片段是否真正支持 claim（%）

## 4) 稳定性（Reliability）
- SchemaPassRate：结构化输出校验通过率（%）
- RetryRate：触发重试的比例（%）
- FallbackRate：触发降级/切换模型的比例（%）

## 5) 成本与延迟（Cost & Latency）
- CostPerArticle：每篇内容平均 token 成本（或人民币/美元）
- P50/P95 Latency：生成延迟的中位数/95 分位（秒）

## 6) 目标（MVP 阶段）
- SchemaPassRate ≥ 95%
- UnsupportedClaimRate 尽量低（目标 ≤ 5%）
- P95 Latency 可接受（例如 ≤ 30s，后续可调）
