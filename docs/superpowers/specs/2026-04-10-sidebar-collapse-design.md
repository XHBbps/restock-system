# Sidebar Collapse & Sub-Category Toggle Design

## Goal

Add two interactive features to the sidebar: (1) collapsible sub-category groups with expand/collapse toggle, (2) full sidebar collapse from 256px to 64px icon-only mode. Both states persist across page refreshes via localStorage, managed through a Pinia store.

## Architecture

A new `useSidebarStore` Pinia store manages `isCollapsed` (sidebar width) and `expandedCategories` (which sub-category groups are open). AppLayout reads these states to conditionally render text/sub-items and control sidebar width via CSS transition. No new dependencies required — uses existing lucide icons and SCSS design tokens.

## Feature 1: Sub-Category Collapsible Groups

**Behavior:**
- Sub-category labels (基础数据, 业务数据, 同步管理, 基础配置, 系统监控) become clickable toggles
- Click toggles visibility of child nav items with a slide-down transition
- A ChevronRight icon rotates 90° when expanded
- If the current route falls within a sub-category, that category auto-expands on page load
- Default: all sub-categories expanded on first visit

**State:**
- `expandedCategories: Set<string>` — set of expanded sub-category labels
- Persisted to localStorage as JSON array
- `toggleCategory(label: string)` action

## Feature 2: Sidebar Collapse (256px ↔ 64px)

**Behavior:**
- Collapsed state: sidebar shrinks to 64px, showing only top-level group titles and nav item icons
- Brand area: hide text, show only the "R" mark
- Nav items: hide labels, only show icons (centered)
- Sub-category titles: hidden entirely in collapsed mode
- Sub-category children: hidden entirely in collapsed mode (only top-level NavItem icons show)
- Footer: hide user text, center logout button
- Hover on icon in collapsed mode: show native `title` tooltip
- Toggle button: placed in the sidebar brand area (right side), uses PanelLeftClose / PanelLeftOpen icons from lucide

**Transition:**
- CSS `transition: width 300ms ease` on sidebar
- CSS `transition: opacity 150ms` on text elements for fade

**State:**
- `isCollapsed: boolean` — sidebar collapsed or not
- Persisted to localStorage
- `toggleCollapse()` action

## Feature 3: Sidebar Pinia Store

**File:** `src/stores/sidebar.ts`

```typescript
interface SidebarState {
  isCollapsed: boolean
  expandedCategories: Set<string>
}
```

**Actions:**
- `toggleCollapse()` — flip isCollapsed
- `toggleCategory(label: string)` — add/remove from expandedCategories
- `ensureCategoryExpanded(label: string)` — expand without toggle (for route-based auto-expand)

**Persistence:**
- `localStorage.getItem('sidebar_collapsed')` → boolean
- `localStorage.getItem('sidebar_expanded_cats')` → JSON string array
- Written via `watch` on state changes

## Files Affected

| File | Action | Responsibility |
|------|--------|---------------|
| `src/stores/sidebar.ts` | Create | Sidebar state management with localStorage persistence |
| `src/components/AppLayout.vue` | Modify | Template: collapsible sub-categories, sidebar collapse, toggle button. Style: transitions, collapsed layout |
| `src/config/navigation.ts` | No change | Existing structure already supports sub-categories |
| `src/router/index.ts` | No change | Existing routes unchanged |

## Collapsed Mode Rendering Rules

| Element | Expanded (256px) | Collapsed (64px) |
|---------|-------------------|-------------------|
| Brand mark "R" | Visible | Visible (centered) |
| Brand text | Visible | Hidden |
| Group title (HOME/RESTOCK/etc) | Visible | Hidden |
| Sub-category title | Visible + clickable toggle | Hidden |
| NavItem icon | Left-aligned with label | Centered, with title tooltip |
| NavItem label | Visible | Hidden |
| Sub-category children | Visible when expanded | Hidden |
| Footer user text | Visible | Hidden |
| Footer logout button | Right-aligned | Centered |
| Collapse toggle button | In brand area | In brand area |

## Out of Scope

- No el-menu migration (keep custom RouterLink implementation)
- No responsive mobile hamburger menu
- No keyboard shortcuts for collapse
- No drag-to-resize sidebar
