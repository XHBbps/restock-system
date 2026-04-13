# Dedup Pushed Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent duplicate replenishment suggestions by treating already-pushed (unarchived) suggestion items as in-transit inventory during engine calculation.

**Architecture:** Replace the stub `load_in_transit()` in `step2_sale_days.py` with a real implementation that queries `suggestion_item` rows where `push_status = 'pushed'` and the parent `suggestion` is not archived. Sum each item's `country_breakdown` by (sku, country) and return it as in-transit stock. The existing `merge_inventory()` already adds in-transit to `total`, so `step3_country_qty` will automatically subtract these quantities.

**Tech Stack:** Python, SQLAlchemy, PostgreSQL JSONB

---

### Task 1: Implement `load_in_transit` from pushed suggestions

**Files:**
- Modify: `backend/app/engine/step2_sale_days.py`
- Modify: `backend/tests/unit/test_engine_step3.py` (optional: add integration-level test)

- [ ] **Step 1: Replace `load_in_transit` stub with real implementation**

In `backend/app/engine/step2_sale_days.py`, replace the stub function:

```python
async def load_in_transit(
    _db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[tuple[str, str], int]:
    """In-transit stock is intentionally disabled for now."""
    del commodity_skus
    return {}
```

With:

```python
async def load_in_transit(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[tuple[str, str], int]:
    """Load in-transit quantities from pushed (unarchived) suggestion items.

    Already-pushed suggestion items represent planned replenishment that hasn't
    arrived yet. Their country_breakdown quantities are treated as in-transit
    stock to prevent the engine from generating duplicate suggestions.
    """
    from app.models.suggestion import Suggestion, SuggestionItem

    stmt = (
        select(
            SuggestionItem.commodity_sku,
            SuggestionItem.country_breakdown,
        )
        .join(Suggestion, Suggestion.id == SuggestionItem.suggestion_id)
        .where(SuggestionItem.push_status == "pushed")
        .where(Suggestion.status != "archived")
    )
    if commodity_skus is not None:
        stmt = stmt.where(SuggestionItem.commodity_sku.in_(commodity_skus))

    rows = (await db.execute(stmt)).all()

    result: dict[tuple[str, str], int] = {}
    for sku, breakdown in rows:
        if not breakdown:
            continue
        for country, qty in breakdown.items():
            key = (sku, country)
            result[key] = result.get(key, 0) + int(qty)
    return result
```

- [ ] **Step 2: Update the docstring at top of file**

Change:
```python
- in_transit is temporarily disabled for replenishment and treated as 0
```
To:
```python
- in_transit comes from pushed (unarchived) suggestion items' country_breakdown
```

- [ ] **Step 3: Add import for select (already imported) — verify no new imports needed**

The function uses `select` (already imported), `Suggestion` and `SuggestionItem` (imported locally inside the function to avoid circular imports).

- [ ] **Step 4: Run existing tests**

Run: `cd backend && python -m pytest tests/unit/test_engine_step3.py -v`
Expected: All tests still pass (they use `compute_country_qty` directly with mock data, not affected by this change)

- [ ] **Step 5: Verify engine runs without error**

Run: `cd backend && python -c "from app.engine.step2_sale_days import load_in_transit; print('OK')"`

- [ ] **Step 6: Commit**

```bash
git add backend/app/engine/step2_sale_days.py
git commit -m "feat: load pushed suggestion items as in-transit stock to prevent duplicate suggestions"
```
