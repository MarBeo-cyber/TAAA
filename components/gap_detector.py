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

Uses LLM for nuanced schema analysis.
Falls back to rule-based detection when LLM unavailable.
"""

from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

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
    confidence: float                  # 0.0 – 1.0
    active_schema: Optional[str]       # The schema the person is using
    expected_schema: Optional[str]     # The schema the environment requires
    predicted_wrong_action: Optional[str]
    suppression_required: bool         # True for INTERFERENCE
    rationale: str
    m_level_recommended: str          # M0 / M1 / M2


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
            confidence=float(data.get("confidence", 0.5)),
            active_schema=data.get("active_schema"),
            expected_schema=data.get("expected_schema"),
            predicted_wrong_action=data.get("predicted_wrong_action"),
            suppression_required=bool(data.get("suppression_required", False)),
            rationale=data.get("rationale", ""),
            m_level_recommended=data.get("m_level_recommended", "M1"),
        )
    except Exception as e:
        logger.warning("[GapDetector] LLM failed: %s — using rules", e)
        return _detect_gap_rules(scenario, subject_profile, current_action, domain)


def _detect_gap_rules(scenario: str, subject_profile: dict,
                      current_action: Optional[str], domain: str) -> GapAnalysis:
    """Rule-based fallback gap detection."""
    s = scenario.lower()
    profile = subject_profile

    # Interference signals: confidence markers in action
    interference_keywords = [
        "turns toward", "walks toward", "assumes", "expects",
        "believes", "confident", "certain", "automatically"
    ]
    ignorance_keywords = [
        "confused", "lost", "doesn't know", "asks", "looks around",
        "hesitates", "uncertain", "stops and looks"
    ]

    action_text = (current_action or "").lower()
    has_interference_signal = any(kw in action_text for kw in interference_keywords)
    has_ignorance_signal = any(kw in action_text for kw in ignorance_keywords)

    # Check high-interference contexts from M1
    m1_prior = profile.get("m1_prior", {})
    high_risk_contexts = m1_prior.get("high_interference_contexts", [])
    env_context = profile.get("environment_context", "")
    schema_conflict = any(ctx in env_context for ctx in high_risk_contexts)

    if has_interference_signal or schema_conflict:
        return GapAnalysis(
            gap_type=GapType.INTERFERENCE,
            confidence=0.72,
            active_schema=f"Habitual schema from {profile.get('culture', 'unknown')} context",
            expected_schema=f"Schema required by {env_context or 'current environment'}",
            predicted_wrong_action=current_action,
            suppression_required=True,
            rationale="Interference detected: active schema from different cultural context.",
            m_level_recommended="M0" if domain == "emergency" else "M1",
        )
    elif has_ignorance_signal:
        return GapAnalysis(
            gap_type=GapType.IGNORANCE,
            confidence=0.68,
            active_schema=None,
            expected_schema=None,
            predicted_wrong_action=None,
            suppression_required=False,
            rationale="Ignorance detected: person is seeking information.",
            m_level_recommended="M1",
        )
    else:
        return GapAnalysis(
            gap_type=GapType.NONE,
            confidence=0.55,
            active_schema=None,
            expected_schema=None,
            predicted_wrong_action=None,
            suppression_required=False,
            rationale="No clear gap signal detected.",
            m_level_recommended="M2",
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
