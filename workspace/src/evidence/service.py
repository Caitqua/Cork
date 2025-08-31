from __future__ import annotations

from typing import List, Optional, Dict

from src.common.models import EvidenceItem, Case, EvidenceLink
from src.common.storage import gen_id


def create_evidence(
    case: Case,
    *,
    type: str,
    title: str,
    date: Optional[str] = None,
    location: Optional[str] = None,
    collector: Optional[str] = None,
    notes: str = "",
    tags: Optional[List[str]] = None,
    details: Optional[Dict[str, str]] = None,
) -> EvidenceItem:
    item = EvidenceItem(
        id=gen_id("evid"),
        type=type,
        title=title,
        date=date,
        location=location,
        collector=collector,
        notes=notes,
        tags=list(tags or []),
        details=dict(details or {}),
    )
    case.evidence.append(item)
    return item


def find_evidence(case: Case, evidence_id: str) -> Optional[EvidenceItem]:
    return next((e for e in case.evidence if e.id == evidence_id), None)


def add_evidence_link(e: EvidenceItem, *, target_type: str, target_id: str, label: Optional[str] = None, visible: bool = True, show_label: bool = False) -> EvidenceLink:
    ln = EvidenceLink(id=gen_id("evl"), target_type=target_type, target_id=target_id, label=label, visible=visible, show_label=show_label)
    e.links.append(ln)
    return ln


def update_evidence_link(e: EvidenceItem, link_id: str, *, target_type: Optional[str] = None, target_id: Optional[str] = None, label: Optional[str] = None, visible: Optional[bool] = None, show_label: Optional[bool] = None) -> Optional[EvidenceLink]:
    ln = next((x for x in e.links if x.id == link_id), None)
    if not ln:
        return None
    if target_type is not None:
        ln.target_type = target_type
    if target_id is not None:
        ln.target_id = target_id
    if label is not None:
        ln.label = label
    if visible is not None:
        ln.visible = bool(visible)
    if show_label is not None:
        ln.show_label = bool(show_label)
    return ln


def remove_evidence_link(e: EvidenceItem, link_id: str) -> bool:
    before = len(e.links)
    e.links = [x for x in e.links if x.id != link_id]
    return len(e.links) != before


def delete_evidence(case: Case, evidence_id: str) -> bool:
    # remove evidence item
    idx = next((i for i, e in enumerate(case.evidence) if e.id == evidence_id), None)
    if idx is None:
        return False
    del case.evidence[idx]
    # purge links in other evidence that target this evidence
    for ev in case.evidence:
        ev.links = [ln for ln in (ev.links or []) if not (ln.target_type == 'evidence' and ln.target_id == evidence_id)]
    # remove any board nodes pinned to this evidence
    nodes_to_remove = [n.id for n in list(case.board_nodes) if getattr(n, 'evidence_id', None) == evidence_id]
    if nodes_to_remove:
        case.board_nodes = [n for n in case.board_nodes if n.id not in nodes_to_remove]
        # also remove any board links attached to those nodes (back-compat if board links are used)
        case.board_links = [bl for bl in case.board_links if bl.source not in nodes_to_remove and bl.target not in nodes_to_remove]
    return True
