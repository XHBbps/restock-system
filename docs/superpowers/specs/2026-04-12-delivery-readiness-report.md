# Restock System 云交付就绪度评估报告

> 评估日期：2026-04-11 ~ 2026-04-12
> 评估目标：A+B+C 综合场景 + 公网交付（代码与配置层面）
> 评估方法：5 级 Rubric × 协同审计（方案 B 模块分批 + Opus/Sonnet subagent）
> Spec：`docs/superpowers/specs/2026-04-11-delivery-readiness-scorecard-design.md`

---

## 1. 执行摘要

- **总体得分**：**2.65 / 4**
- **交付门槛判定**：**⚠️ 待补强**
- **唯一阻塞项**：D3 安全性维度均分 **2.13 < 3.0** 硬约束
- **4 汇总组得分**：
  - G1 能不能上线：**2.75** ✅
  - G2 上线后能不能稳：**2.53** ✅
  - G3 坏了能不能救：**2.83** ✅（最高）
  - G4 用着顺不顺：**2.51** ✅
- **审计阶段附带交付的即时修复**（5 项）：
  1. push 端点状态机封闭性（M3，防重复采购单）
  2. Reaper 容器拓扑冗余（M4，消除僵尸回收 SPOF）
  3. 认证业务日志（M6，5 类 structlog 事件）
  4. LoginView 锁定倒计时 + 中文化（M6）
  5. JWT 密钥管理 runbook（M6，~100 行 SOP）
- **测试验证**：后端 163 passed / 前端 vue-tsc + eslint + vitest 全绿

---

## 2. 评分矩阵

| 模块 \ 维度 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | 均分 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| M1 赛狐集成 | 3 | 2 | 2 | 3 | 3 | 3 | 3 | 2 | — | **2.63** |
| M2 补货引擎 | 3 | 3 | 2 | 3 | 3 | 3 | 3 | 2 | — | **2.75** |
| M3 建议单与推送 | 3 | 2 | 2 | 3 | 3 | 3 | 3 | 2 | 2 | **2.56** |
| M4 任务队列 | 3 | 2 | 2 | 3 | 3 | 3 | 3 | 2 | — | **2.63** |
| M5 前端数据页 | 3 | 3 | 2 | 3 | 2 | 3 | 2 | 3 | 3 | **2.67** |
| M6 认证与配置 | 3 | 3 | **3** | 3 | 3 | 3 | 2 | 2 | 2 | **2.67** |
| M7 基础设施 | 3 | 2 | 2 | 3 | 2 | 3 | 3 | 2 | — | **2.50** |
| M8 部署与交付 | — | 3 | 2 | 3 | 2 | 3 | 3 | 2 | — | **2.57** |
| **维度均分** | **3.00** | **2.50** | **2.13** | **3.00** | **2.63** | **3.00** | **2.75** | **2.13** | **2.33** | **2.62** |

**— = N/A（不参与平均分计算）**

### 热力图解读

- 🟢 **全绿列**（D1 / D4 / D6）= 3.00——功能完整性、可部署性、可靠性三个维度**全部模块均达"良好"**
- 🔴 **最弱列**（D3 / D8）= 2.13——安全性和性能/容量是**全项目共性短板**
- 🟡 **最弱行**（M7 基础设施）= 2.50——"为人作嫁"悖论：structlog/BusinessError 基石却自身 D5=2

---

## 3. 4 汇总组详细分析

### G1 能不能上线（2.75）

**主要支撑**：D1=3.00（功能完整）+ D4=3.00（部署就绪）
**主要拖累**：D3=2.13（安全共性缺口）
**改进路径**：D3 是唯一阻塞交付门槛的维度。补齐安全 headers + 速率限制 + CVE 强制化即可推动 G1 突破 3.0。

### G2 上线后能不能稳（2.53）

**主要支撑**：D6=3.00（可靠性全达标）
**主要拖累**：D3=2.13 + D8=2.13（安全 + 性能双低）
**改进路径**：短期补安全（D3），中期加 SLO / 慢查询日志 / 容量评估（D8）。

### G3 坏了能不能救（2.83，最高）

**主要支撑**：D4=3.00 + D6=3.00（deploy 脚本 + 备份恢复完整）
**亮点**：deploy.sh 10 步流程 + trap EXIT 自动回滚 + pg_backup.sh + restore_db.sh + reaper 冗余
**短板**：D5=2.63（日志基础好但无集中收集/告警/metrics）

### G4 用着顺不顺（2.51，最低）

**主要拖累**：D9=2.33（仅 M5=3 真正达标，M3/M6=2）+ D8=2.13
**改进路径**：前端 element-plus 按需引入 + 移动端 @media 断点 + LoginView 已修的中文化/倒计时

---

## 4. 补强行动清单（按优先级）

### 🔴 P0 阻塞（必须在交付前修）

**0 项**。审计前识别的 2 个 P0 候选在审计阶段全部处理：
- P0-1 赛狐 API 出口 IP 不可达 → 用户已 acknowledge，云部署阶段统一解决（白名单或代理）
- P0-5 JWT 轮换文档 → ✅ 已在审计阶段写入 runbook §3.4

