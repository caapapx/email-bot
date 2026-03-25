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
| 新增日期 | 2026-03-25 |
| 新增内容 | 实现 recipient_role 全链路降权与 [CC]/[GRP] 视觉标注 |
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

---

## 2026-03-25 Recipient Role 降权改造详情

### 背景
针对“我是收件人（To）”和“我是被抄送对象（Cc/Group）”的邮件在重要程度上存在显著差异，系统需要对此进行全链路区分。

### 核心实现
1. **数据源层**：通过移除 `himalaya` 的 `--no-headers` 参数，在 body 中保留 MIME headers。
2. **推断层**：在 Phase 1/3 中增加 `recipient_role` 信号：
   - `direct`: 显式在 To
   - `cc_only`: 显式只在 Cc
   - `group_only`: 不在 To/Cc，但在收件列表中（邮件组）
   - `indirect`: 混合 Cc 与 Group
3. **降权策略**：
   - `cc_only` / `indirect`: 乘数 0.6
   - `group_only`: 乘数 0.4
   - `direct` / `unknown`: 乘数 1.0
4. **视觉标注**：
   - `[CC]`: 对应 `cc_only` / `indirect`
   - `[GRP]`: 对应 `group_only`
5. **调度增强**：`daytime-sync` 任务扩展覆盖至 Phase 4，实现日内秒级可见的降权反馈。
