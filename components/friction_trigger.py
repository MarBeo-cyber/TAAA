"""
TAAA — Friction Trigger Engine (Integrated)

Integrates ChatGPT's SARS score (adopted with credit) with:
  - M1 Registry for domain_distance computation
  - Bilateral consent gating
  - MAAA bridge for stress_load (real-time biometrics)
  - Signal extractor for computing scores from raw signals

SARS formula, as specified in Working Paper Addendum v0.5 §4:
  SARS = ambiguity*0.25 + domain*0.30 + consequence*0.20
       + confidence_mismatch*0.15 + stress*0.10

(The earlier prototype used 0.25/0.25/0.25/0.15/0.10. The code now matches the
addendum rather than the prototype.)

M2 is friction-triggered, not time-triggered.
It activates when the system detects cognitive friction:
  schema ambiguity + action relevance + mismatch risk + uncertainty/overconfidence

The scores are NOT hand-coded by the developer.
They are computed from real signals by SignalExtractor.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
from typing import Optional

from core.bilateral_consent import CONSENT_MANAGER

logger = logging.getLogger("taaa.friction_trigger")


# ── Models (adopted from ChatGPT prototype, extended) ────────────────────────

class LearningMode(str, Enum):
    SANDBOX     = "sandbox"
    VALIDATION  = "validation"
    OPERATIONAL = "operational"


class RiskClass(str, Enum):
    NONE                        = "none"
    IGNORANCE                   = "ignorance"
    ACTIVE_INTERFERENCE         = "active_interference"
    UNRESOLVED_AMBIGUITY        = "unresolved_ambiguity"
    HIGH_CONSEQUENCE_SCHEMA_GAP = "high_consequence_schema_gap"


class TriggerState(str, Enum):
    """Three states, as specified in Addendum v0.5 §5.

    MONITORING is the L2 band: the system has noticed friction but does not
    escalate to a cognitive-layer bridge. It exists because the realistic
    intercultural cases measured through TAAAAgent land between 0.35 and the
    0.55 escalation threshold — previously they were reported as INACTIVE,
    which is not what the pipeline was doing.
    """
    INACTIVE   = "inactive"
    MONITORING = "monitoring"
    ACTIVE     = "active"


class ConfidenceLevel(str, Enum):
    C0 = "C0_unvalidated"
    C1 = "C1_bootstrap"
    C2 = "C2_operational_lite"
    C3 = "C3_domain_validated"
    C4 = "C4_expert_validated"


@dataclass
class CognitiveEvent:
    """
    Input to the friction trigger engine.
    Scores are computed by SignalExtractor from real signals,
    NOT hand-coded by the developer.
    """
    text: str
    domain: str
    subject_id: str = "anonymous"

    # Signal-extracted scores (all 0.0–1.0)
    ambiguity_score: float = 0.0      # Computed by SignalExtractor
    domain_distance: float = 0.0      # Computed from M1 registry
    consequence_score: float = 0.0    # Computed from domain + context
    user_confidence: float = 0.5      # Computed from behavioral signals
    system_confidence: float = 0.5    # Computed from M1/M2 match
    stress_load: float = 0.0          # From MAAA bridge / PAAA

    mode: LearningMode = LearningMode.OPERATIONAL
    session_id: Optional[str] = None  # Bilateral consent session

    def clamp(self) -> "CognitiveEvent":
        for k in ["ambiguity_score", "domain_distance", "consequence_score",
                  "user_confidence", "system_confidence", "stress_load"]:
            setattr(self, k, max(0.0, min(1.0, float(getattr(self, k)))))
        return self


@dataclass
class TriggerResult:
    score: float
    state: TriggerState
    reasons: list[str] = field(default_factory=list)
    m2_recommended: bool = False
    consent_checked: bool = False
    consent_level: str = "unknown"


@dataclass
class SchemaHypothesis:
    id: str
    label: str
    domain: str
    description: str
    confidence_level: ConfidenceLevel = ConfidenceLevel.C0
    evidence: list[str] = field(default_factory=list)
    version: int = 1
    created_at: float = field(default_factory=time.time)


@dataclass
class M2Decision:
    trigger: TriggerResult
    risk_class: RiskClass
    recommendation: str
    operational_update_allowed: bool
    sandbox_update_created: bool
    proposed_schema: Optional[SchemaHypothesis] = None
    notes: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def summary(self) -> str:
        return (f"[M2] trigger={self.trigger.state.value} "
                f"SARS={self.trigger.score:.2f} "
                f"risk={self.risk_class.value} "
                f"→ {self.recommendation}")


# ── Friction Trigger Engine (adopted + extended) ──────────────────────────────

class FrictionTriggerEngine:
    """
    SARS score implementation, adopted from ChatGPT M2 prototype.
    Extended with M1-aware domain_distance and consent gating.

    Threshold tuning. These numbers are inside the range the pipeline can
    actually produce; the previous docstring advertised 0.62 / 0.75 against a
    measured ceiling of 0.52. Measured by tests/test_reachability.py, which
    sweeps SignalExtractor output through TAAAAgent and fails if the reachable
    maximum drops below the conservative threshold:

      0.45 = sensitive    (catches the mid-band intercultural cases)
      0.55 = default      (Addendum v0.5 §4 escalation threshold)
      0.65 = conservative (fewer escalations, higher precision)

    Reachable SARS range through TAAAAgent, measured over the sweep in
    tests/test_reachability.py: 0.000 – 0.722.
    """

    DEFAULT_THRESHOLD   = 0.55   # Addendum v0.5 §4
    MONITORING_THRESHOLD = 0.35  # L2 observation band floor

    WEIGHTS = {
        "ambiguity":           0.25,
        "domain":              0.30,
        "consequence":         0.20,
        "confidence_mismatch": 0.15,
        "stress":              0.10,
    }

    def __init__(self, threshold: float = DEFAULT_THRESHOLD,
                 monitoring_threshold: float = MONITORING_THRESHOLD):
        self.threshold = threshold
        self.monitoring_threshold = min(monitoring_threshold, threshold)

    def score(self, event: CognitiveEvent) -> TriggerResult:
        event = event.clamp()
        mismatch = max(0.0, event.user_confidence - event.system_confidence)

        sars = (
            self.WEIGHTS["ambiguity"]           * event.ambiguity_score +
            self.WEIGHTS["domain"]              * event.domain_distance +
            self.WEIGHTS["consequence"]         * event.consequence_score +
            self.WEIGHTS["confidence_mismatch"] * mismatch +
            self.WEIGHTS["stress"]              * event.stress_load
        )

        reasons = []
        if event.ambiguity_score     >= 0.60: reasons.append("semantic_ambiguity")
        if event.domain_distance     >= 0.60: reasons.append("domain_distance")
        if event.consequence_score   >= 0.70: reasons.append("high_consequence")
        if mismatch                  >= 0.35: reasons.append("confidence_mismatch")
        if event.stress_load         >= 0.65: reasons.append("stress_load")

        # Consent check for outward monitoring
        consent_level = "none"
        consent_checked = False
        if event.session_id:
            session = CONSENT_MANAGER.get_session(event.session_id)
            if session:
                consent_level = session.consent_level.value
                consent_checked = True

        active = sars >= self.threshold
        if active:
            state = TriggerState.ACTIVE
        elif sars >= self.monitoring_threshold:
            state = TriggerState.MONITORING
        else:
            state = TriggerState.INACTIVE

        return TriggerResult(
            score=round(sars, 4),
            state=state,
            reasons=reasons,
            m2_recommended=active,
            consent_checked=consent_checked,
            consent_level=consent_level,
        )


# ── Schema Risk Classifier (adopted from ChatGPT) ─────────────────────────────

class SchemaRiskClassifier:
    """
    Classifies the type of schema risk.
    Preserves the ignorance/interference distinction central to TAAA.
    """

    # SignalExtractor's user_confidence floor, with the behavioural signals the
    # agent actually supplies (speech_hesitation=0, gaze_dwell_ms=0), is
    #     0.10*0.65 + 1.0*0.20 + 1.0*0.15 = 0.415
    # The old cut-off of 0.35 was therefore below the floor and IGNORANCE — half
    # of the framework's headline distinction — could not be produced at all.
    # 0.45 sits just above the floor, so the band is narrow but real.
    IGNORANCE_CONFIDENCE_MAX = 0.45

    def classify(self, event: CognitiveEvent) -> RiskClass:
        event = event.clamp()
        mismatch = max(0.0, event.user_confidence - event.system_confidence)

        # High consequence + ambiguity or domain gap
        if (event.consequence_score >= 0.80 and
                (event.ambiguity_score >= 0.55 or event.domain_distance >= 0.55)):
            return RiskClass.HIGH_CONSEQUENCE_SCHEMA_GAP

        # Active interference: high user confidence but wrong domain
        if mismatch >= 0.35 and event.domain_distance >= 0.50:
            return RiskClass.ACTIVE_INTERFERENCE

        # Pure ambiguity
        if event.ambiguity_score >= 0.65:
            return RiskClass.UNRESOLVED_AMBIGUITY

        # Ignorance: low user confidence (knows they don't know)
        if event.user_confidence <= self.IGNORANCE_CONFIDENCE_MAX:
            return RiskClass.IGNORANCE

        return RiskClass.NONE


# ── Safety Governor (adopted + extended with domain list) ─────────────────────

class SafetyGovernor:
    """
    Blocks operational learning in high-risk domains.
    Extended with TAAA-specific medical/privacy domains.
    """

    HIGH_RISK_DOMAINS = {
        "medical", "clinical", "legal", "contract", "finance",
        "emergency", "infrastructure", "cybersecurity",
        "engineering_safety", "public_safety",
        "psychiatric", "pharmaceutical", "judicial",
    }

    def is_high_risk(self, domain: str) -> bool:
        return domain.lower().strip() in self.HIGH_RISK_DOMAINS

    def operational_update_allowed(self, event: CognitiveEvent) -> bool:
        """May this event update *operational* M2 topology? Never in OPERATIONAL
        mode — that is the architectural invariant from PATCH_NOTES_M2_GATED."""
        if event.mode == LearningMode.OPERATIONAL:
            return False
        if self.is_high_risk(event.domain):
            return False
        return event.mode in {LearningMode.SANDBOX, LearningMode.VALIDATION}

    def sandbox_capture_allowed(self, event: CognitiveEvent) -> bool:
        """May we record a C0 sandbox hypothesis for later human review?

        This is a strictly weaker permission than operational_update_allowed.
        A sandbox hypothesis is not memory: it enters GatedM2Memory at C0 and
        publish_operational() raises PermissionError below C3. Recording one
        from an operational observation is therefore safe, and is what makes the
        proposal queue have anything in it — previously this branch was gated on
        operational_update_allowed, which is always False in OPERATIONAL mode,
        so GatedM2Memory.create_sandbox was unreachable from TAAAAgent.

        The one exception: in a high-risk domain even an unreviewed record of a
        consequential event is withheld unless the session is explicitly a
        sandbox/validation session.
        """
        if self.is_high_risk(event.domain):
            return event.mode in {LearningMode.SANDBOX, LearningMode.VALIDATION}
        return True

    def recommendation(self, event: CognitiveEvent, risk: RiskClass) -> str:
        if self.is_high_risk(event.domain):
            return "request_human_expert_review"
        if risk == RiskClass.HIGH_CONSEQUENCE_SCHEMA_GAP:
            return "block_automation_request_expert"
        if risk == RiskClass.ACTIVE_INTERFERENCE:
            return "pause_and_show_alternative_schema"
        if risk == RiskClass.UNRESOLVED_AMBIGUITY:
            return "ask_disambiguation_question"
        if risk == RiskClass.IGNORANCE:
            return "provide_missing_context"
        return "continue_without_intervention"


# ── Gated M2 Memory (adopted from ChatGPT, connected to M2Topology) ───────────

class GatedM2Memory:
    """
    Three-stage memory gate for schema hypotheses.
    Schema can only be published operationally at C3/C4 confidence.
    Adopted from ChatGPT prototype with extended evidence tracking.
    """

    def __init__(self):
        self.sandbox:     dict[str, SchemaHypothesis] = {}
        self.validated:   dict[str, SchemaHypothesis] = {}
        self.operational: dict[str, SchemaHypothesis] = {}

    def create_sandbox(self, label: str, domain: str,
                       description: str, evidence: list[str]) -> SchemaHypothesis:
        h = SchemaHypothesis(
            id=str(uuid4()),
            label=label, domain=domain,
            description=description,
            confidence_level=ConfidenceLevel.C0,
            evidence=evidence,
        )
        self.sandbox[h.id] = h
        logger.info("[M2Memory] Sandbox created: %s (%s)", h.label, h.id[:8])
        return h

    def promote(self, hypothesis_id: str,
                level: ConfidenceLevel) -> SchemaHypothesis:
        if hypothesis_id not in self.sandbox:
            raise KeyError(f"Hypothesis {hypothesis_id} not in sandbox")
        h = self.sandbox[hypothesis_id]
        h.confidence_level = level
        h.version += 1
        self.validated[hypothesis_id] = h
        logger.info("[M2Memory] Promoted %s → %s", h.label, level.value)
        return h

    def publish_operational(self, hypothesis_id: str) -> SchemaHypothesis:
        if hypothesis_id not in self.validated:
            raise KeyError(f"Hypothesis {hypothesis_id} not validated")
        h = self.validated[hypothesis_id]
        if h.confidence_level not in {ConfidenceLevel.C3, ConfidenceLevel.C4}:
            raise PermissionError(
                f"Only C3/C4 can be published. Current: {h.confidence_level.value}"
            )
        self.operational[hypothesis_id] = h
        logger.info("[M2Memory] Published operational: %s", h.label)
        return h

    @property
    def counts(self) -> dict:
        return {
            "sandbox":     len(self.sandbox),
            "validated":   len(self.validated),
            "operational": len(self.operational),
        }


# ── M2 Orchestrator (adopted + integrated with TAAA architecture) ─────────────

class M2Orchestrator:
    """
    Full M2 processing pipeline.
    Integrates ChatGPT's components with TAAA bilateral consent and M1 registry.
    """

    def __init__(self, memory: Optional[GatedM2Memory] = None,
                 threshold: float = FrictionTriggerEngine.DEFAULT_THRESHOLD):
        self.trigger    = FrictionTriggerEngine(threshold)
        self.classifier = SchemaRiskClassifier()
        self.safety     = SafetyGovernor()
        self.memory     = memory or GatedM2Memory()

    def process(self, event: CognitiveEvent) -> M2Decision:
        t0 = time.time()
        tr   = self.trigger.score(event)
        risk = self.classifier.classify(event)
        rec  = self.safety.recommendation(event, risk)
        allowed = self.safety.operational_update_allowed(event)

        proposed = None
        created  = False
        notes    = []

        if tr.state == TriggerState.ACTIVE:
            notes.append(f"M2 trigger active: SARS={tr.score:.3f} — {', '.join(tr.reasons)}")
        elif tr.state == TriggerState.MONITORING:
            notes.append(f"M2 observation band (no escalation): SARS={tr.score:.3f}")
        if risk != RiskClass.NONE:
            notes.append(f"Risk class: {risk.value}")
        if not allowed:
            notes.append("Operational update blocked by SafetyGovernor.")
        if tr.consent_checked:
            notes.append(f"Consent level: {tr.consent_level}")

        # Create a C0 sandbox hypothesis if capture is permitted and friction
        # was detected. C0 can never be published operationally (needs C3/C4).
        if self.safety.sandbox_capture_allowed(event) and risk != RiskClass.NONE:
            mismatch = max(0.0, event.user_confidence - event.system_confidence)
            proposed = self.memory.create_sandbox(
                label=f"{event.domain}_{risk.value}",
                domain=event.domain,
                description=(
                    f"Schema friction in '{event.domain}': "
                    f"{event.text[:120]}"
                ),
                evidence=[
                    f"sars={tr.score:.3f}",
                    f"ambiguity={event.ambiguity_score:.2f}",
                    f"domain_distance={event.domain_distance:.2f}",
                    f"consequence={event.consequence_score:.2f}",
                    f"user_confidence={event.user_confidence:.2f}",
                    f"confidence_mismatch={mismatch:.2f}",
                    f"stress_load={event.stress_load:.2f}",
                ],
            )
            created = True
            notes.append("Sandbox schema hypothesis created.")

        return M2Decision(
            trigger=tr, risk_class=risk, recommendation=rec,
            operational_update_allowed=allowed,
            sandbox_update_created=created,
            proposed_schema=proposed, notes=notes,
            latency_ms=round((time.time() - t0) * 1000, 2),
        )
