from __future__ import annotations

from typing import List, Optional

from src.common.models import Case, BoardNode, BoardLink, EvidenceItem
from src.common.storage import gen_id


def add_node(
    case: Case,
    *,
    title: str,
    description: str = "",
    x: int | None = None,
    y: int | None = None,
    icon: str | None = None,
    image_path: str | None = None,
    evidence_id: str | None = None,
) -> BoardNode:
    # place nodes in a simple grid if not provided
    idx = len(case.board_nodes)
    if x is None or y is None:
        cols = 4
        cell_w, cell_h = 180, 140
        r, c = divmod(idx, cols)
        x = 120 + c * cell_w
        y = 100 + r * cell_h
    node = BoardNode(
        id=gen_id("node"),
        title=title,
        description=description,
        icon=icon,
        image_path=image_path,
        evidence_id=evidence_id,
        x=x,
        y=y,
    )
    case.board_nodes.append(node)
    return node


def _icon_for_evidence_type(t: str) -> str:
    t = (t or "").lower()
    if "photo" in t or "image" in t:
        return "📷"
    if "video" in t or "clip" in t:
        return "🎞️"
    if "audio" in t:
        return "🎧"
    if "document" in t or "doc" in t:
        return "📄"
    if "link" in t:
        return "🔗"
    if "person" in t:
        return "👤"
    return "📌"


def add_node_from_evidence(case: Case, e: EvidenceItem) -> BoardNode | None:
    # Avoid duplicates by evidence_id
    if any((n.evidence_id == e.id) for n in case.board_nodes):
        return None
    title = f"[{e.type}] {e.title}"
    icon = _icon_for_evidence_type(e.type)
    return add_node(case, title=title, description=e.notes or "", icon=icon, evidence_id=e.id)


def add_link(case: Case, *, source: str, target: str, label: Optional[str] = None) -> BoardLink:
    link = BoardLink(id=gen_id("link"), source=source, target=target, label=label)
    case.board_links.append(link)
    return link


def list_nodes(case: Case) -> List[BoardNode]:
    return list(case.board_nodes)


def list_links(case: Case) -> List[BoardLink]:
    return list(case.board_links)


def remove_node(case: Case, node_id: str) -> bool:
    before = len(case.board_nodes)
    case.board_nodes = [n for n in case.board_nodes if n.id != node_id]
    case.board_links = [e for e in case.board_links if e.source != node_id and e.target != node_id]
    return len(case.board_nodes) != before


def remove_link(case: Case, link_id: str) -> bool:
    before = len(case.board_links)
    case.board_links = [e for e in case.board_links if e.id != link_id]
    return len(case.board_links) != before
