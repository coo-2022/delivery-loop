# Delivery Loop 初始设计

状态：初始方案  
目标仓库：`coo-2022/delivery-loop`  
日期：2026-07-16

## 1. 背景

我们希望搭建一套通用的软件交付流水线：用户在页面或 GitHub Issue Form 提交需求，系统按照优先级从需求池中取任务，分配给可替换的 coding agent。agent 先输出方案，经过人工审核后才允许写代码；代码完成并验证通过后提交 PR；PR 经过人工 review 合入后，agent 释放并处理下一个需求。发布版本仍由人工确认，自动化负责 tag、build、release 和状态回写。

这套系统本身不应该耦合 OpenEarth。它应该是一个独立的 GitHub-driven delivery orchestrator，可以管理 OpenEarth，也可以管理其他仓库。

## 2. 业界现状

当前业界已经有很多相近部件，但缺少一个完全等价的通用控制器。

### 2.1 GitHub Copilot coding agent

GitHub Copilot coding agent 是最接近的商业形态：用户可以把 issue 或任务交给 Copilot，它在云端环境中 clone 仓库、修改代码、保存过程日志、生成 PR，并在完成后请求人 review。开发者可以在 PR 或评论中继续要求修改。

它证明了 `issue -> agent -> PR -> human review` 是主流方向。

局限：

- 绑定 GitHub Copilot 和 GitHub 的产品形态。
- 不强调“方案先审，再实现”的两阶段门禁。
- 不提供通用多 agent 调度控制面。
- 不面向自定义 benchmark / release governance。

### 2.2 Jules / Codex / Claude Code / Devin

Google Jules、OpenAI Codex、Claude Code、Devin 等更像异步 coding agent。它们解决“agent 如何执行开发任务”：读代码、改代码、跑测试、开 PR 或辅助 review。

局限：

- 多数不是需求池调度系统。
- 通常不管理多个 agent backend。
- 不天然提供统一的需求排序、lease、审核状态机和发布节奏治理。

### 2.3 GitHub Actions / Projects / Issues

GitHub 原生能力可以承担事实源和协作层：

- Issues：需求入口和讨论记录。
- Labels / Projects：状态和优先级。
- Pull Requests：代码审核门禁。
- Checks / Actions：自动验证门禁。
- Releases：版本发布。

局限：GitHub 原生 workflow 不负责 agent 调度和任务执行。

### 2.4 研究原型

已有研究原型把 GitHub issue resolution 拆成多 agent 协作，例如 planner、reproducer、coder、tester、failure analyst、PR agent，并由 GitHub label/webhook 状态机驱动。这类系统说明 label/webhook + 多 agent + safety gate 是合理架构。

局限：多数是研究系统，不是通用产品化控制器。

## 3. 定位

Delivery Loop 是一个通用控制面，不是单个 coding agent。

```text
GitHub Issues / Projects = 需求事实源
Delivery Loop = 调度器和状态机
Codex / Claude / opencode / Copilot / Devin = 可替换执行 agent
GitHub PR / CI = 代码门禁
Release workflow = 发布门禁
Benchmark = 防失控门禁
```

核心原则：

- 不绑定某个 coding agent。
- 不绑定某个业务项目。
- GitHub 是事实源，Delivery Loop 是 worker。
- 人工审核阶段产物，而不是人工操作每个细节。
- 方案审核通过前不能写代码。
- PR review 通过前不能合入。
- 发布确认前不能 tag / release。
- benchmark 是发布门禁，不只是测试脚本。

## 4. GitHub 访问模型

独立仓库 `delivery-loop` 可以访问并管理其他仓库的 issue 和 PR。

### 4.1 公共仓库

如果目标仓库是 public：

- 读取 issues 可以不用 token，但会受 GitHub API rate limit 限制。
- 写评论、打 label、创建分支、开 PR、读取 checks 需要 token 或 GitHub App。

### 4.2 私有仓库

如果目标仓库是 private：

- 必须通过 GitHub App 或 PAT 授权。
- 推荐 GitHub App，不推荐长期使用个人 PAT。

### 4.3 推荐权限

GitHub App 权限：

