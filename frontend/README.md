# Restock Frontend

赛狐补货计算工具前端。Vue 3 + Element Plus + Pinia + Vite。

## 本地开发

```bash
npm install
npm run dev  # http://localhost:5173
```

开发服务器默认会自动将 `/api/*` 代理到 `http://localhost:8000`。

如果本机 `8000` 端口被占用，可在 `frontend/.env` 中覆盖代理目标：

```bash
VITE_API_PROXY_TARGET=http://localhost:8001
```

## 常用命令

```bash
npm run lint         # ESLint
npm run type-check   # vue-tsc
npm run format       # Prettier
npm run test         # Vitest
npm run build        # 生产构建
```

## 设计风格

参考项目文档入口 `../docs/onboarding.md` 与 `../docs/Project_Architecture_Blueprint.md`。设计 tokens 定义在 `src/styles/tokens.scss`。
