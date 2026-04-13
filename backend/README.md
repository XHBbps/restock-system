# Restock Backend

赛狐补货计算工具后端。Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / PostgreSQL 16。

## 本地开发

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"

# 安装 pre-commit 钩子
pre-commit install

# 启动本地数据库（需要已启动 deploy/docker-compose.yml 的 db 服务）
# 或独立启动
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16-alpine

# 拷贝环境变量
cp .env.example .env
# 编辑 .env 设置 DATABASE_URL 等

# 执行迁移
alembic upgrade head

# 启动
uvicorn app.main:app --reload
```

访问 http://localhost:8000/docs 查看 API。

## 代码质量

```bash
ruff check .      # lint
black .           # format
mypy app          # type check
pytest            # test
```

宪法 NON-NEGOTIABLE：每次提交必须通过所有检查。pre-commit 钩子会自动执行。
