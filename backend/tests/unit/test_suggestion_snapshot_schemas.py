from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.suggestion_snapshot import (
    SnapshotCreateRequest,
    SnapshotItemOut,
    SnapshotOut,
)


def test_snapshot_create_request():
    req = SnapshotCreateRequest(item_ids=[1, 2, 3], note="发给供应商 A")
    assert req.item_ids == [1, 2, 3]
    assert req.note == "发给供应商 A"


def test_snapshot_create_request_note_optional():
    req = SnapshotCreateRequest(item_ids=[1])
    assert req.note is None


def test_snapshot_create_request_note_max_length():
    with pytest.raises(ValidationError):
        SnapshotCreateRequest(item_ids=[1], note="x" * 201)


def test_snapshot_create_request_items_min_one():
    with pytest.raises(ValidationError):
        SnapshotCreateRequest(item_ids=[])


def test_snapshot_out_fields():
    out = SnapshotOut(
        id=1,
        suggestion_id=42,
        version=1,
        exported_by=10,
        exported_by_name="alice",
        exported_at=datetime.now(),
        item_count=3,
        note="test",
        generation_status="ready",
        file_size_bytes=2048,
        download_count=0,
    )
    assert out.version == 1
    assert out.generation_status == "ready"