```text
Metadata: read
Issues: read/write
Pull requests: read/write
Contents: read/write
Checks: read
Actions: read
Projects: read/write, optional
Releases: read/write, optional
```

原则：按仓库授权，按能力最小化授权。

## 5. 多仓库配置

Delivery Loop 可以管理多个目标仓库。

```yaml
repos:
  - owner: coo-2022
    name: OpenEarth
    default_branch: main
    labels:
      intake: request:new
      planned: request:planned
      design_review: design:review
      design_approved: design:approved
      agent_claimed: agent:claimed
      pr_review: pr:review
      release_candidate: release:candidate
  - owner: coo-2022
    name: another-project
    default_branch: main
```

## 6. 状态机

需求状态主要通过 GitHub labels 和 comments 表达。

```text
request:new
request:triaged
request:planned

design:in-progress
design:review
design:changes-requested
design:approved

impl:in-progress
impl:blocked

pr:open
pr:review
pr:changes-requested
pr:approved
pr:merged

release:candidate
release:approved
release:released
```

推荐状态流：

```text
用户提交 issue
  -> request:new
  -> triage / priority
  -> request:planned
  -> agent claimed
  -> design proposal
  -> design:review
  -> human approval
  -> design:approved
  -> implementation branch
  -> tests + benchmark
  -> PR
  -> human PR review
  -> merge
  -> release candidate
  -> release approval
  -> release
```

## 7. 人工门禁

### 7.1 方案审核

agent 接到需求后，第一阶段只允许输出方案，不允许改代码。

方案必须包含：

- 问题理解
- 影响范围
- 架构修改
- 文件/模块影响
- 风险
- 验收标准
- 测试计划
- 版本影响

通过方式：人工添加 `design:approved` label，或在 issue comment 中使用明确命令。

示例：

```text
/delivery approve-design
```

不通过方式：人工评论修改意见，并保持或添加 `design:changes-requested`。

### 7.2 PR 审核

实现完成并通过自动验证后，agent 创建 PR。

PR review 不通过：

- 保留 agent lease。
- 读取 review comment。
- 重新调度同一 agent 或兼容 agent 修改。

PR review 通过：

- 满足 branch protection 和 checks 后允许合入。
- 合入后释放 agent。

### 7.3 发布审核

合入 main 不等于发布。

发布候选需要：

- 自动生成 release notes。
- 自动给出版本建议。
- 自动汇总变更 issues 和 PRs。
- 自动跑 release gate。
- 人工确认 `release:approved` 后才 tag/build/release。

## 8. Agent Pool

Delivery Loop 不内置某个 agent，而是维护可替换 agent backend。

```yaml
agents:
  - name: codex-local
    type: command
    command: codex exec --repo {repo_dir}
    capabilities: [design, implement, revise]
  - name: claude-code
    type: command
    command: claude --print
    capabilities: [design, implement, revise]
  - name: opencode
    type: command
    command: opencode run --dir {repo_dir}
    capabilities: [design, implement]
```

Agent 状态：

```text
idle
claimed
running
blocked
failed
```

## 9. Lease 机制

为了避免多个 loop 抢同一个需求，需要 lease。

最小实现：

- 添加 `agent:claimed` label。
- 在 issue 下写入结构化 comment。

```json
{
  "schema": "delivery.lease.v1",
  "issue": "coo-2022/OpenEarth#123",
  "agent": "codex-local",
  "stage": "designing",
  "lease_id": "...",
  "claimed_at": "2026-07-16T10:00:00Z",
  "expires_at": "2026-07-16T11:00:00Z"
}
```

lease 过期后：

- loop 可以重新领取。
- 原 agent 的后续写回必须检查 lease_id，避免过期写回污染状态。

## 10. 调度策略

P0 调度先用确定性规则，不直接让 LLM 决定优先级。

```text
score = priority_weight
      + severity_weight
      + user_impact_weight
      + strategic_weight
      + stale_bonus
      - risk_penalty
      - size_penalty
```

排序输入：

- priority labels: `priority:P0-P3`
- request type: bug / feature / docs / benchmark / release
- affected domain
- blocked users
- age / stale time
- linked incidents
- milestone / release target

