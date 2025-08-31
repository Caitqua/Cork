from __future__ import annotations

from typing import List, Optional

from src.common.models import Case, NoteItem
from src.common.storage import gen_id
from src.common.models import now_iso


def list_notes(case: Case) -> List[NoteItem]:
    return list(case.notes)


def create_note(case: Case, *, title: str, body: str) -> NoteItem:
    note = NoteItem(id=gen_id("note"), title=title or "Note", body=body or "", created_at=now_iso(), updated_at=now_iso())
    case.notes.append(note)
    return note


def find_note(case: Case, note_id: str) -> Optional[NoteItem]:
    return next((n for n in case.notes if n.id == note_id), None)


def update_note(case: Case, note_id: str, *, title: Optional[str] = None, body: Optional[str] = None) -> Optional[NoteItem]:
    n = find_note(case, note_id)
    if not n:
        return None
    if title is not None:
        n.title = title
    if body is not None:
        n.body = body
    n.updated_at = now_iso()
    return n


def delete_note(case: Case, note_id: str) -> bool:
    before = len(case.notes)
    case.notes = [n for n in case.notes if n.id != note_id]
    return len(case.notes) != before

