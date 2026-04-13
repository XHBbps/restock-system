# Table Header Alignment & No-Wrap Fix

## Overview

Fix two visual issues in all Element Plus tables after adding `sortable` attributes:
1. Table headers with sort icons wrap to multiple lines
2. Table content not consistently aligned under its header

## Solution

Single file change: `frontend/src/styles/element-overrides.scss`, Table section.

### Fix 1: Header no-wrap

Add `white-space: nowrap` to `th.el-table__cell` to prevent header text + sort icon from wrapping.

Add `.caret-wrapper` inline-flex styling to keep sort icon properly inline.

### Fix 2: Cell padding alignment

Ensure `th` and `td` `.cell` both have `padding: 0 !important` with consistent `line-height: inherit` so content aligns horizontally with its header.

## Scope

- CSS only, no Vue template changes
- Affects all tables globally via element-overrides.scss
