from __future__ import annotations

from typing import Dict, List
from datetime import datetime

from src.common.models import AppState, Case


def _latest_evidence(cases: List[Case], limit: int = 5) -> List[Dict]:
    items: List[Dict] = []
    for c in cases:
        for e in c.evidence:
            items.append({
                "case_id": c.id,
                "case_name": c.name,
                "evidence_id": e.id,
                "title": e.title,
                "type": e.type,
                "date": e.date or "",
            })
    def sort_key(x: Dict):
        try:
            return datetime.fromisoformat(x.get("date", "").replace("Z", ""))
        except Exception:
            return datetime.min

    items.sort(key=sort_key, reverse=True)
    return items[:limit]


def overview(state: AppState) -> Dict:
    active = [c for c in state.cases if not c.archived]
    archived = [c for c in state.cases if c.archived]
    return {
        "active_cases": len(active),
        "archived_cases": len(archived),
        "latest_evidence": _latest_evidence(state.cases, limit=8),
    }
