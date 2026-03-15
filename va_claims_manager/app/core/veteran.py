"""
Veteran data model (plain dataclass, no UI or DB dependencies).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Veteran:
    id: Optional[int] = None
    full_name: str = ""
    ssn_last4: str = ""
    dob: str = ""                  # ISO-8601 date string
    branch: str = ""
    entry_date: str = ""           # ISO-8601
    separation_date: str = ""      # ISO-8601
    discharge_type: str = "Honorable"
    dd214_on_file: bool = False
    era: str = ""
    notes: str = ""
    # Dependent counts — used for accurate compensation rate calculation
    dependents_spouse: int = 0     # 0 or 1
    dependents_children: int = 0   # number of qualifying children
    dependents_parents: int = 0    # number of dependent parents (0, 1, or 2)
    created_at: str = ""
    updated_at: str = ""

    @property
    def display_name(self) -> str:
        return self.full_name or "Unknown Veteran"

    @property
    def service_summary(self) -> str:
        parts = []
        if self.branch:
            parts.append(self.branch)
        if self.entry_date and self.separation_date:
            parts.append(f"{self.entry_date[:4]}–{self.separation_date[:4]}")
        elif self.entry_date:
            parts.append(f"from {self.entry_date[:4]}")
        return ", ".join(parts) if parts else "No service info"

    @classmethod
    def from_row(cls, row) -> "Veteran":
        """Create a Veteran from a sqlite3.Row."""
        keys = row.keys() if hasattr(row, "keys") else []
        return cls(
            id=row["id"],
            full_name=row["full_name"] or "",
            ssn_last4=row["ssn_last4"] or "",
            dob=row["dob"] or "",
            branch=row["branch"] or "",
            entry_date=row["entry_date"] or "",
            separation_date=row["separation_date"] or "",
            discharge_type=row["discharge_type"] or "Honorable",
            dd214_on_file=bool(row["dd214_on_file"]),
            era=row["era"] or "",
            notes=row["notes"] or "",
            dependents_spouse=int(row["dependents_spouse"]) if "dependents_spouse" in keys else 0,
            dependents_children=int(row["dependents_children"]) if "dependents_children" in keys else 0,
            dependents_parents=int(row["dependents_parents"]) if "dependents_parents" in keys else 0,
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
