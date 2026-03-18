# Phase 1 Intent 分类改造记录

## TL;DR

将 Phase 1 intent 分类从 8 条 regex 硬匹配改为 LLM batch 推断（kimi-k2.5）。
30 封实测样本中 regex 与 LLM 分类不一致率 93%，regex 系统性误判。

---

## 变更概要

| 项目 | 内容 |
|------|------|
| 日期 | 2026-03-18 |
| 变更类型 | refactor / enhancement |
| 影响范围 | Phase 1 intent classification |
| 新增脚本 | `scripts/phase1_loading.sh`, `scripts/phase1_thinking.sh` |
| 保留脚本 | `scripts/phase1_mailbox_census.sh`（fallback） |
| LLM 后端 | DashScope OpenAI-compatible API, model: kimi-k2.5 |
| 关联提交 | `feat: split phase1 into loading/thinking layers with LLM intent classification` |

---

## 改造前：regex 分类器

`phase1_mailbox_census.sh` 内嵌 `classifyIntent` 函数，8 条 regex 顺序匹配：

```javascript
const rules = [
  ['support',         [/支持|故障|报错|问题|support|ticket|help/]],
  ['finance',         [/发票|报销|付款|对账|预算|财务|合同|invoice|payment/]],
  ['recruiting',      [/招聘|面试|候选人|简历|offer|猎头|hr/]],
  ['scheduling',      [/会议|日程|邀约|安排|时间|calendar|meeting/]],
  ['receipt',         [/回执|收据|receipt|confirmation|确认函/]],
  ['newsletter',      [/newsletter|digest|报名开启|活动|分享|讲座|课程/]],
  ['internal_update', [/通知|公告|政策|制度|周报|月报|合规|宣导|培训/]],
  ['human',           [/.*/]],  // fallback
];
```

核心缺陷：
1. 顺序优先——"问题"一词命中 `support`，导致资源申请、版本发布邮件全部误分
2. 类别粒度不足——没有 `resource_request`、`release`、`compliance`
3. 置信度缺失——只有 intent 标签，没有 confidence 和 evidence

## 改造后：loading / thinking 分层

```
phase1_loading.sh          phase1_thinking.sh
┌──────────────┐           ┌──────────────────────┐
│ himalaya 拉取 │           │ 读 sample-bodies.json │
│ envelope 合并 │    ──→    │ 按 batch 调 LLM API   │
│ body 采样     │           │ 解析 JSON 结果         │
│ 结构化统计    │           │ 合并 → census + report │
└──────────────┘           └──────────────────────┘
确定性，无 LLM              kimi-k2.5, batch=10
```

thinking 脚本支持三种后端（按优先级）：
1. `LLM_API_KEY` → OpenAI-compatible API（当前使用）
2. `ANTHROPIC_API_KEY` → Anthropic API
3. `claude` CLI → 需在独立终端运行

---

## 实测对比：regex vs LLM（30 封样本）

### 汇总

| 指标 | 值 |
|------|-----|
| 样本量 | 30 封（Phase 1 body sample） |
| 不一致数 | 28 / 30 |
| 不一致率 | 93% |
| LLM 平均置信度 | 0.92 |

### 逐条对比

