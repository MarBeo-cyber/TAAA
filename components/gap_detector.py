"""
TAAA — Gap Detector + Interference Predictor

The most important distinction in the TAAA framework:

  IGNORANCE:    schema absent — the person doesn't know
                → add information
                → cost: low (person is open to guidance)

  INTERFERENCE: schema present but WRONG — the person believes they know
                → suppress first, then correct
                → cost: high (certainty blocks new information)

The American in Shinjuku doesn't think "I don't know where to go."
He thinks "I know where to go." That is the interference condition.
It is more dangerous than ignorance because the person acts with confidence.

Two detectors, and they are not equivalent:

  _detect_gap_llm    — asks a model to reason about the scenario. Reports the
                       model's own `confidence` number.

  _detect_gap_rules  — the no-API-key fallback. It is a KEYWORD CLASSIFIER over
                       the scenario text plus the caller-supplied `current_action`
                       label, cross-checked against M1's interference risk between
                       the subject's culture and the environment's. It has no
                       calibration data, so it reports `confidence=None` and a
                       discrete `rule_id` naming the rule that fired, plus the
                       matched substrings in `evidence`. Do not read a rule_id as
                       a measurement: it tells you which words were present, not
                       how likely the classification is to be right.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from schema_memory.m1_priors import M1

logger = logging.getLogger("taaa.gap_detector")

try:
    import anthropic
    _CLIENT = anthropic.Anthropic()
    _LLM_AVAILABLE = True
except Exception:
    _CLIENT = None
    _LLM_AVAILABLE = False


class GapType(Enum):
    NONE            = "none"           # No gap detected
    IGNORANCE       = "ignorance"      # Schema absent — person doesn't know
    INTERFERENCE    = "interference"   # Schema present but wrong — person believes they know
    PARTIAL         = "partial"        # Schema partially correct — needs refinement


@dataclass
class GapAnalysis:
    """Result of gap detection analysis."""
    gap_type: GapType
    active_schema: Optional[str]       # The schema the person is using
    expected_schema: Optional[str]     # The schema the environment requires
    predicted_wrong_action: Optional[str]
    suppression_required: bool         # True for INTERFERENCE
    rationale: str
    m_level_recommended: str           # M0 / M1 / M2

    detector: str = "rules"            # "llm" | "rules"
    # Self-reported by the LLM. None on the rules path — the keyword classifier
    # has no calibration set, so any number it printed would be decoration.
    confidence: Optional[float] = None
    # Which rule fired, on the rules path. None on the LLM path.
    rule_id: Optional[str] = None
    # The substrings/among-signals that actually made the rule fire.
    evidence: list[str] = field(default_factory=list)


@dataclass
class InterferencePrediction:
    """Detailed analysis of an active interference schema."""
    schema_name: str
    strength: float                    # 0–1, how automatic/strong the schema is
    activation_context: str            # What is triggering the schema
    predicted_error: str               # What the person will do wrong
    suppression_strategy: str          # How to interrupt before the error
    timing_window_ms: int              # How long we have before wrong action
    cultural_source: Optional[str]     # Which cultural/professional prior it comes from


# ── LLM-powered Gap Detection ─────────────────────────────────────────────────

GAP_DETECTION_SYSTEM = """You are the Gap Detector module of the TAAA (Translational Autopoietic Adaptive Agent).