LLM 可以辅助归一化需求，但不能单独决定最终优先级。

## 11. Benchmark 门禁

Delivery Loop 需要一套 system-level benchmark，防止自进化交付系统失控。

第一批 benchmark：

1. 新需求不能绕过方案审核直接写代码。
2. 未获得 `design:approved` 不能创建实现 PR。
3. CI 失败不能进入 merge-ready。
4. PR review 未批准不能进入 merged。
5. 未获得 `release:approved` 不能 tag / release。
6. agent lease 过期后不能继续写回状态。
7. agent 不能直接 push main。
8. issue 缺少验收标准时必须先要求补充信息或生成待审核方案假设。
9. P0/P1 bug 修复必须新增回归 benchmark。
10. release notes 必须和实际 merged PRs 一致。

## 12. 页面与入口

GitHub Pages 可以作为展示页面，但不应该把 token 放到前端。

P0 推荐：

- 页面展示 release cadence、需求池、阶段看板、流程说明。
- 新需求按钮跳转 GitHub Issue Form。
- GitHub Issue Form 创建真实 issue。

P1 可选：

- GitHub App + backend API 支持完全自定义表单。
- Pages 调 backend，由 backend 创建 issue。

## 13. P0 范围

P0 目标是可跑通一个仓库的本地闭环。

包含：

- GitHub Issue 读取。
- label-based 状态机。
- priority 排序。
- agent lease。
- design proposal 生成和写回 issue comment。
- 等待 `design:approved`。
- 调用外部 agent command 实现。
- 本地测试命令执行。
- 创建 PR。
- PR review comment 触发 revise。
- PR merged 后释放 agent。

不包含：

- 自动发布。
- 多租户 dashboard。
- 复杂 Project fields。
- 云端 worker 编排。
- 私有 GitHub App 安装界面。

## 14. P1/P2

P1：

- GitHub App 模式。
- Webhook 触发，而不是纯 polling。
- 多仓库配置。
- 多 agent pool。
- Dashboard 状态实时刷新。
- Release candidate 和人工发布确认。

P2：

- 组织级需求聚类和去重。
- 自动生成版本计划。
- benchmark 演进策略。
- agent 成本、成功率、耗时统计。
- 自动选择最合适 agent。
- 和 Linear/Jira 双向同步。

## 15. 推荐技术路线

第一版用 Python 实现，原因：

- 容易调用本地 Codex/Claude/opencode。
- 容易写 CLI 和 daemon。
- GitHub API 可先通过 `gh` CLI，后续换 PyGithub / GitHub App SDK。
- benchmark 和测试生态成熟。

建议目录：

```text
delivery-loop/
  README.md
  docs/
    initial-design.md
  delivery_loop/
    cli.py
    github.py
    scheduler.py
    leases.py
    agents/
      command.py
    workflows/
      design.py
      implement.py
      release.py
  tests/
    test_scheduler.py
    test_leases.py
    test_state_machine.py
  pyproject.toml
```

## 16. 初始命令草案

```bash
delivery-loop init
delivery-loop repo add coo-2022/OpenEarth
delivery-loop issues list
delivery-loop tick --once
delivery-loop run --interval 60
delivery-loop agent list
delivery-loop lease list
```

## 17. 关键开放问题

- P0 是否只支持 `gh` CLI，还是直接上 GitHub App？
- agent 输出方案是否只写 issue comment，还是也落本地 run artifact？
- 是否要求所有需求都进入 GitHub Project？
- release cadence 是每个被管理仓库配置，还是 delivery-loop 全局配置？
- benchmark 是目标仓库自己提供，还是 delivery-loop 也维护系统 benchmark？

## 18. 结论

Delivery Loop 应该作为独立项目存在。它不是 OpenEarth 的一个子模块，而是一个通用软件交付控制器。

OpenEarth 可以作为第一个 dogfood 目标仓库：

```text
delivery-loop 管理 coo-2022/OpenEarth issues / PRs / releases
OpenEarth 自己继续专注五域 Experience 和自进化 agent 系统
```

这个边界可以避免 OpenEarth 被交付平台逻辑污染，也让 Delivery Loop 未来可以服务任意 GitHub 项目。
