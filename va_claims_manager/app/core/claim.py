"""
Claim data model and Caluza Triangle evaluation logic.
"""
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Claim:
    id: Optional[int] = None
    veteran_id: int = 0
    condition_name: str = ""
    vasrd_code: str = ""
    body_system: str = ""
    claim_type: str = "direct"
    presumptive_basis: str = ""
    # Caluza Triangle
    has_diagnosis: bool = False
    diagnosis_source: str = ""
    diagnosis_date: str = ""
    has_inservice_event: bool = False
    inservice_source: str = ""
    inservice_description: str = ""
    inservice_date: str = ""
    has_nexus: bool = False
    nexus_source: str = ""
    nexus_type: str = "direct"
    nexus_language_verified: bool = False
    # Denial risk flags
    risk_missing_nexus: bool = False
    risk_no_continuity: bool = False
    risk_wrong_form: bool = False
    risk_negative_cp_likely: bool = False
    # Status
    status: str = "building"   # building | ready | submitted | decided | appealing
    priority_rating: Optional[int] = None
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def triangle_complete(self) -> bool:
        return self.has_diagnosis and self.has_inservice_event and self.has_nexus

    @property
    def triangle_score(self) -> int:
        """0-3: how many legs of the Caluza Triangle are satisfied."""
        return sum([self.has_diagnosis, self.has_inservice_event, self.has_nexus])

    @property
    def risk_count(self) -> int:
        return sum([
            self.risk_missing_nexus, self.risk_no_continuity,
            self.risk_wrong_form, self.risk_negative_cp_likely,
        ])

    @property
    def status_color(self) -> str:
        """Return a CSS hex color for the claim's overall status."""
        if self.triangle_complete and self.risk_count == 0:
            return "#1a7a4a"   # green — ready
        elif self.triangle_complete and self.risk_count > 0:
            return "#b8610a"   # orange — complete but risks
        elif self.triangle_score >= 2:
            return "#0070c0"   # blue — mostly done
        else:
            return "#c0392b"   # red — incomplete

    def compute_risks(self):
        """
        Recompute denial risk flags based on current triangle state.
        Called before saving to DB.
        """
        self.risk_missing_nexus = not self.has_nexus
        # Nexus language verification
        if self.has_nexus and not self.nexus_language_verified:
            self.risk_negative_cp_likely = True
        else:
            self.risk_negative_cp_likely = False
        # Form correctness (basic check)
        self.risk_wrong_form = (self.claim_type == "tdiu" and not self.has_diagnosis)
        # Continuity risk if no in-service event linked
        self.risk_no_continuity = (not self.has_inservice_event)

    @classmethod
    def from_row(cls, row) -> "Claim":
        return cls(
            id=row["id"],
            veteran_id=row["veteran_id"],
            condition_name=row["condition_name"] or "",
            vasrd_code=row["vasrd_code"] or "",
            body_system=row["body_system"] or "",
            claim_type=row["claim_type"] or "direct",
            presumptive_basis=row["presumptive_basis"] or "",
            has_diagnosis=bool(row["has_diagnosis"]),
            diagnosis_source=row["diagnosis_source"] or "",
            diagnosis_date=row["diagnosis_date"] or "",
            has_inservice_event=bool(row["has_inservice_event"]),
            inservice_source=row["inservice_source"] or "",
            inservice_description=row["inservice_description"] or "",
            inservice_date=row["inservice_date"] or "",
            has_nexus=bool(row["has_nexus"]),
            nexus_source=row["nexus_source"] or "",
            nexus_type=row["nexus_type"] or "direct",
            nexus_language_verified=bool(row["nexus_language_verified"]),
            risk_missing_nexus=bool(row["risk_missing_nexus"]),
            risk_no_continuity=bool(row["risk_no_continuity"]),
            risk_wrong_form=bool(row["risk_wrong_form"]),
            risk_negative_cp_likely=bool(row["risk_negative_cp_likely"]),
            status=row["status"] or "building",
            priority_rating=row["priority_rating"],
            notes=row["notes"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )
