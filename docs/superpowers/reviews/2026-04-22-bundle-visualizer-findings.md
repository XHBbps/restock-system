# Bundle Visualizer Findings — 2026-04-22

> 一次性 `rollup-plugin-visualizer` 调研，关闭 audit P2-D3。运行方式：临时 `npm install --no-save rollup-plugin-visualizer` + `npm run build` 生成 `dist/stats.html`。visualizer 不入 package.json，本文档是唯一持久产物。

## 执行概要

| chunk | renderedLength (rollup) | on-disk minified | on-disk gzip |
|---|---|---|---|
| element-plus | 1,885 KB | 886 KB | 294 KB |
| charts | 1,468 KB | 545 KB | 189 KB |
| framework | 314 KB | ~125 KB | ~47 KB |
| index | 129 KB | ~55 KB | ~21 KB |

数据来自 rollup-plugin-visualizer v5 (`version: 2` schema)，`nodeParts` 包含每个模块的 `renderedLength` / `gzipLength` / `brotliLength`，各 chunk 数值为所有模块求和。表内 "renderedLength (rollup)" 列是 rollup 渲染后、terser 压缩前的源字节数；"on-disk minified" 是 `vite build` 产物 `dist/assets/*.js` 的实际磁盘大小（经 terser 压缩）。两者相差约 2-3 倍；传输用 on-disk gzip/brotli 对更能反映用户真实下载量。

## element-plus 分析（1,885 KB 最小化后）

- 模块数量：1,577 个（807 个来自 `element-plus/es/components/*`，覆盖 91 个组件）
- Top 5 modules（按 renderedLength）：
  1. `async-validator/dist-web/index.js` — 34 KB（gzip 7 KB）
  2. `element-plus/es/components/date-picker-panel/…/panel-date-range.vue_…_lang.mjs` — 30 KB（gzip 4 KB）
  3. `@element-plus/icons-vue/dist/index.js` — 29 KB（gzip 5 KB）
  4. `@floating-ui/dom/dist/floating-ui.dom.mjs` — 24 KB（gzip 6 KB）
  5. `element-plus/es/components/date-picker-panel/…/panel-date-pick.vue_…_lang.mjs` — 24 KB（gzip 5 KB）
- Tree-shake 漏项判断：**无明显漏项**。chunk 由 807 个 `es/components/` 细粒度 `.mjs` 文件构成，无单一大型 `packages/index.js` 入口，说明 `ElementPlusResolver` 按需导入已生效。
- `@element-plus/icons-vue/dist/index.js`（29 KB minified）是整包入口——若项目只使用少量图标（≤10 个），可改用 `import { IconName } from '@element-plus/icons-vue'` 按名导入来获得 tree-shake 收益；当前 29 KB gzip 5 KB 代价可接受。
- 最大单模块 `async-validator`（表单校验器，34 KB）无法进一步拆分，是 el-form 的必要依赖。
- 建议动作：**保持现状**；若未来需要显著减包，优先考虑懒加载 DatePicker 相关路由（节约 ~54 KB 最小化后）。

## charts (echarts + vue-echarts) 分析（1,468 KB 最小化后）

