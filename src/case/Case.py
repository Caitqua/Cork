@dataclass
class Case:
    id: str
    name: str
    # archived: bool = False
    # solved: bool = False
    def to_dict(self) -> Dict:
        return asdict(self)
