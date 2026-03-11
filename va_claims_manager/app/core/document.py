"""
Document data model.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Document:
    id: Optional[int] = None
    veteran_id: int = 0
    claim_id: Optional[int] = None
    filename: str = ""
    filepath: str = ""
    file_hash: str = ""
    doc_type: str = "Other"
    doc_date: str = ""
    source_facility: str = ""
    author: str = ""
    page_count: int = 0
    ocr_performed: bool = False
    ingestion_status: str = "pending"  # pending | processing | complete | error
    ingestion_error: str = ""
    file_size_bytes: int = 0
    created_at: str = ""

    @classmethod
    def from_row(cls, row) -> "Document":
        return cls(
            id=row["id"],
            veteran_id=row["veteran_id"],
            claim_id=row["claim_id"],
            filename=row["filename"] or "",
            filepath=row["filepath"] or "",
            file_hash=row["file_hash"] or "",
            doc_type=row["doc_type"] or "Other",
            doc_date=row["doc_date"] or "",
            source_facility=row["source_facility"] or "",
            author=row["author"] or "",
            page_count=row["page_count"] or 0,
            ocr_performed=bool(row["ocr_performed"]),
            ingestion_status=row["ingestion_status"] or "pending",
            ingestion_error=row["ingestion_error"] or "",
            file_size_bytes=row["file_size_bytes"] or 0,
            created_at=row["created_at"] or "",
        )

    @property
    def size_display(self) -> str:
        if self.file_size_bytes < 1024:
            return f"{self.file_size_bytes} B"
        elif self.file_size_bytes < 1024 * 1024:
            return f"{self.file_size_bytes / 1024:.1f} KB"
        else:
            return f"{self.file_size_bytes / (1024 * 1024):.1f} MB"
