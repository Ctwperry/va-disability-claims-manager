"""
C&P Exam Preparation Sheet dialog.

Generates a per-claim preparation guide for the Compensation & Pension exam,
covering what the examiner evaluates, symptoms to describe, nexus language,
and body-system-specific tips drawn from 38 CFR Part 4 and VA practice.
"""
import html
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QApplication, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# ---------------------------------------------------------------------------
# Guidance data by body system
# ---------------------------------------------------------------------------

_GUIDANCE: dict[str, dict] = {
    "Musculoskeletal": {
        "examiner_focus": [
            "Range of motion (ROM) measured with a goniometer — every degree matters",
            "Painful motion rule (38 CFR § 4.59): pain during movement = minimum 10% rating regardless of ROM",
            "Flare-up frequency, duration, triggers, and severity",
            "Functional loss: activities you cannot or must avoid doing",
            "Muscle strength, atrophy, and spasm",
            "X-ray / MRI evidence of degenerative changes",
            "Effect on work capacity (standing, lifting, bending, prolonged sitting)",
        ],
        "describe_these": [
            "Your WORST days, not your average — describe flare-ups in full detail",
            "Pain level 0–10 at rest, during motion, and at its worst",
            "Activities limited or avoided: sitting, standing, walking, climbing stairs, lifting",
            "Sleep disruption caused by pain",
            "Compensation behaviors: limping, guarding, using a cane or brace",
            "Pain medication taken and its side effects on daily functioning",
            "How the condition has worsened progressively since service",
        ],
        "avoid": [
            '"I manage fine" — describe your functional loss, not your coping strategies',
            "Do not minimize by saying you've adapted; say what you've had to STOP doing",
            '"It\'s not that bad today" — describe your baseline AND your worst-case days',
        ],
        "nexus": (
            "Your nexus letter must state:\n\n"
            '"It is at least as likely as not that the veteran\'s current [condition] '
            "was caused by / is a direct result of [specific in-service event documented in STRs dated ___].\"\n\n"
            "For secondary conditions add: \"The veteran's [condition] is secondary to and caused or "
            'aggravated by service-connected [primary condition]."'
        ),
        "dbq_tip": (
            "Request your doctor complete the DBQ specific to your joint/spine. "
            "Key sections: ROM measurements, painful motion, functional loss during flare-ups. "
            "The VA rates the worst documented ROM, not just the exam-day reading."
        ),
    },
    "Mental Health": {
        "examiner_focus": [
            "Occupational impairment: ability to maintain employment, follow instructions, handle workplace stress",
            "Social impairment: relationships, isolation, avoidance of people or situations",
            "Symptom frequency and severity: panic attacks, flashbacks, nightmares, hypervigilance",
            "Five functional domains (VA transitioning to domain-based rating):",
            "  1. Cognition — memory, concentration, processing speed",
            "  2. Interpersonal relationships — conflict, withdrawal, intimacy",
            "  3. Task completion — ability to finish work and daily tasks",
            "  4. Self-care / independent living",
            "  5. Social and occupational adaptability",
            "Medication history, hospitalizations, and crisis interventions",
        ],
        "describe_these": [
            "How symptoms interfere with work: absences, inability to concentrate, conflict with coworkers",
            "Specific triggers you avoid and WHY (crowds, driving, certain sounds, dates)",
            "Sleep disturbances: nightmares, insomnia, hypervigilance at night",
            "Panic attacks: frequency, duration, physical symptoms (heart racing, sweating, can't breathe)",
            "Social withdrawal: events you no longer attend, relationships damaged or ended",
            "Times you had to leave a situation or were unable to function",
            "Impact on family relationships and daily self-care",
        ],
        "avoid": [
            "Do NOT put on a brave face — the examiner rates what you REPORT",
            '"I\'m coping" without explaining the enormous effort and cost of that coping',
            "Downplaying duration — describe how long symptoms have persisted since service",
            "Leaving out Military Sexual Trauma (MST) if relevant — it is protected and confidential",
        ],
        "nexus": (
            "For PTSD, clearly identify the specific in-service stressor event.\n\n"
            "For other mental health conditions:\n"
            '"It is at least as likely as not that the veteran\'s [diagnosis] '
            "was caused or aggravated by the in-service stressor of [specific event or chronic stress].\"\n\n"
            "For secondary mental health (e.g., depression secondary to chronic pain):\n"
            '"The veteran\'s [depression/anxiety] is secondary to and caused by '
            'service-connected [condition] and the functional limitations it imposes."'
        ),
        "dbq_tip": (
            "The PTSD DBQ (or Mental Disorders DBQ for non-PTSD) asks about occupational and social "
            "impairment. Complete the Global Assessment of Functioning (GAF) estimate with your provider. "
            "A score of 50 or below generally supports a 70% rating."
        ),
    },
    "Respiratory": {
        "examiner_focus": [
            "Pulmonary function tests: FEV1, FVC, FEV1/FVC ratio — these determine the rating level",
            "CPAP/BiPAP prescription (sleep apnea: 50% rating requires CPAP prescription)",
            "Frequency of incapacitating episodes per year",
            "Oxygen supplementation requirement",
            "Exercise tolerance and dyspnea (shortness of breath) on exertion",
            "Environmental triggers: dust, smoke, cold air, chemicals",
        ],
        "describe_these": [
            "Breathing difficulty during normal activities: walking stairs, yard work, carrying groceries",
            "Nighttime symptoms: witnessed apnea episodes, waking gasping, morning headaches",
            "CPAP usage: compliance percentage, does it help, do you tolerate it",
            "Asthma attacks: frequency, severity, ER visits, rescue inhaler use",
            "Workplace limitations caused by breathing or fatigue from poor sleep",
            "Fatigue during the day due to non-restorative sleep from apnea",
        ],
        "avoid": [
            "Do NOT skip mentioning your CPAP prescription — it is the basis for the 50% rating",
            "Do not underreport nighttime episodes; bring your CPAP data/compliance report",
            '"It\'s controlled with medication" — note the medication required and its side effects',
        ],
        "nexus": (
            '"It is at least as likely as not that the veteran\'s [sleep apnea / asthma / COPD] '
            "was incurred in or caused by exposure to [burn pits / military industrial chemicals / "
            "sand/dust/particulate matter] during service at [location and dates].\"\n\n"
            "For PACT Act conditions: No nexus letter required — condition is presumptive."
        ),
        "dbq_tip": (
            "For sleep apnea, the Sleep Apnea DBQ requires documentation of your CPAP prescription. "
            "Bring a copy of the prescription to the exam. "
            "For asthma/COPD, bring your most recent pulmonary function test results."
        ),
    },
    "Cardiovascular": {
        "examiner_focus": [
            "METs (metabolic equivalents of task): exercise capacity is the primary rating determinant",
            "Ejection fraction percentage (heart failure)",
            "Blood pressure readings (multiple readings) — diastolic pressure is key for hypertension",
            "Chest pain on exertion (angina symptoms)",
            "Congestive heart failure symptoms: leg swelling, shortness of breath lying flat",
            "Number and type of medications required to control the condition",
        ],
        "describe_these": [
            "Activities that cause chest pain, shortness of breath, or palpitations",
            "Walking distance or stairs you can manage before symptoms appear",
            "Most recent blood pressure readings from your doctor",
            "Medication side effects: fatigue, dizziness, cold extremities, cough",
            "How cardiac symptoms limit your ability to work or perform daily tasks",
            "Any hospitalizations, stents, or cardiac procedures",
        ],
        "avoid": [
            "Do not report only resting blood pressure — describe exertional symptoms",
            '"My blood pressure is controlled" without noting it requires daily medication to achieve that',
        ],
        "nexus": (
            "For hypertension in Vietnam veterans: PRESUMPTIVE under Agent Orange — no nexus needed.\n\n"
            "For others:\n"
            '"It is at least as likely as not that the veteran\'s hypertension / [condition] '
            "was caused by the chronic physiological stress and physical demands of "
            '[combat / military occupational specialty] during service."'
        ),
        "dbq_tip": (
            "The Hypertension DBQ focuses on diastolic readings. Bring a log of your blood pressure "
            "readings over the past few months. For ischemic heart disease, the examiner will request "
            "an exercise stress test result and current METs capacity."
        ),
    },
    "Sensory (Vision/Hearing)": {
        "examiner_focus": [
            "Audiogram: pure-tone thresholds at 500, 1000, 2000, 3000, and 4000 Hz",
            "Speech discrimination (word recognition) percentage score",
            "Maryland CNC word recognition test results",
            "Tinnitus: constant vs. intermittent, bilateral vs. unilateral, pitch",
            "Visual acuity with and without correction",
            "Visual field defects and contrast sensitivity",
        ],
        "describe_these": [
            "Tinnitus: the sound it makes, when it is loudest, how it disrupts sleep and concentration",
            "Difficulty understanding speech in noisy environments (restaurants, meetings)",
            "Frequency of asking people to repeat themselves",
            "TV / phone volume level you require compared to others",
            "Hearing aid usage and whether it fully resolves the problem",
            "Vision changes: glare sensitivity, night vision loss, difficulty reading",
        ],
        "avoid": [
            "Do not rely solely on the audiogram — describe the FUNCTIONAL impact on your daily life",
            "Tinnitus is rated flat 10% but must be claimed — mention it even if it seems minor",
            '"My hearing aids fix it" — describe residual difficulties even with aids',
        ],
        "nexus": (
            '"It is at least as likely as not that the veteran\'s bilateral hearing loss '
            "and/or tinnitus was caused by occupational noise exposure during military service, "
            "specifically [weapons qualification on the range / aircraft engine noise / "
            'IED blast exposure / use of heavy equipment without adequate hearing protection]."'
        ),
        "dbq_tip": (
            "Hearing loss and tinnitus have separate DBQs. Both can be claimed simultaneously. "
            "The audiologist must be licensed and the test must be the controlled audiometric exam — "
            "a smartphone hearing test is not sufficient for VA purposes."
        ),
    },
    "Neurological": {
        "examiner_focus": [
            "Headache / migraine frequency: days per month you are incapacitated",
            "Neurological deficits: numbness, tingling, weakness in extremities",
            "Seizure type, frequency, and post-ictal recovery time",
            "Cognitive impairment: memory gaps, word-finding problems, processing speed",
            "TBI symptom checklist and documented loss of consciousness (LOC) duration",
            "Effect on driving, employment, and independent living",
        ],
        "describe_these": [
            "Headache frequency: days per month where you cannot work or function",
            "Migraine triggers and duration of each episode (include prodrome and recovery)",
            "Sensory symptoms: what they feel like and whether they are progressing",
            "TBI history: exact date, mechanism (blast, blunt trauma), LOC duration, post-concussion symptoms",
            "Memory failures that affect work or safety (missed appointments, forgotten tasks)",
            "Whether you can safely drive; if not, document this explicitly",
        ],
        "avoid": [
            "Do not minimize headache severity — if migraines prevent you from working, say so clearly",
            "Do not omit TBI if relevant — even a 'mild' TBI with ongoing symptoms is ratable",
        ],
        "nexus": (
            '"The veteran\'s migraines / neuropathy / [condition] are at least as likely as not '
            "caused by [TBI sustained on [date] / acoustic trauma from blast exposure / "
            'cervical spine injury] incurred during military service."'
        ),
        "dbq_tip": (
            "The Headache DBQ specifically asks for frequency of prostrating attacks. "
            "A prostrating attack means you are unable to perform normal activities. "
            "Document 1–2 per month = 30%, more than once per month = 50%."
        ),
    },
    "Skin": {
        "examiner_focus": [
            "Total body surface area (BSA%) affected — especially at its worst",
            "Frequency of incapacitating episodes per year requiring bed rest or hospitalization",
            "Systemic therapy required: immunosuppressants, biologics, steroids",
            "Constant vs. episodic nature of the condition",
            "Location, size, and depth of scars",
        ],
        "describe_these": [
            "Body surface area affected, especially on visible or exposed areas",
            "Itching, burning, or pain that disrupts sleep or concentration",
            "Flare-up frequency and duration requiring prescription treatment",
            "All medications tried: topical and systemic, and their side effects",
            "Emotional or social impact of visible skin conditions",
            "Photos of flare-ups (bring to the appointment if possible)",
        ],
        "avoid": [
            "Do not present only your good days — show documentation of flare-ups",
            "Document all treatment attempts, especially if multiple treatments have failed",
        ],
        "nexus": (
            '"It is at least as likely as not that the veteran\'s [dermatitis / psoriasis / eczema / '
            "burn scar] was caused by or aggravated by [chemical exposure / physical irritants / "
            'toxic substance / chronic stress] encountered during active duty service."'
        ),
        "dbq_tip": (
            "The Skin DBQ asks for the percentage of exposed skin affected and frequency of "
            "incapacitating episodes. Bring dated photos showing the condition at its worst. "
            "Note whether systemic (whole-body) treatment is required — this drives higher ratings."
        ),
    },
    "Digestive": {
        "examiner_focus": [
            "Frequency and severity of incapacitating episodes",
            "Weight loss or nutritional deficiency",
            "Surgical history and post-operative complications",
            "Diarrhea / constipation frequency and impact on daily schedule",
            "Dietary restrictions required",
        ],
        "describe_these": [
            "How often symptoms prevent you from leaving home or working",
            "Dietary restrictions you must follow and their social impact",
            "Urgency episodes — inability to control bowel function",
            "Weight loss over time and current BMI",
            "Impact on work schedule: needing access to bathroom constantly",
        ],
        "avoid": [
            '"I manage with diet" — describe what you cannot eat and how that limits your life',
            "Minimizing urgency episodes — these are highly relevant to the rating",
        ],
        "nexus": (
            "For Gulf War veterans: IBS and functional GI disorders are presumptive — no nexus needed.\n\n"
            "For others:\n"
            '"It is at least as likely as not that the veteran\'s [condition] was caused by '
            '[service-related stress / medication use during service / in-service gastrointestinal illness]."'
        ),
        "dbq_tip": (
            "The GI DBQ series has separate forms for different conditions (GERD, IBS, etc.). "
            "Document incapacitating episodes specifically — the number per year drives the rating. "
            "Bring records of ER visits or days missed from work due to GI symptoms."
        ),
    },
}

