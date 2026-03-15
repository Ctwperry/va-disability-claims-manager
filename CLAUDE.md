# VA Disability Claims Manager — Developer Guide

A PyQt6 desktop app helping US Military Veterans organize medical records and
apply for VA disability compensation. Core framework: the **Caluza Triangle**
(current diagnosis + in-service event + medical nexus).

---

## Quick Start

```bash
cd "VA Disability Program/va_claims_manager"
python main.py          # or run.bat
```

Python: `C:\Users\Ctwpe\AppData\Local\Programs\Python\Python314\python.exe`

---

## Module Map

```
va_claims_manager/
├── main.py                        Entry point, splash, DB init, MainWindow launch
├── app/
│   ├── config.py                  Paths, constants, DOC_TYPE_WEIGHTS, VASRD_CODES_PATH, etc.
│   ├── core/
│   │   ├── claim.py               Claim dataclass + Caluza Triangle props + compute_risks()
│   │   ├── veteran.py             Veteran dataclass (display_name, service_summary props)
│   │   ├── document.py            Document dataclass
│   │   └── rating_calculator.py   combined_rating(), bilateral_adjustment(), check_tdiu_eligibility()
│   ├── analysis/
│   │   ├── condition_scanner.py   scan_veteran_records() — context-aware FTS5 scan with weighted scoring
│   │   ├── context_analyzer.py    analyze_context() — linguistic negation/positive/family/resolved detection
│   │   └── presumptive_data.py    get_era_categories(), enrich_vasrd_conditions() — PACT Act data
│   ├── db/
│   │   ├── connection.py          get_connection() — SQLite WAL mode, row_factory
│   │   ├── schema.py              initialize_database(), migrations (v1→4), get/set_setting()
│   │   └── repositories/
│   │       ├── veteran_repo.py    get_by_id, get_all, create, update, delete
│   │       ├── claim_repo.py      get_by_id, get_all, create, update, delete, count_*
│   │       └── document_repo.py   get_by_id, get_all_for_veteran, create, update, delete
│   ├── ingestion/
│   │   ├── pipeline.py            Parallel ingestion (ThreadPoolExecutor): file → pages → FTS5 index
│   │   ├── pdf_extractor.py       pdfplumber text extraction + OCR fallback
│   │   ├── docx_extractor.py      python-docx extraction
│   │   ├── ocr_processor.py       OpenCV + pytesseract OCR fallback
│   │   └── classifier.py          Heuristic doc_type detection (DD214, STR, DBQ, etc.)
│   ├── search/
│   │   └── fts_engine.py          FTS5 queries: snippet(), NEAR, phrase, BM25 rank
│   ├── services/
│   │   └── conditions_service.py  load_vasrd_codes(), load_enriched_conditions() — LRU-cached
│   ├── export/
│   │   ├── package_builder.py     Structured folder: cover + claim summaries + forms checklist
│   │   └── pdf_writer.py          reportlab PDF generation: cover sheet, claim summary, forms checklist
│   └── ui/
│       ├── app_window.py          MainWindow: sidebar nav, veteran combo, panel stack, theme init
│       ├── styles.py              MAIN_STYLE + DARK_STYLE QSS; get_style(dark=False)
│       ├── workers.py             QRunnable workers with Qt signals
│       ├── panels/
│       │   ├── dashboard_panel.py       Stat cards, combined rating, PACT banner, TDIU, era recs
│       │   ├── veteran_panel.py         Veteran profile CRUD
│       │   ├── claim_panel.py           Caluza Triangle editor, risks, continuity, dialogs
│       │   ├── document_panel.py        Drag-drop intake, classify, view
│       │   ├── search_panel.py          FTS5 search bar + snippet results
│       │   ├── export_panel.py          Export package configuration + generation
│       │   └── conditions_browser_panel.py  Browse 400+ VASRD codes, add claim one-click
│       ├── dialogs/
│       │   ├── settings_dialog.py        App settings: theme, OCR path, export dir, workers
│       │   ├── statement_4138_dialog.py  VA Form 21-4138 draft statement generator
│       │   ├── nexus_letter_dialog.py    Nexus letter request template
│       │   ├── buddy_statement_dialog.py VA Form 21-10210 buddy statement
│       │   ├── cp_prep_dialog.py         C&P exam prep sheet
│       │   └── scan_results_dialog.py    Context-aware scan results with evidence cards
│       └── widgets/
│           ├── triangle_widget.py        QPainter Caluza Triangle visualization
│           ├── symptom_log_widget.py     Symptom & Treatment Log table (JSON in/out)
│           └── evidence_panel.py         Linked evidence documents with role selectors
```

---

## Key Patterns

