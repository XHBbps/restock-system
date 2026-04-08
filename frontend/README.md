# Restock Frontend

赛狐补货计算工具前端。Vue 3 + Element Plus + Pinia + Vite。

## 本地开发

```bash
npm install
npm run dev  # http://localhost:5173
```

开发服务器会自动将 `/api/*` 代理到 `http://localhost:8000`。

## 常用命令

```bash
npm run lint         # ESLint
npm run type-check   # vue-tsc
npm run format       # Prettier
npm run test         # Vitest
npm run build        # 生产构建
```

## 设计风格

参考 spec.md 的 "Frontend Design Direction" 章节。设计 tokens 定义在 `src/styles/tokens.scss`。