_GUIDANCE_DEFAULT = {
    "examiner_focus": [
        "Current diagnosis confirmed by a licensed provider",
        "Severity of symptoms and functional limitations",
        "Frequency and duration of symptomatic episodes",
        "Treatment history and response to each treatment tried",
        "Impact on occupational and daily activities",
    ],
    "describe_these": [
        "Your worst days — severity, frequency, and what you cannot do",
        "How symptoms have progressed or worsened since military service",
        "Medications and their side effects on daily functioning",
        "Work tasks or activities you have had to stop or significantly limit",
        "Any hospitalizations, ER visits, or specialist referrals",
    ],
    "avoid": [
        '"I\'m managing fine" — describe functional loss, not how you cope with it',
        "Presenting only your best days — the rating reflects your average impact",
    ],
    "nexus": (
        "The critical phrase every nexus letter must contain:\n\n"
        '"It is at least as likely as not that the veteran\'s [condition] '
        "was caused by / is a result of [in-service event or exposure].\"\n\n"
        "The standard of proof is 50% or greater probability. "
        "The benefit of the doubt goes to the veteran (38 CFR § 3.102)."
    ),
    "dbq_tip": (
        "Ask your private doctor to complete the DBQ for your specific condition. "
        "DBQs are available free at the VA website. A well-completed private DBQ "
        "from your treating provider carries significant weight with the rater."
    ),
}

