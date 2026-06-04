"""
TAAA — Friction Trigger Engine (Integrated)

Integrates ChatGPT's SARS score (adopted with credit) with:
  - M1 Registry for domain_distance computation
  - Bilateral consent gating
  - MAAA bridge for stress_load (real-time biometrics)
  - Signal extractor for computing scores from raw signals

Original SARS formula (ChatGPT, 2026):
  SARS = ambiguity*0.25 + domain*0.25 + consequence*0.25
       + confidence_mismatch*0.15 + stress*0.10

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

from schema_memory.m1_priors import M1
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
    INACTIVE = "inactive"
    ACTIVE   = "active"


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

    Threshold tuning:
      0.62 = balanced (adopted from ChatGPT)
      0.50 = sensitive (catches more, more false positives)
      0.75 = conservative (fewer interventions, higher precision)
    """

    DEFAULT_THRESHOLD = 0.50

    WEIGHTS = {
        "ambiguity":           0.25,
        "domain":              0.25,
        "consequence":         0.25,
        "confidence_mismatch": 0.15,
        "stress":              0.10,
    }

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold

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

        return TriggerResult(
            score=round(sars, 4),
            state=TriggerState.ACTIVE if active else TriggerState.INACTIVE,
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
        if event.user_confidence <= 0.35:
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
        if event.mode == LearningMode.OPERATIONAL:
            return False
        if self.is_high_risk(event.domain):
            return False
        return event.mode in {LearningMode.SANDBOX, LearningMode.VALIDATION}

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
        if risk != RiskClass.NONE:
            notes.append(f"Risk class: {risk.value}")
        if not allowed:
            notes.append("Operational update blocked by SafetyGovernor.")
        if tr.consent_checked:
            notes.append(f"Consent level: {tr.consent_level}")

        # Create sandbox hypothesis if allowed and friction detected
        if allowed and risk != RiskClass.NONE:
            mismatch = max(0.0, event.user_confidence - event.system_confidence)
            proposed = self.memory.create_sandbox(
                label=f"{event.domain}_{risk.value}",
                domain=event.domain,
                description=(
                    f"Schema friction in '{event.domain}': "
                    f"{event.text[:120]}"
                ),
                evidence=[
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