```
idx | subject                        | regex           | LLM              | conf  | match
----|--------------------------------|-----------------|------------------|-------|------
  0 | 关于为二级资质续审现场审查备考的通知 | scheduling      | compliance       | 0.95 |  N
  1 | 2026年科大讯飞出口管制合规政策声明   | support         | compliance       | 0.98 |  N
  2 | Re: Fw: 【联调联试告知单】FDZ3.1  | support         | resource_request | 0.90 |  N
  3 | 【报名开启】AI提效实践分享·第二期    | newsletter      | newsletter       | 0.92 |  Y
  4 | Re: Fw: 【联调联试告知单】FDZ3.1  | support         | resource_request | 0.85 |  N
  5 | Fw: 【联调联试告知单】FDZ3.1.0    | support         | resource_request | 0.88 |  N
  6 | 湖北ZZPT三期系统入HW测评部署报错记录 | support         | support          | 0.90 |  Y
  7 | Re: AQ01-TJ0S2Z-BBT-2025项目   | support         | resource_request | 0.92 |  N
  8 | 回复: 【联调联试】                 | scheduling      | release          | 0.88 |  N
  9 | 【版本发布】FDZ3.0.1_JXTGJ1.15   | support         | release          | 0.95 |  N
 10 | Re: 冷泉项目1.2.1版本升级资源申请   | support         | resource_request | 0.95 |  N
 11 | Re: AQ01-TJ0S2Z-BBT-2025项目   | support         | resource_request | 0.95 |  N
 12 | 【联调联试】                      | scheduling      | release          | 0.90 |  N
 13 | Re: AQ01-TJ0S2Z-BBT-2025项目   | support         | resource_request | 0.95 |  N
 14 | Re: 【版本申请】智能建模V5.1.5      | support         | resource_request | 0.95 |  N
 15 | 【版本申请】智能建模V5.1.5-1006     | support         | resource_request | 0.95 |  N
 16 | 【检查结果】项目交付体系执行结果同步    | finance         | internal_update  | 0.90 |  N
 17 | 民品业务群预投项目2月进展分析报告       | finance         | internal_update  | 0.90 |  N
 18 | Re: 冷泉项目1.2.1版本升级资源申请   | support         | resource_request | 0.95 |  N
 19 | 智能中台V1.0.1联调联试信息同步       | scheduling      | release          | 0.90 |  N
 20 | 冷泉项目1.2.1版本升级资源申请        | support         | resource_request | 0.98 |  N
 21 | 冷泉项目1.2.1版本升级资源申请        | support         | resource_request | 0.98 |  N
 22 | 【双月报】民品产品化版本与研究院核心技术  | support         | internal_update  | 0.95 |  N
 23 | 李震工作周报（2026-03-09至03-13）  | support         | internal_update  | 0.92 |  N
 24 | Re: 【资源申请】江苏AQ-DSJ项目K8s   | support         | release          | 0.88 |  N
 25 | 回复: zcb项目8c语料库_V1.0.0版本   | support         | release          | 0.90 |  N
 26 | 交付四区技术团队工作周报               | support         | internal_update  | 0.95 |  N
 27 | 回复: TJNLZX_V1.5.0build1002   | support         | release          | 0.90 |  N
 28 | 回复: ZG项目_V1.2.0版本资源申请     | support         | release          | 0.88 |  N
 29 | 回复: 【资源申请】YYS1.2.4_AHYD    | support         | release          | 0.92 |  N
```

### Intent 分布对比

| intent | regex 分到该类 | LLM 分到该类 |
|--------|--------------|-------------|
| support | 22 | 1 |
| scheduling | 4 | 0 |
| newsletter | 1 | 1 |
| finance | 2 | 0 |
| resource_request | 0 | 12 |
| release | 0 | 9 |
| internal_update | 1 | 5 |
| compliance | 0 | 2 |

### 误判根因

| regex 误判模式 | 原因 | 实际 intent |
|---------------|------|------------|
| `support` 泛滥 | `/问题/` 命中正文中"问题反馈""问题项"等非 support 语境 | resource_request / release |
| `scheduling` 误判 | `/时间|安排/` 命中"上线时间""联调联试" | release |
| `finance` 误判 | `/预算|合同/` 命中"预投项目""执行结果" | internal_update |
| `compliance` 缺失 | regex 无此类别 | 保密考试、出口管制声明 |
| `resource_request` 缺失 | regex 无此类别 | 资源申请、授权申请 |
| `release` 缺失 | regex 无此类别 | 版本发布、联调联试、部署反馈 |

---

## LLM 分类质量评估

LLM 新增的 3 个 intent 类别（`resource_request` / `release` / `compliance`）直接对应该邮箱的核心业务流：

- `resource_request`（40%）：项目资源申请、授权申请、K8s 资源——对应 Phase 4 的 LF1 流
- `release`（30%）：版本发布、联调联试、部署反馈——对应 Phase 4 的 LF2 流
- `compliance`（7%）：保密考试、出口管制——对应 Phase 4 的 LF4 流

这意味着 Phase 4 的 flow 分类（LF1-LF4）可以直接复用 Phase 1 的 LLM intent 结果，不再需要二次 regex。

---

## 后续影响

1. Phase 2 persona 推断现在可以基于真实 intent 分布做推理，而不是基于 regex 误判的分布
2. Phase 4 的 `classifyFlow` 函数可以直接查 Phase 1 intent 结果，省掉重复分类
3. attention-budget 的 noise 标记更准确——regex 把大量正常邮件标为 `support`，LLM 不会

## 已知局限

1. 当前只分类了 30 封 body sample（471 封中的 6.4%），未采样的邮件仍无 intent
2. kimi-k2.5 对中英混合主题的 confidence 略低（0.85-0.88），纯中文主题更稳定（0.92-0.98）
3. batch size=10 时单 batch 耗时约 3-5 秒，全量 471 封约需 47 个 batch ≈ 3 分钟
