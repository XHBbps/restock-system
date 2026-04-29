# CodeRabbit Review 分组记录

> 记录时间：2026-04-29
> 用途：记录为 CodeRabbit review 临时拆分的审查范围，便于后续复盘、补查或继续按组提交 review。

## 分组详情

| 组别 | 审查范围 | 已排除范围 | 说明 |
|---|---|---|---|
| 第 2 组 | 后端测试 + Alembic 迁移 | `backend/tests/unit/test_sign.py` | 后端测试文件与数据库迁移相关内容；签名单测已单独处理凭据 fixture，不纳入本组 review。 |
| 第 3 组 | `frontend/src` | 无 | 前端源码主目录，包含 views、components、stores、api、utils、tests 等前端实现代码。 |
| 第 4 组 | 前端外围配置 | 无 | 前端源码目录之外的配置与工程文件，例如 Vite、TypeScript、ESLint、Vitest、package 配置等。 |
| 第 5 组 | 部署 / 文档 / 配置 | `docs/saihu_api` | 部署脚本、Docker/Caddy 配置、项目文档与通用配置；赛狐 API 外部参考资料目录不纳入本组 review。 |

## 备注

- 本文仅记录当前明确给出的第 2-5 组；第 1 组未在本次上下文中提供，暂不补写。
- 这些分组是 review 组织方式，不代表代码模块边界或长期架构分层。
- 若后续继续使用这些分组，应以实际变更文件为准，必要时重新排除已单独审查过的敏感或外部资料目录。
