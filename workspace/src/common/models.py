from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

@dataclass
class EvidenceLink:
    id: str
    target_type: str  # 'node' or 'evidence'
    target_id: str
    label: Optional[str] = None
    visible: bool = True
    show_label: bool = False


@dataclass
class EvidenceItem:
    id: str
    type: str
    title: str
    date: Optional[str] = None
    location: Optional[str] = None
    collector: Optional[str] = None
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    details: Dict[str, str] = field(default_factory=dict)
    links: List[EvidenceLink] = field(default_factory=list)


@dataclass
class DocumentItem:
    id: str
    title: str
    path: str
    mime: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class NoteItem:
    id: str
    title: str
    body: str
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    tags: List[str] = field(default_factory=list)


@dataclass
class BoardNode:
    id: str
    title: str
    description: str = ""
    icon: Optional[str] = None
    image_path: Optional[str] = None
    evidence_id: Optional[str] = None
    details: Dict[str, str] = field(default_factory=dict)
    thread: Optional[str] = None
    x: int = 100
    y: int = 100


@dataclass
class BoardLink:
    id: str
    source: str
    target: str
    label: Optional[str] = None
    visible: bool = True
    show_label: bool = False


@dataclass
class Case:
    id: str
    name: str
    archived: bool = False
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    client_info: Dict[str, str] = field(default_factory=dict)
    objectives: List[str] = field(default_factory=list)
    case_type: Optional[str] = None
    summary: str = ""
    evidence: List[EvidenceItem] = field(default_factory=list)
    documents: List[DocumentItem] = field(default_factory=list)
    notes: List[NoteItem] = field(default_factory=list)
    board_nodes: List[BoardNode] = field(default_factory=list)
    board_links: List[BoardLink] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AppState:
    cases: List[Case] = field(default_factory=list)
    last_saved_at: Optional[str] = None
    # UI/Config flags
    dark_mode: bool = False

    def to_dict(self) -> Dict:
        return {
            "cases": [c.to_dict() for c in self.cases],
            "last_saved_at": self.last_saved_at,
            "dark_mode": self.dark_mode,
        }
