# Phase 4 价值输出改造记录

## TL;DR

将 Phase 4 从硬编码 regex 打分改为 LLM 推断（astron-code-latest）。
LLM 输出 5 条 daily-urgent、3 条 pending-replies、4 条 sla-risks，每条带具体证据和 action hint。

---

## 变更概要

| 项目 | 内容 |
|------|------|
| 日期 | 2026-03-19 |
| 变更类型 | refactor / enhancement |
| 新增脚本 | `scripts/phase4_loading.sh`, `scripts/phase4_thinking.sh` |
| 保留脚本 | `scripts/phase4_daily_value_outputs.sh`（fallback） |
| LLM 后端 | astron-code-latest (OpenAI-compatible) |
| 人工上下文 | 支持 manual-facts / manual-habits / calibration notes |

---

## 改造前后对比

### 旧版（硬编码）

```javascript
// urgency 打分
if (dueSoon) urgencyScore += 30;
if (isWaitingOnMe) urgencyScore += 25;
// owner 判断
if (/工时填报提醒/.test(threadKey)) ownerGuess = '邮箱主人';
// why 生成
if (/资源申请/.test(threadKey)) why = '资源申请线程，需跟进审批进度';
```

### 新版（LLM）

```yaml
- thread_key: "工时填报提醒"
  urgency_score: 95
  why: "工时填报逾期将直接影响当月考核结果，当前已填未审核工时16小时"
  action_hint: "立即登录OA系统完成工时填报并跟进审批流程"
  owner: "zjma12@kxdigit.com"
  evidence_source: mail_evidence
```

关键差异：
- 旧版 why 是模板字符串，新版从邮件正文提取具体数字（"16小时"）
- 旧版 owner 是硬编码映射，新版从邮件上下文推断
- 旧版 urgency 是加权打分，新版是 LLM 综合评估
- 新版 sla_risks 能识别 deployment_failure 类型（"非一次成功"），旧版只能识别 stalled

---

## LLM 输出摘要

| 输出 | 数量 | 示例 |
|------|------|------|
| daily_urgent | 5 | 工时填报(95)、江苏AQ-DSJ部署失败(85)、ZG部署失败(80) |
| pending_replies | 3 | 冷泉资源申请待审批、联调联试待确认 |
| sla_risks | 4 | 2个 deployment_failure、2个 stalled |
| weekly_brief | 1 | 30 threads, 4 flow summary, 3 top actions |
