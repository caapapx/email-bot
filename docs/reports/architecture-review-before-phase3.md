# 架构审视：人工上下文注入 + Gastown 融合路径

日期：2026-03-18
触发：Phase 3 改造前的全局审视

---

## 一、各阶段人工上下文注入现状

### 框架规定 vs 实际实现

| 阶段 | 框架规定 | 当前实现 | 缺口 |
|------|---------|---------|------|
| Phase 1 | 可忽略人工上下文，只做底层普查 | ✅ 符合 | 无 |
| Phase 2 | 应优先吸收人工上下文（画像、流程、owner、节奏任务） | ❌ 不读取任何人工上下文 | 严重 |
| Phase 3 | 应校正 owner_guess、注入周期性任务、解释项目简称 | ❌ 脚本尚未改造 | 严重 |
| Phase 4 | 应注入周期任务、标记来源为 user_declared_rule | ❌ owner/action 全部硬编码 | 严重 |

### 应该存在但不存在的文件

```
runtime/context/                    ← 目录不存在
├── manual-habits.yaml              ← 周期性职责（每周统计、每月总结）
├── manual-facts.yaml               ← 已确认事实（owner、审批链、SLA）
├── context-pack.json               ← 外部材料提取结果
├── material-manifest.json          ← 材料清单
└── material-extracts/              ← 材料文本提取
```

### 注入方式设计

人工上下文有三种注入时机：

```
1. 初始化注入（Phase 开始前）
   用户提供材料/规则 → 落盘到 runtime/context/ → loading 脚本读取

2. 运行时校正（Phase 执行中）
   LLM 输出低置信结论 → 暂停等待确认 → 用户纠偏 → 更新 manual-facts.yaml

3. 回顾校正（Phase 完成后）
   用户审阅报告 → 发现错误 → 写入 instance-calibration-notes.md → 下次运行读取
```

### 各阶段具体注入点

**Phase 2 — persona 推断**

| 注入内容 | 文件来源 | 注入方式 | 效果 |
|---------|---------|---------|------|
| 用户真实角色 | manual-facts.yaml | loading 时合入 context-pack | 校正 persona hypothesis |
| 组织架构/部门 | manual-facts.yaml | 同上 | 补充 LLM 无法从邮件推断的信息 |
| 周期性职责 | manual-habits.yaml | 同上 | 注入"每周统计""每月总结"等 |
| 术语映射 | manual-facts.yaml | 同上 | 解释 AQ=安全、TG=听谷、FDZ=反诈 |
| 前次校准 | instance-calibration-notes.md | loading 时读取 | 避免重复犯错 |

**Phase 4 — 价值输出**

| 注入内容 | 文件来源 | 注入方式 | 效果 |
|---------|---------|---------|------|
| owner 规则 | manual-facts.yaml | thinking 时作为 system context | 替代硬编码的 owner_guess |
| 固定截止习惯 | manual-habits.yaml | 同上 | "每月5号前总结"进入 sla-risks |
| 周期任务 | manual-habits.yaml | 同上 | "每周统计资源申请"进入 daily-urgent |
| 线程纠偏 | instance-calibration-notes.md | 同上 | "这个线程不是我负责" |

### 脚本改造方案

Phase 2 loading 增加人工上下文读取：

```bash
# phase2_loading.sh 新增逻辑
MANUAL_FACTS="${ROOT_DIR}/runtime/context/manual-facts.yaml"
MANUAL_HABITS="${ROOT_DIR}/runtime/context/manual-habits.yaml"
CALIBRATION="${ROOT_DIR}/docs/validation/instance-calibration-notes.md"

# 如果存在，合入 context-pack.json
# 如果不存在，跳过（不阻塞执行）
```

Phase 2 thinking prompt 增加人工上下文段：

```
## Human-provided context (if available)
- Manual facts: {manual_facts_content}
- Manual habits: {manual_habits_content}
- Previous calibration notes: {calibration_content}

Rules:
1. Human-provided facts override email-only inference
2. Mark evidence source: mail_evidence / user_declared_rule / material_evidence
3. If human context contradicts email evidence, flag the conflict explicitly
```

### OpenClaw 对话模式下的注入

用户在对话中提供的信息（如"这个线程不是我负责"）应该：
1. 立即写入 `manual-facts.yaml`（持久化）
2. 更新当前 Phase 的 context-pack（即时生效）
3. 在报告中标记来源为 `user_confirmed_fact`

### Gastown polecat 模式下的注入

polecat 执行 thinking 任务时：
1. loading 脚本在 sling 前运行，产出 context-pack.json（已含人工上下文）
2. polecat 读取 context-pack.json，不需要额外注入
3. 用户通过 `gt nudge <polecat> "这个线程不是我负责"` 实时校正
4. polecat 收到 nudge 后更新 manual-facts.yaml 并重新评估