### 🟡 P1 强烈建议（在交付前修，按 ROI 排序）

#### 第一优先级：D3 安全性升级（解除交付门槛唯一阻塞）

| # | 动作 | 影响模块 | 工作量 | 效果 |
|:-:|---|---|---|---|
| **1** | **Caddy + nginx 添加安全 headers**（HSTS / X-Frame-Options / CSP / X-Content-Type-Options / Referrer-Policy） | M5/M7/M8 | ~20 行 Caddyfile + ~10 行 nginx.conf | 3 个模块 D3 可从 2 → 3 |
| **2** | **入口级速率限制**——引入 slowapi 或 Caddy `rate_limit` 指令，至少覆盖 `/api/auth/login` 和 `/api/suggestions/*/push` | M1/M3/M6 | ~30 LOC + 配置 | 3 个模块 D3 可从 2 → 3 |
| **3** | **CVE 扫描强制化**——CI `continue-on-error: false` + allowlist 机制 | M8 | ~5 行 CI 配置 | M8 D3 可从 2 → 3 |

**效果预估**：#1 + #2 + #3 全部完成后，至少 6/8 模块 D3 升 3 → D3 均分从 2.13 升到 ≈ 2.75-3.00 → **交付门槛的 D3 ≥ 3.0 硬约束有望达标**。

#### 第二优先级：数据表 TTL 清理

| # | 动作 | 影响模块 | 工作量 |
|:-:|---|---|---|
| **4** | **daily_archive job 新增三表 30 天清理**（api_call_log + task_run + login_attempt） | M1/M4/M6 | ~15 LOC + 1 测试 |

#### 第三优先级：测试覆盖 + 代码健壮性

| # | 动作 | 影响模块 | 工作量 |
|:-:|---|---|---|
| **5** | **M4 worker/reaper 核心路径单测**（SKIP LOCKED / heartbeat / dedupe / reaper） | M4 | ~200 LOC 测试 |
| **6** | **M1 SaihuClient/TokenManager mock 单测**（retry / token refresh / 分页） | M1 | ~150 LOC 测试 |
| **7** | **M4 split-brain 守护**（_mark_success 加 `WHERE status='running'`）+ 时钟源统一（`func.now()`） | M4 | ~15 LOC |
| **8** | **M7 5xx JSON 化**（全局 Exception handler 返回 JSON 而非纯文本） | M7 | ~10 LOC + 1 测试 |

#### 第四优先级：文档 + 可观测性

| # | 动作 | 影响模块 | 工作量 |
|:-:|---|---|---|
| **9** | **M5 element-plus 按需引入**（用户已立项） | M5 | 中等（unplugin 配置）|
| **10** | **M4 /api/monitor/tasks 聚合端点** | M4 | ~30 LOC |
| **11** | **M2 JSONB 快照 DB 不可变约束**（trigger 或 ORM __setattr__） | M2 | ~20 LOC |
| **12** | **M8 备份加密**（OSS 服务端加密 or pg_dump + gpg） | M8 | 运维配置 |

### 🟢 P2 可延后（不阻塞交付，列入技术债清单）

共 ~30 项，按类别归纳：

| 类别 | 代表性条目 | 模块 |
|---|---|---|
| **Dead code / dead config** | `error` 状态清理（M3）/ `PUSH_MAX_ITEMS_PER_BATCH` 删除（M3）/ snapshot nullable→NOT NULL（M2） | M2/M3 |
| **ADR 欠缺** | 全项目 6+ 核心设计决策无 ADR（JWT vs session / localStorage vs HttpOnly / Celery vs TaskRun / Caddy vs Nginx / 单用户 sub=owner...） | M4/M5/M6/M8 |
| **validate_settings 缺口** | 引擎参数 / push 重试次数 / worker poll interval / reaper interval / login 阈值 缺校验 | M2/M3/M4/M6 |
| **前端清洁度** | ZipcodeRuleView 1276 行拆分 / legacy redirect 清理 / LoginView 移动端 @media | M5/M6 |
| **可观测性增强** | a11y / i18n / Lighthouse CI / 连接池监控 / Sentry 前端错误上报 | M5/M7 |
| **部署增强** | 蓝绿部署 / IaC / 多环境 / CD tag 自动触发 / CPU limit / restore_db.sh 错误处理 | M8 |

---

## 5. 审计阶段附带交付的即时修复清单

审计过程中用户授权的即时修复（已 commit + 测试通过）：

| # | 修复内容 | 模块 | Commit |
|:-:|---|---|---|
| 1 | push 端点拒绝对 archived/pushed 建议单推送（防重复采购单） | M3 | `1f01122` |
| 2 | Reaper 冗余到 scheduler 容器（消除僵尸回收 SPOF） | M4 | `0ab9a13`（随 zipcode refactor） |
| 3 | auth.py 5 类 structlog 业务事件日志 + XFF 依赖注释 | M6 | `367cf7f` |
| 4 | LoginView 中文化 + 锁定倒计时消费 `locked_until` | M6 | `367cf7f` |
| 5 | runbook §3.4 JWT 密钥管理（首次生成/轮换/泄漏应急 ~100 行 SOP） | M6 | `367cf7f` |

