# Frontend UX Improvements Design

## Overview

Five targeted UX improvements to the restock_system frontend (Vue 3 + Element Plus). All changes follow the existing逐页修改 approach (方案 A) — no new abstractions or wrapper components.

Project context: 1-5 internal users, no need for over-engineering.

---

## 1. Table Tooltip on Overflow

**Goal**: Truncated cell text shows full content on hover.

**Approach**: Add `show-overflow-tooltip` attribute to every `el-table-column` across all 15 table views.

**Files** (15):
- `views/WarehouseView.vue`
- `views/ShopView.vue`
- `views/SuggestionListView.vue`
- `views/SkuConfigView.vue`
- `views/ApiMonitorView.vue`
- `views/SyncManagementView.vue`
- `views/ZipcodeRuleView.vue`
- `views/HistoryView.vue`
- `views/OverstockView.vue`
- `views/data/DataProductsView.vue`
- `views/data/DataInventoryView.vue`
- `views/data/DataOrdersView.vue`
- `views/data/DataOutRecordsView.vue`
- `views/SuggestionDetailView.vue`
- `views/ReplenishmentRunView.vue`

**Details**:
- Element Plus built-in: only triggers when text is actually truncated
- Remove existing `:title` attributes (e.g., ApiMonitorView) to avoid double tooltip
- Remove custom `.ellipsis` CSS class usage if it was only for truncation display (the tooltip handles it)

---

## 2. Table Column Sorting

**Goal**: Users can sort table data by clicking column headers (ascending/descending toggle).

**Approach**: Add `sortable` attribute to appropriate `el-table-column` elements. Uses Element Plus frontend sorting (`sortable`, not `sortable="custom"`).

**Columns that GET sorting**:
- Numeric columns (quantities, amounts, days, priority, counts)
- Date/time columns (created_at, updated_at, synced_at, etc.)
- Status columns (short tag text)
- Short code columns (country code, SKU code, warehouse code, shop name)

**Columns that DO NOT get sorting**:
- Long text columns (product titles, error messages, endpoint URLs, descriptions)
- Action/operation columns (buttons)
- Custom component columns (SkuCard)
- Nested/expanded content

**Files**: Same 15 views as section 1.

---

## 3. Warehouse Country Dropdown

**Goal**: Replace free-text country input with a searchable dropdown.

**File**: `views/WarehouseView.vue`

**Changes**:
- Replace `el-input` (maxlength=2) with `el-select` + `filterable`
- Hardcode 21 country options from saihu API site mapping:

```typescript
const countryOptions = [
  { code: 'US', label: 'US - 美国' },
  { code: 'CA', label: 'CA - 加拿大' },
  { code: 'MX', label: 'MX - 墨西哥' },
  { code: 'GB', label: 'GB - 英国' },
  { code: 'DE', label: 'DE - 德国' },
  { code: 'FR', label: 'FR - 法国' },
  { code: 'IT', label: 'IT - 意大利' },
  { code: 'ES', label: 'ES - 西班牙' },
  { code: 'IN', label: 'IN - 印度' },
  { code: 'JP', label: 'JP - 日本' },
  { code: 'AU', label: 'AU - 澳大利亚' },
  { code: 'AE', label: 'AE - 阿联酋' },
  { code: 'TR', label: 'TR - 土耳其' },
  { code: 'SG', label: 'SG - 新加坡' },
  { code: 'BR', label: 'BR - 巴西' },
  { code: 'NL', label: 'NL - 荷兰' },
  { code: 'SA', label: 'SA - 沙特阿拉伯' },
  { code: 'SE', label: 'SE - 瑞典' },
  { code: 'PL', label: 'PL - 波兰' },
  { code: 'BE', label: 'BE - 比利时' },
  { code: 'IE', label: 'IE - 爱尔兰' },
]
```

- Selected value is the 2-char code (e.g., `US`) — compatible with existing data
- `@change` triggers save, replacing `@blur` / `@keyup.enter`
- Remove maxlength validation logic
- Remove the "ISO 两位码" placeholder

---

## 4. Remove Page Descriptions and Hints

**Goal**: Strip all descriptive text and field hints for a cleaner interface.

**Deletions**:

| File | What to remove |
|------|---------------|
| `views/WarehouseView.vue` | Page-level `<p>` description |
| `views/ShopView.vue` | Page-level `<p>` description |
| `views/SuggestionListView.vue` | Page-level `<p>` description |
| `views/ReplenishmentRunView.vue` | Page-level `<p>` description |
| `views/SyncAutoView.vue` | Page-level `<p>` description |
| `views/SyncManualView.vue` | Page-level `<p>` description |
| `views/GlobalConfigView.vue` | All `<span class="hint">` elements (6 total) |
| `views/ZipcodeRuleView.vue` | Inline hint text |
| `config/sync.ts` | `description` field values in sync definitions (if only used for display) |

**Preserved**: Field labels, placeholders, and any text that serves as an input constraint indicator.

---

## 5. Cron Expression Preset Dropdown + Custom Input

**Goal**: Replace plain text input with a dropdown of common cron schedules, with a custom fallback.

**File**: `views/GlobalConfigView.vue`

**Preset options**:
```typescript
const cronPresets = [
  { label: '每天 06:00', value: '0 6 * * *' },
  { label: '每天 08:00', value: '0 8 * * *' },
  { label: '每天 12:00', value: '0 12 * * *' },
  { label: '每天 20:00', value: '0 20 * * *' },
  { label: '每 12 小时', value: '0 */12 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '自定义', value: '__custom__' },
]
```

**Interaction logic**:
- On page load: if `form.calc_cron` matches a preset value, select that preset. Otherwise, select "自定义" and show the text input with current value.
- Selecting a preset: hides text input, sets `form.calc_cron` to preset value.
- Selecting "自定义": shows `el-input` below, placeholder `0 8 * * *`, user types cron expression manually.

**State management**:
- Add a reactive `cronMode` ref: `'preset'` or `'custom'`
- Add a `selectedCronPreset` ref to track dropdown selection
- `form.calc_cron` remains the source of truth for the actual value sent to backend