### Panel lifecycle
Every panel gets `load_veteran(veteran_id: int | None)` called when the veteran
changes. Panels that emit data changes use a signal (e.g., `claims_updated`,
`documents_updated`) which `app_window.py` connects to `DashboardPanel.refresh()`.

### Cross-panel navigation with pre-fill
`DashboardPanel` and `ConditionsBrowserPanel` emit `add_claim_requested(dict)`.
`MainWindow._on_add_claim_from_browser()` handles it: calls `_nav_select(3)` then
`ClaimPanel.prefill_new_claim(condition)`.

### Signal protocol for condition dicts
```python
{
    "name": str,            # condition display name
    "code": str,            # VASRD code or ""
    "system": str,          # body system or ""
    "is_presumptive": bool,
    "presumptive_basis": str,
    "eligible_eras": list[str],
}
```

### Database schema versions
| Version | Added |
|---------|-------|
| 1 | Base tables (veterans, claims, documents, FTS5) |
| 2 | `effective_date`, `effective_date_basis`, `secondary_to_claim_id` on claims |
| 3 | `first_treatment_date`, `continuity_notes` on claims |
| 4 | `symptom_log` TEXT (JSON) on claims |

Migrations live in `schema._run_migrations()`. Use `_alter_safe()` for idempotent
`ALTER TABLE` statements. Bump `CURRENT_VERSION` and add a `if from_version < N` block.

### Claim data flow
1. User fills `ClaimPanel` editor
2. `_on_save()` constructs a `Claim` dataclass, calls `claim.compute_risks()`
3. `claim_repo.create(c)` or `claim_repo.update(c)` persists to SQLite
4. `claims_updated` signal fires → Dashboard refreshes

### VASRD / Conditions
- `app/services/conditions_service.py` is the single source for loading VASRD codes
- `load_vasrd_codes()` → raw list of `{code, name, system}` dicts (LRU-cached)
- `load_enriched_conditions()` → same list enriched with `is_presumptive`, `presumptive_basis`, `eligible_eras` (LRU-cached)

### Symptom log
Stored as a JSON string in `claims.symptom_log`. `SymptomLogWidget` (in
`ui/widgets/`) handles the table UI. Its public API:
- `load_data(json_str)` — populate table
- `get_data_json() -> str` — serialize back
- `clear()` — reset to empty

### Evidence linking
`EvidencePanel` (in `ui/widgets/`) handles the linked-documents display.
Public API: `load_evidence(claim_id)`, `clear()`.
DB join: `claim_documents(claim_id, document_id, role, notes)` where `notes` is
a JSON blob `{pages: [{page_number, keyword, snippet, pattern_label, positive, negated}], auto_detected, confidence, score}`.

---

## Context-Aware Condition Scanning

`condition_scanner.py` uses a **weighted confidence score** instead of raw match counts:

```
confidence_score = avg(evidence_score per piece)
  where evidence_score =
    -0.5                      if negation_detected or family_history
    source_weight × 1.5       if positive_diagnosis
    source_weight × 0.5       if uncertainty_flag
    source_weight             otherwise
```

Confidence levels: `High ≥ 0.70`, `Medium ≥ 0.40`, `Low ≥ 0.10`, `Very Low ≥ −0.10`, `Negative < −0.10`

`context_analyzer.py` classifies the ±200-char text window around each keyword match:
- **Family History** → `family_history=True` (highest priority, returns immediately)
- **Negation** → `negation_detected=True` ("denies", "ruled out", "no evidence of", "R/O")
- **Workup/Differential** → treated as negation ("workup for", "consider", "differential")
- **Positive Diagnosis** → `positive_diagnosis=True` ("diagnosed with", "assessment:", "on treatment")
- **Resolved** → `resolved=True` ("resolved", "healed", "in remission")
- **Uncertain** → `uncertainty_flag=True` ("possible", "questionable", "suspected")

`DOC_TYPE_WEIGHTS` in `config.py` maps document types to quality scores (DBQ/NexusLetter = 1.0,
STR = 0.9, VAMedical = 0.80, BuddyStatement = 0.40, etc.).

---

## Document Ingestion (Parallel)

`pipeline.py` uses `ThreadPoolExecutor` (default 4 workers) for concurrent extraction:
- **Worker threads**: SHA-256 hash + text extraction + classification (all GIL-releasing I/O)
- **Calling thread**: dedup check + all DB writes (serialised to avoid WAL contention)
- Progress fires per-file as each completes (not in batch)
- `max_workers` configurable via `SettingsDialog` → `app_settings` table key `max_ingestion_workers`

---

## Theming (Dark / Light Mode)

```python
# styles.py
get_style(dark: bool = False) -> str   # returns MAIN_STYLE or DARK_STYLE

# Apply app-wide (no restart needed):
QApplication.instance().setStyleSheet(get_style(dark=True))
```

