from __future__ import annotations

import json
import os
import uuid
from typing import Optional

from .models import AppState, Case, EvidenceItem, DocumentItem, NoteItem, BoardNode, BoardLink, EvidenceLink
from .models import now_iso


DEFAULT_DATA_PATH = os.getenv("APP_DATA_PATH", os.path.join(os.getcwd(), "data", "store.json"))


def ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_state(path: Optional[str] = None) -> AppState:
    path = path or DEFAULT_DATA_PATH
    if not os.path.exists(path):
        return AppState()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    cases = []
    for c in raw.get("cases", []):
        case = Case(
            id=c["id"],
            name=c.get("name", "Untitled"),
            archived=c.get("archived", False),
            created_at=c.get("created_at", now_iso()),
            updated_at=c.get("updated_at", now_iso()),
            client_info=c.get("client_info", {}),
            objectives=c.get("objectives", []),
            case_type=c.get("case_type"),
            summary=c.get("summary", ""),
        )
        for e in c.get("evidence", []):
            case.evidence.append(
                EvidenceItem(
                    id=e["id"],
                    type=e.get("type", "unknown"),
                    title=e.get("title", "Untitled"),
                    date=e.get("date"),
                    location=e.get("location"),
                    collector=e.get("collector"),
                    notes=e.get("notes", ""),
                    tags=e.get("tags", []),
                    details=e.get("details", {}),
                    links=[
                        EvidenceLink(
                            id=ln.get("id"),
                            target_type=ln.get("target_type", "evidence"),
                            target_id=ln.get("target_id", ""),
                            label=ln.get("label"),
                            visible=bool(ln.get("visible", True)),
                            show_label=bool(ln.get("show_label", False)),
                        )
                        for ln in e.get("links", [])
                    ],
                )
            )
        for d in c.get("documents", []):
            case.documents.append(
                DocumentItem(
                    id=d["id"], title=d.get("title", "Untitled"), path=d.get("path", ""), mime=d.get("mime"), tags=d.get("tags", []), meta=d.get("meta", {})
                )
            )
        for n in c.get("notes", []):
            case.notes.append(
                NoteItem(
                    id=n["id"],
                    title=n.get("title", "Note"),
                    body=n.get("body", ""),
                    created_at=n.get("created_at", now_iso()),
                    updated_at=n.get("updated_at", now_iso()),
                    tags=n.get("tags", []),
                )
            )
        for bn in c.get("board_nodes", []):
            case.board_nodes.append(
                BoardNode(
                    id=bn["id"],
                    title=bn.get("title", "Node"),
                    description=bn.get("description", ""),
                    icon=bn.get("icon"),
                    image_path=bn.get("image_path"),
                    evidence_id=bn.get("evidence_id"),
                    details=bn.get("details", {}),
                    thread=bn.get("thread"),
                    x=int(bn.get("x", 100)),
                    y=int(bn.get("y", 100)),
                )
            )
        # links (backward compat: also accept board_edges)
        for bl in (c.get("board_links") or c.get("board_edges") or []):
            case.board_links.append(
                BoardLink(
                    id=bl["id"],
                    source=bl.get("source", ""),
                    target=bl.get("target", ""),
                    label=bl.get("label"),
                    visible=bool(bl.get("visible", True)),
                    show_label=bool(bl.get("show_label", False)),
                )
            )
        cases.append(case)
    return AppState(
        cases=cases,
        last_saved_at=raw.get("last_saved_at"),
        dark_mode=bool(raw.get("dark_mode", False)),
    )


def save_state(state: AppState, path: Optional[str] = None) -> None:
    path = path or DEFAULT_DATA_PATH
    ensure_dir(path)
    state.last_saved_at = now_iso()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
