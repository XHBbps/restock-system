"""FastAPI 应用入口（Phase 1 骨架）。

Phase 2 将补充：
- lifespan 管理 Scheduler + Worker + Reaper 启动/停止
- 结构化日志中间件
- 全局异常处理
- 路由注册
"""

from fastapi import FastAPI

app = FastAPI(
    title="赛狐补货计算工具",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """健康检查（Docker HEALTHCHECK + Caddy 探活）。"""
    return {"status": "ok"}