---

## 二、Gastown 融合现状与路径

### 当前状态：零 gastown 集成

所有脚本都是手动执行的 shell + node，没有任何 gastown 命令调用。
执行方式：用户在终端手动 `bash scripts/phaseN_loading.sh && bash scripts/phaseN_thinking.sh`。

### 与规划的差距

集成方案规划了 4 个阶段：

| 阶段 | 规划内容 | 当前状态 |
|------|---------|---------|
| 阶段 1 | Loading/Thinking 分离 | ✅ Phase 1, 2 已完成 |
| 阶段 1.5 | Phase 2 LLM 改造 | ✅ 已完成 |
| 阶段 2 | 单 Phase gastown 试跑 | ❌ 未开始 |
| 阶段 3 | 全 Phase 迁移 | ❌ 未开始 |
| 阶段 4 | Witness 集成 | ❌ 未开始 |

### 融合后的形态

**当前形态（手动串行）**

```
用户终端
  └── bash phase1_loading.sh
  └── bash phase1_thinking.sh
  └── bash phase2_loading.sh
  └── bash phase2_thinking.sh
  └── ...
```

**融合后形态（gastown 编排）**

```
gt sling phase1 ──→ rig 自动编排
                     ├── polecat-loader: phase1_loading.sh（自动）
                     ├── polecat-intent-a: phase1_thinking.sh --batch 0-49（自动）
                     ├── polecat-intent-b: phase1_thinking.sh --batch 50-99（自动）
                     └── refinery: 合并 intent 结果（自动）
                            │
                            ▼ 触发下一阶段
gt sling phase2 ──→ rig 自动编排
                     ├── polecat-loader: phase2_loading.sh（自动，含人工上下文）
                     └── polecat-persona: phase2_thinking.sh（自动）
                            │
                            ▼ 可选：暂停等待用户确认
gt nudge polecat-persona "P2 的角色判断正确，但 P5 不对，我不负责保密管理"
                            │
                            ▼ 继续
gt sling phase4 ──→ ...
```

### 改造要点

**1. Formula 定义**

每个 Phase 的 loading + thinking 封装为一个 gastown formula：

```toml
# formulas/phase2.toml
[formula]
name = "phase2-persona-inference"

[steps.loading]
command = "bash scripts/phase2_loading.sh"
outputs = ["runtime/validation/phase-2/context-pack.json"]

[steps.thinking]
command = "bash scripts/phase2_thinking.sh"
depends_on = ["loading"]
outputs = ["runtime/validation/phase-2/persona-hypotheses.yaml"]
```

**2. 阶段间依赖**

```
phase1 (convoy)
  └── done ──→ 触发 phase2 (convoy)
                  └── done ──→ 触发 phase4 (convoy)
```

gastown 的 bead 依赖机制（`bd dep add`）天然支持这种链式触发。

**3. 人工校正的融合**

两种模式：

| 模式 | 触发方式 | gastown 机制 |
|------|---------|-------------|
| 同步校正 | Phase 完成后暂停，等用户确认 | polecat 输出后 hook 到用户 review |
| 异步校正 | 用户随时 nudge 纠偏 | `gt nudge` 发送到活跃 polecat session |

**4. 不需要改造的部分**

- loading 脚本不需要改——它们已经是确定性的 shell 脚本，gastown 直接调用
- thinking 脚本不需要改——polecat 本身就是 Claude session，但当前用 API 调用也兼容
- 输出格式不需要改——YAML/JSON 已经是 refinery 可合并的格式

**5. 需要新增的部分**

- `formulas/` 目录：每个 Phase 的 formula 定义
- `scripts/phase_orchestrator.sh`：可选的本地编排脚本（不用 gastown 时的 fallback）
- `runtime/context/` 初始化脚本：创建目录结构 + 空模板文件

---

## 三、结论

### 在开始 Phase 3 改造前应该做的事

1. **创建 runtime/context/ 骨架** — 空的 manual-facts.yaml 和 manual-habits.yaml 模板
2. **Phase 2 loading 补充人工上下文读取** — 改动小，但对后续所有 Phase 有基础性影响
3. **Phase 3 直接按 loading/thinking + 人工上下文 的完整模式实现** — 不再补课

### Gastown 融合时机

当前阶段不急于接入 gastown。原因：
- loading/thinking 分离已经完成了最关键的架构改造
- 人工上下文注入是比并发更紧迫的缺口
- gastown 融合是"加速"，人工上下文是"正确性"——先保证正确，再加速

建议在 Phase 1-4 全部完成 loading/thinking 改造 + 人工上下文注入后，再统一接入 gastown。
