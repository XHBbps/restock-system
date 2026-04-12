# Fix suggestion.py Encoding Corruption

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix encoding-corrupted Chinese strings in `suggestion.py` while preserving the new sorting functionality that was added in the same uncommitted changeset.

**Architecture:** Restore the file to its committed (clean) version, then re-apply only the legitimate code changes: new sorting functions, new query parameters, intentional docstring changes. Do NOT re-apply any corrupted Chinese strings.

**Tech Stack:** Python, FastAPI, SQLAlchemy

---

### Task 1: Restore and re-apply changes to suggestion.py

**Files:**
- Modify: `backend/app/api/suggestion.py`

- [ ] **Step 1: Restore the committed version**

```bash
cd E:\Ai_project\restock_system
git checkout HEAD -- backend/app/api/suggestion.py
```

This restores the file to the last committed (encoding-clean) version.

- [ ] **Step 2: Add new imports**

At the top of the file, add the two new imports needed by the sorting functions.

Change:
```python
from sqlalchemy import func, select, update
```
To:
```python
from sqlalchemy import Float, case, func, select, update
```

And add after the `from sqlalchemy.ext.asyncio import AsyncSession` line:
```python
from sqlalchemy.sql.elements import ColumnElement
```

- [ ] **Step 3: Add sorting helper functions**

After the `router = APIRouter(...)` line, add:

```python
SUGGESTION_STATUS_SORT_ORDER: dict[str, int] = {
    "draft": 0,
    "partial": 1,
    "pushed": 2,
    "archived": 3,
    "error": 4,
}


def _suggestion_status_sort_expr() -> ColumnElement[int]:
    return case(
        *[(Suggestion.status == status, order) for status, order in SUGGESTION_STATUS_SORT_ORDER.items()],
        else_=len(SUGGESTION_STATUS_SORT_ORDER),
    )


def _success_rate_sort_expr() -> ColumnElement[float]:
    return func.coalesce(
        Suggestion.pushed_items.cast(Float) / func.nullif(Suggestion.total_items, 0),
        -1.0,
    )


def _apply_suggestion_sort(stmt, sort_by: str | None, sort_order: str):
    success_rate_expr = _success_rate_sort_expr()
    sort_map: dict[str, tuple[ColumnElement[object], ...]] = {
        "id": (Suggestion.id,),
        "created_at": (Suggestion.created_at,),
        "triggered_by": (Suggestion.triggered_by,),
        "status": (_suggestion_status_sort_expr(),),
        "total_items": (Suggestion.total_items,),
        "pushed_items": (Suggestion.pushed_items,),
        "failed_items": (Suggestion.failed_items,),
        "success_rate": (
            case((Suggestion.total_items == 0, 1), else_=0),
            success_rate_expr,
        ),
    }
    columns = sort_map.get(sort_by or "", (Suggestion.created_at,))
    ordered_columns = [column.asc() if sort_order == "asc" else column.desc() for column in columns]
    return stmt.order_by(*ordered_columns, Suggestion.created_at.desc(), Suggestion.id.desc())
```

- [ ] **Step 4: Update `list_suggestions` endpoint**

Add sort parameters and use the sort helper:

1. Add two new query params to `list_suggestions`:
```python
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
```

2. Change `base = select(Suggestion).order_by(Suggestion.created_at.desc())` to:
```python
    base = select(Suggestion)
```

3. After the `sku` filter block and before `count_stmt`, add:
```python
    base = _apply_suggestion_sort(base, sort_by, sort_order)
```

- [ ] **Step 5: Verify the server starts**

```bash
cd backend && .\.venv\Scripts\python.exe -c "from app.api.suggestion import router; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/suggestion.py
git commit -m "feat: add suggestion list sorting + fix encoding corruption"
```