- 模块数量：577 个（echarts/lib/* 484 个，zrender/lib/* 92 个，vue-echarts/* 1 个）
- Top 5 modules（按 renderedLength）：
  1. `echarts/lib/core/echarts.js` — 60 KB（gzip 12 KB）
  2. `echarts/lib/chart/line/LineView.js` — 33 KB（gzip 7 KB）
  3. `echarts/lib/component/tooltip/TooltipView.js` — 31 KB（gzip 7 KB）
  4. `zrender/lib/Element.js` — 31 KB（gzip 6 KB）
  5. `echarts/lib/component/axis/AxisBuilder.js` — 30 KB（gzip 7 KB）
- 实际使用的 chart 类型（有非零字节）：**line、bar、pie** 及其 helper。
- 20 余个 chart 类型（gauge、funnel、sankey、map、treemap、graph、radar 等）虽在依赖图中出现，但 **renderedLength 全为 0**——rollup tree-shaking 已将其置空，不占实际包体积。
- 未检测到 `echarts/index.js`（全量入口）被打入，各模块均来自 `echarts/lib/` 细粒度路径，说明 `echarts/core` + 按需注册已生效（或 vue-echarts 自身已做 tree-shake）。
- 建议动作：**保持现状**。echarts 的 tree-shaking 效果已相当理想；1,468 KB → gzip 385 KB 在同类图表库中属正常水位。如需进一步压缩，可评估是否能移除 tooltip/legend 等组件，但对 UX 影响较大，不建议优先处理。

## framework 分析（314 KB 最小化后）

- 构成（top 5）：
  1. `@vue/runtime-core/dist/runtime-core.esm-bundler.js` — 142 KB
  2. `@vue/reactivity/dist/reactivity.esm-bundler.js` — 44 KB
  3. `vue-router/dist/vue-router.mjs` — 43 KB
  4. `@vue/runtime-dom/dist/runtime-dom.esm-bundler.js` — 33 KB
  5. `vue-router/dist/devtools-EWN81iOl.mjs` — 14 KB（devtools hook，生产构建理应排除）
  6. `pinia/dist/pinia.mjs` — 10 KB
  7. `@vue/shared/dist/shared.esm-bundler.js` — 7 KB
  8. `lucide-vue-next/dist/esm/icons/*.js` — 各 ≤1 KB（按需导入的图标）
- 是否正常：**是**。vue-router devtools 模块（14 KB）在正式 production build 中应被 `NODE_ENV=production` 条件编译移除，但当前仍出现。可检查 vite 的 `mode` 配置是否为 `production`，如是则这部分字节在生产环境实际不会执行（dead code elimination 未完全消除）。不属于紧急问题。

## index 分析（129 KB 最小化后）

- 构成（top 10）：
  1. `axios/lib/utils.js` — 22 KB
  2. `axios/lib/core/AxiosHeaders.js` — 8 KB
  3. `axios/lib/adapters/fetch.js` — 8 KB
  4. `axios/lib/core/Axios.js` — 7 KB
  5. `axios/lib/adapters/xhr.js` — 6 KB
  6. `axios/lib/helpers/toFormData.js` — 6 KB
  7. `src/config/appPages.ts` — 6 KB（路由页面配置，体积合理）
  8. `src/router/index.ts` — 5 KB
  9. `axios/lib/defaults/index.js` — 4 KB
  10. `src/stores/auth.ts` — 2 KB
- 是否意外含大依赖：**否**。index chunk 主要由 axios（~65 KB）和项目路由/配置代码组成，无意外引入的大型第三方库。

## 总结与行动项

- [ ] element-plus tree-shake 机会：**无需跟进**——按需导入已正确配置，91 个组件细粒度打包，无 wholesale import 问题。若后续 1,885 KB 仍是痛点，可评估 `@element-plus/icons-vue` 按名 import（潜在节省 ~24 KB minified）。
- [ ] echarts 精简机会：**无需跟进**——tree-shaking 已生效，仅 line/bar/pie 有实际字节，20+ 其他 chart 类型均为零字节占用。
- [ ] vue-router devtools chunk（14 KB）：低优先级，可通过确认 `build.mode=production` 或 rollup tree-shake 条件消除，影响较小。
- [ ] 最大发现：**element-plus on-disk 为 886 KB minified / 294 KB gzip**（与 `npm run build` 日志一致）；visualizer 的 renderedLength 1,885 KB 是 terser 压缩前的源字节数，不影响用户下载体积但能看清模块构成。全站传输量（gzip）约 **551 KB**，对内部工具（1-5 用户）完全可接受，无需立即优化。
- [x] P2-D3 收口：本调研到此结束，visualizer 不入 deps

## 附：复现步骤

```bash
cd frontend
npm install --no-save rollup-plugin-visualizer
# 在 vite.config.ts 临时加:
#   import { visualizer } from 'rollup-plugin-visualizer'
#   plugins: [..., visualizer({ filename: 'dist/stats.html', gzipSize: true, brotliSize: true, template: 'treemap' })]
npm run build
# 看完 dist/stats.html 后：
git checkout frontend/vite.config.ts
npm uninstall rollup-plugin-visualizer  # 若 --no-save 装过就无需这步
rm -f dist/stats.html
```
