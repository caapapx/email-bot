# Phase 2 Persona 推断改造记录

## TL;DR

将 Phase 2 persona/business 推断从硬编码模板改为 LLM 推断（kimi-k2.5）。
旧脚本输出 3 条泛化假设 + 固定置信度；LLM 输出 5 条 persona + 4 条 business，每条带具体证据链。

---

## 变更概要

| 项目 | 内容 |
|------|------|
| 日期 | 2026-03-18 |
| 变更类型 | refactor / enhancement |
| 影响范围 | Phase 2 persona + business inference |
| 新增脚本 | `scripts/phase2_loading.sh`, `scripts/phase2_thinking.sh` |
| 保留脚本 | `scripts/phase2_profile_inference.sh`（fallback） |
| LLM 后端 | DashScope OpenAI-compatible API, model: kimi-k2.5 |

---

## 改造前后对比

### Persona 假设

| 维度 | 旧（硬编码） | 新（LLM） |
|------|------------|-----------|
| 假设数量 | 3 条固定 | 5 条，按证据强度排列 |
| 置信度 | 0.88 / 0.85 / 0.80（写死） | 0.92 / 0.88 / 0.85 / 0.75 / 0.65（LLM 评估） |
| 证据 | `internal_ratio=0.xxxx` 等统计值 | 具体邮件内容、称呼、项目名、频次 |
| 信息密度 | "内部项目协同与交付推进角色" | "项目交付部门的中层管理者，负责审批资源申请和版本发布" |

旧 P1: `用户主要承担内部项目协同与交付推进角色` (0.88)
新 P1: `该邮箱所有者是项目交付部门的中层管理者，负责审批资源申请和版本发布` (0.92)
  → evidence: "多封邮件中出现'任浩总''浩总好'等称呼，显示其管理身份"

旧脚本完全没有的发现：
- P2: 负责辽宁区域四大运营商发卡质检项目（从"辽宁"文件夹 + 日报频次推断）
- P4: 工作沟通以简短审批回复为主（从"答复"关键词 18 次 + "同意"二字回复推断）
- P5: 参与保密资质续审（confidence=0.65，正确标记为低置信）

### Business 假设

| 维度 | 旧（硬编码） | 新（LLM） |
|------|------------|-----------|
| 假设数量 | 3 条 | 4 条 |
| 具体度 | "邮件活动中心围绕项目交付" | "合肥讯飞数码科技有限公司…主营AI安全质检、大数据治理及语音识别解决方案" |
| 业务洞察 | 无 | 识别出预投项目管理模式、合同转化率 68%、二级保密资质 |

旧 B1: `公司邮件活动中心围绕项目交付、研发联调、资源申请与合规通知` (0.90)
新 B2: `公司业务覆盖辽宁、江苏、天津、贵州、湖北、江西等多省份的运营商及政府安全项目` (0.85)
  → evidence: 逐省列出项目代号

旧脚本完全没有的发现：
- B3: 预投项目管理模式，104 个预投项目，合同转化率 68%（从月报正文提取）
- B4: 二级保密资质 + 出口管制合规（从合规邮件推断，confidence=0.72）

---

## 架构变化

```
旧: phase2_profile_inference.sh
    读 census.json → 硬编码 if/else → 模板填充 → YAML

新: phase2_loading.sh → phase2_thinking.sh
    读 census + intent results + bodies
    → 构建 context-pack.json（enriched samples with LLM intent labels）
    → 单次 LLM 调用 → 解析 JSON → YAML + report
```

Phase 2 loading 层的关键改进：将 Phase 1 的 LLM intent 结果注入 context pack，
使 Phase 2 的 LLM 能基于真实 intent 分布做推断，而不是基于 regex 误判的分布。

---

## 已知局限

1. 单次 LLM 调用处理全部推断，context 较长（~30 封 enriched sample），token 消耗约 8K input
2. 置信度仍由 LLM 自评，无外部校准机制
3. 未接入人工上下文通道（manual-habits.yaml / manual-facts.yaml），后续需补充