Your task is to analyse a situation and determine whether a person is experiencing:
  - NONE: no schema gap
  - IGNORANCE: the person lacks a schema for this situation (they know they don't know)
  - INTERFERENCE: the person has an ACTIVE but WRONG schema (they believe they know, but are wrong)
  - PARTIAL: the person's schema is partially correct but needs refinement

The critical distinction: INTERFERENCE is more dangerous than IGNORANCE.
An interfering schema produces ACTIVE wrong predictions that the person experiences as correct.
The American in Shinjuku station who turns toward the wrong exit because
"exit is in the direction opposite to incoming flow" is experiencing INTERFERENCE.
He acts with confidence. He needs suppression before correction.

Respond ONLY in JSON with this exact structure:
{
  "gap_type": "none|ignorance|interference|partial",
  "confidence": 0.0-1.0,
  "active_schema": "description of the schema the person is using, or null",
  "expected_schema": "description of the schema the environment requires, or null",
  "predicted_wrong_action": "what they will do wrong, or null",
  "suppression_required": true/false,
  "rationale": "brief explanation",
  "m_level_recommended": "M0|M1|M2"
}"""


def detect_gap(scenario: str,
               subject_profile: dict,
               current_action: Optional[str] = None,
               domain: str = "daily") -> GapAnalysis:
    """
    Detect schema gap in a given scenario for a given subject.

    scenario: description of the situation
    subject_profile: {culture, profession, age, context, m1_prior, ...}
    current_action: what the person is doing / about to do (if known)
    domain: "emergency" | "daily"
    """

    if _LLM_AVAILABLE:
        return _detect_gap_llm(scenario, subject_profile, current_action, domain)
    else:
        return _detect_gap_rules(scenario, subject_profile, current_action, domain)


def _detect_gap_llm(scenario: str, subject_profile: dict,
                    current_action: Optional[str], domain: str) -> GapAnalysis:
    prompt = f"""Scenario: {scenario}

Subject profile:
{json.dumps(subject_profile, indent=2, ensure_ascii=False)}

Current action (if known): {current_action or 'not specified'}
Domain: {domain}

Analyse for schema gaps. Focus especially on whether the person has an ACTIVE but WRONG schema
(interference) vs simply lacking information (ignorance)."""

    try:
        resp = _CLIENT.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=GAP_DETECTION_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        return GapAnalysis(
            gap_type=GapType(data.get("gap_type", "none")),
            active_schema=data.get("active_schema"),
            expected_schema=data.get("expected_schema"),
            predicted_wrong_action=data.get("predicted_wrong_action"),
            suppression_required=bool(data.get("suppression_required", False)),
            rationale=data.get("rationale", ""),
            m_level_recommended=data.get("m_level_recommended", "M1"),
            detector="llm",
            # Model self-report, not a measured calibration.
            confidence=float(data.get("confidence", 0.5)),
        )
    except Exception as e:
        logger.warning("[GapDetector] LLM failed: %s — using rules", e)
        return _detect_gap_rules(scenario, subject_profile, current_action, domain)


# ── Rule-based fallback: keyword lists ───────────────────────────────────────
# These are hand-written substring lists, not learned features. They are the
# no-API-key floor of the system, and the code says so everywhere it reports.

# Automaticity: the person acts without checking. This is the behavioural
# signature of an ACTIVE schema — the "he believes he knows" half of interference.
AUTOMATICITY_MARKERS = [
    "turns toward", "walks toward", "walking confidently", "assumes",
    "expects", "believes", "confident", "certain", "automatically",
    "immediately", "without checking", "as usual", "obviously",
]

# Uncertainty: the person knows they don't know. Signature of IGNORANCE.
UNCERTAINTY_MARKERS = [
    "confused", "lost", "doesn't know", "does not know", "asks",
    "looks around", "hesitates", "uncertain", "stops and looks",
    "cannot answer", "can't answer", "unsure", "not sure",
    "doesn't have access", "does not have access",
]

# Mismatch: the SITUATION states that the two schemas diverge. Required for
# INTERFERENCE, because interference is a claim about the world, not about how
# the caller happened to phrase the action label. Deliberately phrase-level:
# a bare "wrong" would fire on "Nothing is wrong."
MISMATCH_MARKERS = [
    "wrong direction", "wrong exit", "wrong way", "wrong turn",
    "opposite to", "opposite direction", "but in this", "but in japanese",
    "incompatible", "does not mean", "doesn't mean", "means something different",
    "misinterpret", "actually means", "instead of", "two incompatible",
    "in us business culture", "perceived as", "the gap is ontological",
]

# M1 interference risk at or above this counts as a schema conflict between the
# subject's culture and the environment's. M1.interference_risk is a real count
# over 6 declared dimensions (see m1_priors.py), so this is the one input here
# that is computed rather than matched.
SCHEMA_CONFLICT_RISK_THRESHOLD = 0.50


def _matches(text: str, markers: list[str]) -> list[str]:
    return [m for m in markers if m in text]


def _schema_conflict(subject_profile: dict) -> tuple[Optional[bool], list[str]]:
    """Is the subject's cultural schema in conflict with the environment's?

    Returns (True | False | None, evidence). None means "not determinable" —
    one of the two profiles is unknown to M1, so the caller must not treat the
    absence of a conflict as evidence of agreement.

    This replaces the old `any(ctx in env_context for ctx in high_risk_contexts)`,
    which compared M1 phrases like "high_context_communication" against culture
    ids like "east_asian" and was therefore never true.
    """
    env_context = (subject_profile.get("environment_context") or "").strip()
    culture = subject_profile.get("culture")

    # Path 1 — both sides are known M1 communities: compute the real risk.
    if culture and env_context and M1.get(culture) and M1.get(env_context):
        risk = M1.interference_risk(culture, env_context)
        if risk["score"] >= SCHEMA_CONFLICT_RISK_THRESHOLD:
            return True, [f"m1_interference_risk={risk['score']} "
                          f"({len(risk['conflict_dimensions'])} dimensions)"]
        return False, [f"m1_interference_risk={risk['score']}"]

    # Path 2 — the caller passed a context *label* rather than a community id
    # (e.g. environment_context="high_context_communication"). Match it against
    # this subject's declared high-interference contexts.
    high_risk_contexts = (subject_profile.get("m1_prior") or {}).get(
        "high_interference_contexts", [])
    hits = [ctx for ctx in high_risk_contexts if ctx and ctx in env_context]
    if hits:
        return True, [f"declared_high_interference_context:{h}" for h in hits]

    return None, []


def _detect_gap_rules(scenario: str, subject_profile: dict,
                      current_action: Optional[str], domain: str) -> GapAnalysis:
    """Keyword classifier over scenario + action label. NOT a measurement.

    Inputs actually consumed:
      - scenario text          (was computed and discarded before this fix)
      - current_action label   (caller-supplied)
      - M1 interference risk between subject culture and environment context

    Output carries `rule_id` and `evidence` instead of a confidence float.
    """
    scenario_text = (scenario or "").lower()
    action_text = (current_action or "").lower()
    both = f"{scenario_text} || {action_text}"

    automaticity = _matches(both, AUTOMATICITY_MARKERS)
    uncertainty = _matches(both, UNCERTAINTY_MARKERS)
    mismatch = _matches(scenario_text, MISMATCH_MARKERS)
    conflict, conflict_evidence = _schema_conflict(subject_profile)

    culture = subject_profile.get("culture") or "unknown"
    env_context = subject_profile.get("environment_context") or "current environment"

    # R1 — INTERFERENCE. Requires all three: the person acts automatically, the
    # situation states that the schemas diverge, and M1 does not positively rule
    # out a cultural conflict. Automaticity alone is not enough — that was the
    # bug that classified "walks toward the counter" at a coffee kiosk as an
    # emergency haptic stop.
    if automaticity and mismatch and conflict is not False:
        return GapAnalysis(
            gap_type=GapType.INTERFERENCE,
            active_schema=f"Habitual schema from {culture} context",
            expected_schema=f"Schema required by {env_context}",
            predicted_wrong_action=current_action,
            suppression_required=True,
            rationale=("Interference: automatic action plus a stated schema "
                       "divergence in the situation."),
            m_level_recommended="M0" if domain == "emergency" else "M1",
            detector="rules",
            rule_id="interference_automaticity_and_stated_mismatch",
            evidence=automaticity + mismatch + conflict_evidence,
        )

    # R2 — PARTIAL. Both signatures present: the person is confident about part
    # of the situation and openly lost about another part. The schema is
    # partially right and needs refinement rather than suppression.
    if automaticity and uncertainty:
        return GapAnalysis(
            gap_type=GapType.PARTIAL,
            active_schema=f"Partially applicable schema from {culture} context",
            expected_schema=f"Schema required by {env_context}",
            predicted_wrong_action=None,
            suppression_required=False,
            rationale=("Partial: confident and uncertain signals coexist — "
                       "schema applies in part, needs refinement."),
            m_level_recommended="M1" if domain == "emergency" else "M2",
            detector="rules",
            rule_id="partial_mixed_signals",
            evidence=automaticity + uncertainty,
        )

    # R3 — IGNORANCE. The person is seeking, not asserting.
    if uncertainty:
        return GapAnalysis(
            gap_type=GapType.IGNORANCE,
            active_schema=None,
            expected_schema=f"Schema required by {env_context}",
            predicted_wrong_action=None,
            suppression_required=False,
            rationale="Ignorance: person is seeking information.",
            m_level_recommended="M1",
            detector="rules",
            rule_id="ignorance_uncertainty_markers",
            evidence=uncertainty,
        )

    # R4 — NONE.
    return GapAnalysis(
        gap_type=GapType.NONE,
        active_schema=None,
        expected_schema=None,
        predicted_wrong_action=None,
        suppression_required=False,
        rationale="No keyword signal for a schema gap in scenario or action.",
        m_level_recommended="M2",
        detector="rules",
        rule_id="none_no_signal",
        evidence=conflict_evidence,
    )


# ── Interference Predictor ────────────────────────────────────────────────────

INTERFERENCE_SYSTEM = """You are the Interference Predictor module of the TAAA.

Given a confirmed INTERFERENCE gap, your task is to predict:
1. How strong and automatic is the wrong schema?
2. What exactly will the person do wrong?
3. How to interrupt BEFORE the error, at the pre-verbal level?
4. How much time before the wrong action is executed?

Key insight: cognitive inhibition cannot use negation ("don't turn right").
Negation ACTIVATES the schema. Interruption must be pre-verbal,
operating below the level where language engages the wrong schema.

Respond ONLY in JSON:
{
  "schema_name": "name of the interfering schema",
  "strength": 0.0-1.0,
  "activation_context": "what is triggering the wrong schema",
  "predicted_error": "specific wrong action",
  "suppression_strategy": "m0_haptic_stop|ar_substitution|procedural_bypass",
  "timing_window_ms": integer (milliseconds before wrong action),
  "cultural_source": "which cultural/professional background this schema comes from"
}"""


def predict_interference(gap: GapAnalysis,
                         scenario: str,
                         subject_profile: dict) -> Optional[InterferencePrediction]:
    """Detailed prediction for an identified interference."""
    if gap.gap_type != GapType.INTERFERENCE:
        return None

    if _LLM_AVAILABLE:
        return _predict_interference_llm(gap, scenario, subject_profile)
    else:
        return _predict_interference_rules(gap, subject_profile)


def _predict_interference_llm(gap: GapAnalysis, scenario: str,
                               subject_profile: dict) -> InterferencePrediction:
    prompt = f"""Gap analysis result:
- Active (wrong) schema: {gap.active_schema}
- Expected schema: {gap.expected_schema}
- Predicted wrong action: {gap.predicted_wrong_action}

Scenario: {scenario}
Subject profile: {json.dumps(subject_profile, indent=2, ensure_ascii=False)}

Predict the interference in detail."""

    try:
        resp = _CLIENT.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=INTERFERENCE_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return InterferencePrediction(
            schema_name=data.get("schema_name", "unknown"),
            strength=float(data.get("strength", 0.7)),
            activation_context=data.get("activation_context", ""),
            predicted_error=data.get("predicted_error", ""),
            suppression_strategy=data.get("suppression_strategy", "m0_haptic_stop"),
            timing_window_ms=int(data.get("timing_window_ms", 300)),
            cultural_source=data.get("cultural_source"),
        )
    except Exception as e:
        logger.warning("[InterferencePredictor] LLM failed: %s", e)
        return _predict_interference_rules(gap, subject_profile)


def _predict_interference_rules(gap: GapAnalysis,
                                 subject_profile: dict) -> InterferencePrediction:
    return InterferencePrediction(
        schema_name=gap.active_schema or "habitual_schema",
        strength=0.75,
        activation_context="automatic activation from cultural background",
        predicted_error=gap.predicted_wrong_action or "action in wrong direction",
        suppression_strategy="m0_haptic_stop",
        timing_window_ms=350,
        cultural_source=subject_profile.get("culture"),
    )