Theme is persisted to `app_settings` under key `"theme"` (`"light"` or `"dark"`).
`MainWindow.__init__` reads this and applies the stylesheet before building the UI.
`SettingsDialog` previews the theme live as the checkbox is toggled.

Dark palette key colors: bg `#1e2228`, card `#272c35`, border `#343b47`,
text `#e8ecf1`, accent `#3d9de8`, header `#5aa8f0`.

---

## PDF Export Package

`export/pdf_writer.py` generates professional PDFs using **reportlab**:

| Function | Output file | Contents |
|---|---|---|
| `write_cover_sheet_pdf()` | `00_Cover_Sheet.pdf` | VA blue banner, veteran info table, claims table with Caluza status, document inventory |
| `write_claim_summary_pdf()` | `Claim_Summary.pdf` | Per-claim: metadata, triangle leg-by-leg status, denial risk flags (color-coded), notes |
| `write_forms_checklist_pdf()` | `Required_Forms_Checklist.pdf` | Primary / per-claim / TDIU / buddy / appeal forms with checkboxes |

`package_builder.py` calls these PDF writers first; if `reportlab` raises, it
falls back to the legacy `.txt` writers (kept in the same file).

Package folder structure:
```
{VeteranName}_{timestamp}/
  00_Cover_Sheet.pdf
  01_DD214/
  02_ServiceTreatmentRecords/
  03_Claims/{ConditionName}_DC{code}/
      Claim_Summary.pdf
      Diagnosis_Evidence/
      InService_Evidence/
      Nexus_Letter/
      Supporting_Evidence/
  04_Forms/Required_Forms_Checklist.pdf
  05_Buddy_Statements/
  06_Other_Medical_Records/
```

---

## Settings Dialog

`ui/dialogs/settings_dialog.py` — opened by the **Settings** sidebar button.

| Setting | DB key | Default |
|---|---|---|
| Theme | `theme` | `"light"` |
| Tesseract path | `tesseract_path` | `""` (auto-detect) |
| Default export dir | `default_export_dir` | `""` (uses `data/exports/`) |
| Ingestion workers | `max_ingestion_workers` | `"4"` |

All settings persist via `get_setting()` / `set_setting()` in `schema.py`.

---

## Domain Vocabulary

| Term | Meaning |
|------|---------|
| Caluza Triangle | The 3 required elements: current diagnosis + in-service event + nexus |
| Nexus | Medical opinion linking current disability to in-service event ("at least as likely as not") |
| VASRD | VA Schedule for Rating Disabilities — ~400 diagnostic codes with 0–100% ratings |
| PACT Act | 2022 law adding presumptive conditions for burn pit / Agent Orange / Gulf War exposure |
| Presumptive | Conditions automatically service-connected without a nexus letter |
| Secondary | Condition caused/aggravated by an already service-connected condition |
| TDIU | Total Disability Individual Unemployability (38 CFR § 4.16) — 100% pay at less than 100% rating |
| DBQ | Disability Benefits Questionnaire — VA form completed by treating physician |
| STR | Service Treatment Records |
| DD-214 | Certificate of Release or Discharge from Active Duty |
| ITF | Intent to File — establishes effective date up to 1 year before formal claim |
| C&P Exam | Compensation & Pension exam — VA medical evaluation for rating decisions |

---

## Common Tasks

### Add a new dialog
1. Create `app/ui/dialogs/my_dialog.py` extending `QDialog`
2. Accept `claim` + `veteran` in `__init__`; call `super().__init__(parent)`
3. In `claim_panel.py`: import, add a button in the status row, connect to a handler that calls `MyDialog(claim, veteran=self._veteran, parent=self).exec()`

### Add a new Claim field
1. Add column to `_CREATE_CLAIMS` DDL in `schema.py`
2. Add `if from_version < N` migration block; bump `CURRENT_VERSION`
3. Add field to `Claim` dataclass in `core/claim.py` with default
4. Add to `Claim.from_row()` with the `if "col" in keys` guard
5. Add to `_params(c)` tuple in `claim_repo.py` (INSERT and UPDATE)
6. Add UI widget in `claim_panel.py` `_build_ui()`, load in `_load_claim()`, clear in `_clear_editor()`, read in `_on_save()`

### Add a new app setting
1. Use `get_setting("my_key", "default")` / `set_setting("my_key", value)` anywhere
2. Add a row to `SettingsDialog._build_ui()` and wire in `_load_settings()` + `_save_all()`

### Extend the condition scanner
- Add keywords to `CONDITION_KEYWORDS` in `condition_scanner.py` (VASRD code → list of phrases)
- Add negation/positive patterns to `context_analyzer.py` pattern banks
- Adjust `DOC_TYPE_WEIGHTS` in `config.py` if a new document type is added

### Run all tests
```bash
cd va_claims_manager
python -m pytest tests/ -v
```