**总影响**：
- M3 P1 从 3 → 0；P0-2 候选从"⚠️ 部分实现"升级为"✅ 已实现"
- M4 P1 从 6 → 4（拓扑隐患消除）
- M6 P0 从 1 → 0（JWT 轮换文档补齐）；P1 从 7 → 3；D5 从 2 → 3
- 后端测试从 140 → 163 passed（+23，含新增 + 并行工作贡献）

---

## 6. D3 安全性升级建议（交付门槛解锁路径）

### 当前状况

D3 均分 2.13 是**唯一阻塞"达标"的维度**（硬约束 ≥ 3.0）。8 个模块中只有 M6=3（认证核心），其余全 2。

### 共性 2 分原因（所有 ≤ 2 的模块都因为这些）

1. ❌ **无安全 headers**——Caddy 和 nginx 都没有 CSP / X-Frame-Options / HSTS / X-Content-Type-Options
2. ❌ **无入口级速率限制**——登录和推送端点可被无限轰炸
3. ❌ **无 CVE 扫描强制化**——CI 有 audit 但 `continue-on-error: true`

### 推荐：3 步升级路径

**Step 1（最高 ROI，~30 分钟）**：Caddy + nginx 安全 headers

```
# deploy/Caddyfile 追加到 handle 块之前:
header {
    Strict-Transport-Security "max-age=31536000; includeSubDomains"
    X-Frame-Options "DENY"
    X-Content-Type-Options "nosniff"
    Referrer-Policy "strict-origin-when-cross-origin"
    Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    Permissions-Policy "camera=(), microphone=(), geolocation=()"
}
```

```
# frontend/nginx.conf 追加:
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

**Step 2（~1 小时）**：入口级速率限制

推荐方案：Caddy 的 `rate_limit` 指令（比 slowapi 更简洁，不污染后端代码）

```
# deploy/Caddyfile /api/* handle 中加:
rate_limit {remote_host} 30r/m  # 每 IP 每分钟 30 个请求
```

或更精细：对 `/api/auth/login` 单独限 `5r/m`。

**Step 3（~15 分钟）**：CVE 扫描强制化

`.github/workflows/ci.yml` 中 `continue-on-error: true` → `false` + 配置 allowlist 文件排除已知误报。

### 效果预估

3 步全部完成后：
- M1/M2/M3/M4/M5/M7/M8 的 D3 均可从 2 → 3（前提是无模块独有安全缺口阻塞）
- M6 已经是 3
- **D3 维度均分从 2.13 → ≈ 3.00**
- **交付门槛判定从 ⚠️ 待补强 → ✅ 达标**

---

## 7. 重新评估建议

完成 P1 第一优先级（D3 安全三步升级）后，建议重跑以下范围：

- **必须重测**：D3 维度（全 8 模块）—— 重新评估安全 headers / 速率限制 / CVE 扫描到位后的分数
- **必须重测**：G1 能不能上线 —— D3 升级后 G1 预计从 2.75 → ≈ 3.0
- **可保留原分数**：D1/D4/D6（全 3.00，无改动依据）、D9（UX 无改动）

---

## 8. 范围声明

本评估仅覆盖代码与配置层面就绪度，不包括：
- 服务器规格、操作系统版本、Docker 版本兼容性
- 网络拓扑、防火墙规则、DNS 解析
- 域名注册、TLS 证书签发可达性（注：Caddy 自动签证书机制已评估✅）
- 第三方服务可达性（赛狐 API 连通性）
- 业务正确性、法律合规、商业风险

完成 P0/P1 后部署到云服务器时，仍需补充：
- 服务器 ≥ 4G RAM 验证（6 服务合计 ~3G limit）
- 防火墙入站规则（仅 80/443，禁止 5432/8000 等）
- 域名 DNS 配置（Caddy 自动 TLS 前置）
- 出口 IP 与赛狐白名单协调

---

## 相关文档

- **Spec**：[评分卡设计 spec](2026-04-11-delivery-readiness-scorecard-design.md)
- **聚合计算**：[docs/superpowers/scorecard/_aggregate.md](../scorecard/_aggregate.md)
- **各模块详细报告**：
  - [M1 赛狐集成](../scorecard/M1-saihu-integration.md)
  - [M2 补货引擎](../scorecard/M2-engine.md)
  - [M3 建议单与推送](../scorecard/M3-suggestions-pushback.md)
  - [M4 任务队列](../scorecard/M4-task-queue.md)
  - [M5 前端数据页](../scorecard/M5-frontend.md)
  - [M6 认证与配置](../scorecard/M6-auth-config.md)
  - [M7 基础设施](../scorecard/M7-infrastructure.md)
  - [M8 部署与交付](../scorecard/M8-deployment.md)
- **标尺一致性记录**：[docs/superpowers/scorecard/_calibration.md](../scorecard/_calibration.md)
