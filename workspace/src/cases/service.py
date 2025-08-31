from __future__ import annotations

from typing import List, Optional

from src.common.models import Case
from src.common.storage import gen_id


def create_case(name: str) -> Case:
    return Case(id=gen_id("case"), name=name)


def find_case(cases: List[Case], case_id: str) -> Optional[Case]:
    return next((c for c in cases if c.id == case_id), None)