# ---------------------------------------------------------------------------
# Condition-specific tips for the most common VASRD codes
# ---------------------------------------------------------------------------

_CODE_TIPS: dict[str, str] = {
    "9411": (
        "PTSD STRESSOR REQUIREMENT: You must identify at least one in-service stressor event. "
        "For combat PTSD, your service records (deployment orders, awards, unit records) serve as "
        "corroboration. For MST or non-combat stressors, buddy statements and personnel record "
        "'markers' (sudden performance drops, requests for transfer) are accepted."
    ),
    "6847": (
        "SLEEP APNEA: A CPAP prescription alone is sufficient for a 50% rating. "
        "Bring the prescription document to the C&P exam. If you require supplemental oxygen "
        "with CPAP or have chronic respiratory failure, you may qualify for 100%."
    ),
    "6260": (
        "TINNITUS: Currently rated flat 10% under DC 6260 regardless of whether it is in one "
        "or both ears. Proposed VA regulatory changes may tie future tinnitus ratings to underlying "
        "hearing loss. File this claim now to lock in your effective date."
    ),
    "7101": (
        "HYPERTENSION: Vietnam veterans — this is NOW presumptive under Agent Orange. "
        "No nexus letter required. For others: document your diastolic readings. "
        "Diastolic ≥ 130 = 60%, 120–129 = 40%, 110–119 = 20%, 100–109 = 10%."
    ),
    "5242": (
        "CERVICAL SPINE: Flexion to 15° or less = 100%; to 30° or less = 40%; to 40° = 30%. "
        "The 'painful arc' rule means if you have pain before reaching the normal endpoint, "
        "the painful point is your documented ROM. Bring your MRI or X-ray reports."
    ),
    "5243": (
        "INTERVERTEBRAL DISC SYNDROME: Incapacitating episodes matter here. "
        "Document how many episodes per year require bed rest. "
        "≥ 6 weeks total incapacity = 60%, 4–6 weeks = 40%, 2–4 weeks = 20%."
    ),
}


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class CPPrepDialog(QDialog):
    """Per-claim C&P Exam Preparation Sheet."""

    def __init__(self, claim, parent=None):
        super().__init__(parent)
        self._claim = claim
        self.setWindowTitle(f"C&P Exam Prep — {claim.condition_name}")
        self.setMinimumSize(740, 640)
        self.resize(780, 700)
        self._build_ui()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header banner
        header = QFrame()
        header.setStyleSheet("background: #1a3a5c; padding: 0;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 16)
        header_layout.setSpacing(4)

        title_lbl = QLabel("C&P Exam Preparation Sheet")
        title_lbl.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_lbl)

        sub_lbl = QLabel(
            f"Condition: {html.escape(self._claim.condition_name)}"
            + (f"  ·  VASRD Code: {html.escape(self._claim.vasrd_code)}" if self._claim.vasrd_code else "")
            + (f"  ·  {html.escape(self._claim.body_system)}" if self._claim.body_system else "")
        )
        sub_lbl.setStyleSheet("color: #a8c4e0; font-size: 13px;")
        header_layout.addWidget(sub_lbl)
        layout.addWidget(header)

        # Disclaimer
        disclaimer = QLabel(
            "  ⚠  This sheet is an organizational guide only. It is not legal advice. "
            "Always consult an accredited VSO or attorney for your specific claim."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(
            "background: #fff8e1; color: #7a5500; font-size: 12px; "
            "padding: 8px 16px; border-bottom: 1px solid #ffe082;"
        )
        layout.addWidget(disclaimer)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 20)
        content_layout.setSpacing(16)

        guidance = self._get_guidance()

        # Section: What the examiner looks for
        content_layout.addWidget(self._section(
            "What the Examiner Is Looking For",
            "#0d47a1", "#e3f0ff",
            guidance["examiner_focus"],
            bullet="◆",
        ))

        # Section: Symptoms to describe
        content_layout.addWidget(self._section(
            "Symptoms & Limitations to Describe at the Exam",
            "#1a7a4a", "#e8f5e9",
            guidance["describe_these"],
            bullet="✔",
        ))

        # Section: What to avoid saying
        content_layout.addWidget(self._section(
            "What NOT to Say or Do",
            "#b71c1c", "#ffebee",
            guidance["avoid"],
            bullet="✘",
        ))

        # Section: Nexus language
        content_layout.addWidget(self._text_section(
            "Nexus Letter Language",
            "#4a148c", "#f3e5f5",
            guidance["nexus"],
        ))

        # Section: DBQ tips
        if "dbq_tip" in guidance:
            content_layout.addWidget(self._text_section(
                "DBQ Tips for This Condition",
                "#e65100", "#fff3e0",
                guidance["dbq_tip"],
            ))

        # Section: Condition-specific tip if available
        code_tip = _CODE_TIPS.get(self._claim.vasrd_code or "")
        if code_tip:
            content_layout.addWidget(self._text_section(
                f"Important — VASRD Code {self._claim.vasrd_code} Specific Guidance",
                "#004d40", "#e0f2f1",
                code_tip,
            ))

        # Section: Caluza Triangle status summary
        content_layout.addWidget(self._caluza_summary())

        # Section: General tips (always shown)
        content_layout.addWidget(self._section(
            "General C&P Exam Tips (All Claims)",
            "#37474f", "#f5f5f5",
            [
                "Arrive early, bring ALL medical records, your DBQ, and any buddy statements",
                "The exam typically lasts 20–45 minutes — do not rush your answers",
                "Describe your symptoms on your WORST days, not the day of the exam",
                "You may bring a support person (they cannot speak for you during the exam)",
                "You are entitled to a copy of the C&P report — request it via FOIA after the exam",
                "If the opinion is unfavorable, you can rebut it with an Independent Medical Exam (IME)",
                "Do NOT exaggerate, but do NOT minimize — be precise and complete",
                'The magic standard: "at least as likely as not" (50%+ probability) is all you need',
            ],
            bullet="→",
        ))

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Footer buttons
        footer = QFrame()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)

        btn_copy = QPushButton("Copy All to Clipboard")
        btn_copy.setFixedWidth(180)
        btn_copy.clicked.connect(self._copy_all)
        footer_layout.addWidget(btn_copy)
        footer_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setFixedWidth(90)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)
        layout.addWidget(footer)

    # ------------------------------------------------------------------
    # Widget builders
    # ------------------------------------------------------------------

    def _section(self, title: str, title_color: str, bg_color: str,
                 items: list[str], bullet: str = "•") -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {bg_color}; border-radius: 8px; "
            f"border: 1px solid {title_color}40; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        hdr = QLabel(title)
        hdr.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {title_color}; "
            "border: none; background: transparent;"
        )
        layout.addWidget(hdr)

        for item in items:
            lbl = QLabel(f"  {bullet}  {html.escape(item)}")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "font-size: 12px; color: #333; border: none; "
                "background: transparent; padding: 1px 0;"
            )
            layout.addWidget(lbl)

        return frame

    def _text_section(self, title: str, title_color: str, bg_color: str, text: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {bg_color}; border-radius: 8px; "
            f"border: 1px solid {title_color}40; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        hdr = QLabel(title)
        hdr.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {title_color}; "
            "border: none; background: transparent;"
        )
        layout.addWidget(hdr)

        # Render each line separately so word wrap works correctly
        for line in text.split("\n"):
            lbl = QLabel(html.escape(line) if line.strip() else " ")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                "font-size: 12px; color: #333; border: none; "
                "background: transparent; padding: 0;"
            )
            layout.addWidget(lbl)

        return frame

    def _caluza_summary(self) -> QFrame:
        c = self._claim
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        hdr = QLabel("Your Caluza Triangle Status")
        hdr.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #333; "
            "border: none; background: transparent;"
        )
        layout.addWidget(hdr)

        def _leg(checked: bool, label: str, detail: str):
            icon = "✔" if checked else "✗"
            color = "#1a7a4a" if checked else "#c0392b"
            lbl = QLabel(f"  {icon}  <b>{html.escape(label)}</b>"
                         + (f"  —  {html.escape(detail)}" if detail else ""))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"font-size: 12px; color: {color}; border: none; background: transparent;"
            )
            return lbl

        layout.addWidget(_leg(c.has_diagnosis, "Leg 1: Current Diagnosis", c.diagnosis_source))
        layout.addWidget(_leg(c.has_inservice_event, "Leg 2: In-Service Event", c.inservice_source))
        layout.addWidget(_leg(c.has_nexus, "Leg 3: Medical Nexus", c.nexus_source))

        if not c.triangle_complete:
            missing = []
            if not c.has_diagnosis:
                missing.append("a formal diagnosis from a licensed provider")
            if not c.has_inservice_event:
                missing.append("documentation of the in-service event in your STRs")
            if not c.has_nexus:
                missing.append("a nexus letter from a medical professional")
            note = QLabel(
                "  ⚠  Still needed before filing: " + "; ".join(missing) + "."
            )
            note.setWordWrap(True)
            note.setStyleSheet(
                "font-size: 12px; color: #b8610a; font-style: italic; "
                "border: none; background: transparent; margin-top: 4px;"
            )
            layout.addWidget(note)

        return frame

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_guidance(self) -> dict:
        body_system = self._claim.body_system or ""
        # Try exact match first, then partial
        guidance = _GUIDANCE.get(body_system)
        if not guidance:
            for key in _GUIDANCE:
                if key.lower() in body_system.lower() or body_system.lower() in key.lower():
                    guidance = _GUIDANCE[key]
                    break
        return guidance or _GUIDANCE_DEFAULT

    def _copy_all(self):
        """Copy the full prep sheet as plain text to the clipboard."""
        c = self._claim
        guidance = self._get_guidance()
        lines = [
            "=" * 70,
            f"C&P EXAM PREPARATION SHEET",
            f"Condition: {c.condition_name}",
        ]
        if c.vasrd_code:
            lines.append(f"VASRD Code: {c.vasrd_code}")
        if c.body_system:
            lines.append(f"Body System: {c.body_system}")
        lines += ["=" * 70, ""]

        def _block(title, items):
            lines.append(title.upper())
            lines.append("-" * 50)
            for item in items:
                lines.append(f"  • {item}")
            lines.append("")

        _block("What the Examiner Is Looking For", guidance["examiner_focus"])
        _block("Symptoms & Limitations to Describe", guidance["describe_these"])
        _block("What NOT to Say or Do", guidance["avoid"])

        lines += [
            "NEXUS LETTER LANGUAGE",
            "-" * 50,
            guidance["nexus"],
            "",
        ]

        if "dbq_tip" in guidance:
            lines += ["DBQ TIPS", "-" * 50, guidance["dbq_tip"], ""]

        code_tip = _CODE_TIPS.get(c.vasrd_code or "")
        if code_tip:
            lines += [
                f"VASRD {c.vasrd_code} SPECIFIC GUIDANCE",
                "-" * 50,
                code_tip,
                "",
            ]

        lines += [
            "CALUZA TRIANGLE STATUS",
            "-" * 50,
            f"  {'✔' if c.has_diagnosis else '✗'}  Leg 1: Diagnosis  {c.diagnosis_source}",
            f"  {'✔' if c.has_inservice_event else '✗'}  Leg 2: In-Service Event  {c.inservice_source}",
            f"  {'✔' if c.has_nexus else '✗'}  Leg 3: Nexus  {c.nexus_source}",
            "",
            "=" * 70,
            "Generated by VA Disability Claims Manager",
            "NOT legal advice. Consult an accredited VSO or attorney.",
        ]

        QApplication.clipboard().setText("\n".join(lines))
