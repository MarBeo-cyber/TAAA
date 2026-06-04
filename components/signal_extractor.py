"""
TAAA — Signal Extractor

The missing piece in ChatGPT's M2 prototype.
Computes the CognitiveEvent scores from REAL signals:
  - ambiguity_score    ← keyword spotting + linguistic markers + gaze dwell
  - domain_distance    ← M1 registry comparison (culture + profession)
  - consequence_score  ← domain classification + explicit risk markers
  - user_confidence    ← behavioral signals (speech rate, hesitation, gaze)
  - system_confidence  ← M1/M2 schema match quality
  - stress_load        ← MAAA bridge / PAAA biometrics

Architecture:
  Level 1 — Always-on ultralight (10–50ms, local, no LLM)
    keyword spotting, gaze dwell, pause detection, domain classification

  Level 2 — Trigger check (10–30ms, SARS score)

  Level 3 — Optional LLM enrichment (300ms–2s, only if SARS > threshold)
    semantic ambiguity analysis, alternative interpretations

This is the layer that makes M2 actually work from a real signal stream,
not from hand-coded scores.
"""

from __future__ import annotations

import re
import time
import math
import logging
from dataclasses import dataclass
from typing import Optional

from schema_memory.m1_priors import M1
from components.friction_trigger import CognitiveEvent, LearningMode

logger = logging.getLogger("taaa.signal_extractor")


# ── Ambiguity keywords (Level 1 — ultralight, always-on) ─────────────────────

# Terms that are semantically ambiguous across cultural/professional schemas
AMBIGUITY_KEYWORDS = {
    # Temporal ambiguity
    "as soon as possible": 0.90,
    "asap":                0.88,
    "urgently":            0.75,
    "critical":            0.72,
    "reasonable time":     0.85,
    "in due course":       0.80,
    "flexible":            0.65,
    "when convenient":     0.70,

    # Commitment ambiguity
    "reasonable effort":   0.88,
    "best effort":         0.82,
    "commercially reasonable": 0.85,
    "appropriate":         0.70,
    "adequate":            0.68,
    "sufficient":          0.65,

    # Relational ambiguity (high-context vs low-context)
    "yes":                 0.55,   # High ambiguity in cross-cultural context
    "understood":          0.50,
    "noted":               0.55,
    "interesting":         0.65,   # In East Asian context: potential indirect refusal
    "silence":             0.60,   # Culturally ambiguous: absence vs respect vs refusal
    "remained silent":     0.68,
    "long silence":        0.72,
    "looked away":         0.55,
    "we will consider":    0.75,
    "let me think":        0.50,

    # Authority/approval ambiguity
    "approval":            0.60,
    "authorization":       0.60,
    "sign-off":            0.55,
    "green light":         0.58,
    "responsibility":      0.65,
    "ownership":           0.62,

    # Technical cross-domain ambiguity
    "incident":            0.70,   # IT vs physical emergency vs legal
    "critical failure":    0.72,
    "downtime":            0.60,
    "impact":              0.55,
    "risk":                0.55,
}

# High-consequence domains (Level 1 classification)
HIGH_CONSEQUENCE_DOMAINS = {
    "medical": 0.95, "clinical": 0.95, "legal": 0.92, "contract": 0.88,
    "finance": 0.85, "emergency": 0.98, "infrastructure": 0.85,
    "cybersecurity": 0.82, "engineering_safety": 0.90, "public_safety": 0.92,
    "psychiatric": 0.95, "pharmaceutical": 0.92, "judicial": 0.90,
    "negotiation": 0.65, "project": 0.50, "general": 0.30,
}

# Confidence markers in text
HIGH_CONFIDENCE_MARKERS = [
    "obviously", "clearly", "of course", "certainly", "definitely",
    "everyone knows", "it's clear", "as we agreed", "as usual",
    "naturally", "it goes without saying",
]
LOW_CONFIDENCE_MARKERS = [
    "i think", "i guess", "maybe", "perhaps", "not sure",
    "i'm not certain", "could be", "i believe", "possibly",
    "i'm wondering", "could you clarify", "i don't understand",
]

# Linguistic hesitation markers (audio proxy)
HESITATION_MARKERS = ["um", "uh", "er", "hmm", "well", "so", "you know"]


@dataclass
class ExtractedSignals:
    """All extracted signals before computing CognitiveEvent."""
    timestamp: float
    # Text signals
    text_ambiguity:      float    # From keyword spotting
    linguistic_confidence: float  # From confidence markers
    # Domain signals
    domain_consequence:  float    # From domain classification
    domain_distance_m1:  float    # From M1 registry
    # Behavioral signals (from PAAA/MAAA if available)
    gaze_dwell_ms:       float    # Time spent looking at a specific element
    speech_hesitation:   float    # Hesitation rate in speech
    paaa_stress:         float    # From PAAA biometrics
    # Computed system confidence
    m1_schema_match:     float    # How well M1 covers this domain+culture

    def to_cognitive_event(self, text: str, domain: str,
                           subject_id: str,
                           mode: LearningMode,
                           session_id: Optional[str]) -> CognitiveEvent:
        """Convert extracted signals to CognitiveEvent for M2 orchestrator."""
        # User confidence: combine text markers + behavioral signals
        user_conf = (
            self.linguistic_confidence * 0.65 +
            (1.0 - self.speech_hesitation) * 0.20 +
            (1.0 - min(1.0, self.gaze_dwell_ms / 3000.0)) * 0.15
        )

        # System confidence: M1 schema match quality
        sys_conf = self.m1_schema_match

        # Ambiguity: text + gaze dwell (staring = processing difficulty)
        ambiguity = (
            self.text_ambiguity * 0.65 +
            min(1.0, self.gaze_dwell_ms / 5000.0) * 0.35
        )

        return CognitiveEvent(
            text=text,
            domain=domain,
            subject_id=subject_id,
            ambiguity_score=round(min(1.0, ambiguity), 3),
            domain_distance=round(self.domain_distance_m1, 3),
            consequence_score=round(self.domain_consequence, 3),
            user_confidence=round(max(0.0, min(1.0, user_conf)), 3),
            system_confidence=round(max(0.0, min(1.0, sys_conf)), 3),
            stress_load=round(self.paaa_stress, 3),
            mode=mode,
            session_id=session_id,
        )


class SignalExtractor:
    """
    Computes CognitiveEvent scores from real signals.

    Level 1 (always-on, < 50ms):
      - Keyword spotting for ambiguity
      - Domain classification for consequence
      - Linguistic confidence markers

    Level 2 (on-demand, < 30ms):
      - M1 registry for domain_distance
      - Behavioral signal integration

    Level 3 (optional LLM, 300ms–2s):
      - Semantic ambiguity enrichment
      - Alternative interpretation detection
    """

    def __init__(self):
        self._keyword_pattern = re.compile(
            "|".join(re.escape(k) for k in AMBIGUITY_KEYWORDS.keys()),
            re.IGNORECASE
        )

    def extract(self,
                text: str,
                domain: str,
                subject_id: str = "anonymous",
                subject_culture: Optional[str] = None,
                subject_profession: Optional[str] = None,
                environment_culture: Optional[str] = None,
                # Behavioral signals from PAAA/MAAA (optional)
                paaa_stress: float = 0.0,
                gaze_dwell_ms: float = 0.0,
                speech_hesitation_rate: float = 0.0,
                # M2 context
                mode: LearningMode = LearningMode.OPERATIONAL,
                session_id: Optional[str] = None,
                use_llm_enrichment: bool = False) -> CognitiveEvent:
        """
        Main extraction method.
        Returns CognitiveEvent with all scores computed from real signals.
        """
        t0 = time.time()

        # ── Level 1: Text analysis (ultralight, always-on) ────────────────────
        text_ambiguity      = self._compute_text_ambiguity(text)
        linguistic_conf     = self._compute_linguistic_confidence(text)
        domain_consequence  = HIGH_CONSEQUENCE_DOMAINS.get(domain.lower(), 0.40)

        # ── Level 2: M1 registry (domain distance) ────────────────────────────
        domain_distance = self._compute_domain_distance(
            subject_culture, subject_profession,
            environment_culture, domain
        )
        m1_match = self._compute_m1_match(
            subject_culture, subject_profession, domain
        )

        signals = ExtractedSignals(
            timestamp=time.time(),
            text_ambiguity=text_ambiguity,
            linguistic_confidence=linguistic_conf,
            domain_consequence=domain_consequence,
            domain_distance_m1=domain_distance,
            gaze_dwell_ms=gaze_dwell_ms,
            speech_hesitation=speech_hesitation_rate,
            paaa_stress=paaa_stress,
            m1_schema_match=m1_match,
        )

        event = signals.to_cognitive_event(
            text=text, domain=domain, subject_id=subject_id,
            mode=mode, session_id=session_id
        )

        # ── Level 3: LLM enrichment (optional, only if trigger likely) ─────────
        if use_llm_enrichment and event.ambiguity_score > 0.55:
            event = self._enrich_with_llm(event, text, domain)

        latency = (time.time() - t0) * 1000
        logger.debug("[SignalExtractor] %.1fms — ambiguity=%.2f domain_dist=%.2f",
                     latency, event.ambiguity_score, event.domain_distance)
        return event

    # ── Level 1: Text signals ─────────────────────────────────────────────────

    def _compute_text_ambiguity(self, text: str) -> float:
        """Keyword-based ambiguity scoring. < 5ms."""
        if not text:
            return 0.0
        text_lower = text.lower()
        matches = self._keyword_pattern.findall(text_lower)
        if not matches:
            return 0.0
        # Score = max match weight, amplified by count
        scores = [AMBIGUITY_KEYWORDS.get(m.lower(), 0.5) for m in matches]
        base = max(scores)
        count_bonus = min(0.20, len(matches) * 0.08)
        return min(1.0, base + count_bonus)

    def _compute_linguistic_confidence(self, text: str) -> float:
        """
        Estimate user confidence from linguistic markers.
        High confidence markers → high score
        Low confidence markers → low score
        Default: 0.5 (neutral)
        """
        text_lower = text.lower()
        high = sum(1 for m in HIGH_CONFIDENCE_MARKERS if m in text_lower)
        low  = sum(1 for m in LOW_CONFIDENCE_MARKERS  if m in text_lower)
        hesitation = sum(1 for m in HESITATION_MARKERS if f" {m} " in f" {text_lower} ")

        if high == 0 and low == 0 and hesitation == 0:
            return 0.55   # Neutral default

        score = 0.55
        score += high * 0.12
        score -= low  * 0.10
        score -= hesitation * 0.05
        return round(max(0.10, min(0.95, score)), 3)

    # ── Level 2: M1 registry ──────────────────────────────────────────────────

    def _compute_domain_distance(self,
                                  subject_culture: Optional[str],
                                  subject_profession: Optional[str],
                                  environment_culture: Optional[str],
                                  domain: str) -> float:
        """
        Compute cultural/professional domain distance using M1 registry.
        This replaces hand-coded domain_distance in CognitiveEvent.
        """
        distance = 0.0

        # Cultural distance (from M1 interference risk)
        if subject_culture and environment_culture and subject_culture != environment_culture:
            risk = M1.interference_risk(subject_culture, environment_culture)
            distance += risk["score"] * 0.6
        elif subject_culture and environment_culture:
            distance += 0.0  # Same culture — no distance

        # Professional domain distance
        # (engineer reading a medical text, doctor reading a legal contract, etc.)
        CROSS_DOMAIN_PAIRS = {
            ("engineering", "medical"):    0.70,
            ("engineering", "legal"):      0.65,
            ("engineering", "finance"):    0.55,
            ("medical", "legal"):          0.45,
            ("medical", "engineering"):    0.70,
            ("it", "medical"):             0.75,
            ("it", "legal"):               0.60,
            ("manager", "clinical"):       0.65,
        }
        if subject_profession:
            for (prof_a, dom_b), dist in CROSS_DOMAIN_PAIRS.items():
                if (prof_a in (subject_profession or "").lower() and
                        dom_b in domain.lower()):
                    distance += dist * 0.4
                    break

        return round(min(1.0, distance), 3)

    def _compute_m1_match(self, subject_culture: Optional[str],
                           subject_profession: Optional[str],
                           domain: str) -> float:
        """
        System confidence: how well does M1 cover this domain+culture combination?
        High coverage → high system confidence.
        """
        if not subject_culture:
            return 0.35   # No cultural prior — low confidence

        profile = M1.get(subject_culture)
        if not profile:
            return 0.30

        # Known high-interference domains for this profile
        interference_contexts = profile.high_interference_contexts
        in_interference_zone = any(
            ctx in domain.lower() for ctx in interference_contexts
        )
        if in_interference_zone:
            return 0.35   # We know M1 is unreliable here

        # Profession match
        if subject_profession:
            prof_profile = M1.get_by_profession(subject_profession)
            if prof_profile:
                return 0.72   # Good M1 coverage for this profession+culture

        return 0.58   # Moderate M1 coverage

    # ── Level 3: LLM enrichment ───────────────────────────────────────────────

    def _enrich_with_llm(self, event: CognitiveEvent,
                          text: str, domain: str) -> CognitiveEvent:
        """
        Optional LLM enrichment for ambiguity score.
        Only called when SARS is likely above threshold AND latency allows.
        """
        try:
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                system=(
                    "You are a schema ambiguity detector. "
                    "Given text and domain, return ONLY a JSON: "
                    '{"ambiguity": 0.0-1.0, "reason": "brief reason"}'
                ),
                messages=[{"role": "user", "content":
                           f"Domain: {domain}\nText: {text[:300]}"}]
            )
            import json
            raw = resp.content[0].text.strip()
            raw = raw.replace("```json","").replace("```","").strip()
            data = json.loads(raw)
            llm_ambiguity = float(data.get("ambiguity", event.ambiguity_score))
            # Blend: LLM 60%, keyword 40%
            event.ambiguity_score = round(
                0.6 * llm_ambiguity + 0.4 * event.ambiguity_score, 3
            )
            logger.debug("[SignalExtractor] LLM enrichment: %.2f", event.ambiguity_score)
        except Exception as e:
            logger.debug("[SignalExtractor] LLM enrichment skipped: %s", e)
        return event

    # ── Convenience: from raw text only ──────────────────────────────────────

    def from_text(self, text: str, domain: str = "general",
                  subject_id: str = "anonymous",
                  subject_culture: Optional[str] = None,
                  subject_profession: Optional[str] = None,
                  environment_culture: Optional[str] = None,
                  paaa_stress: float = 0.0,
                  gaze_dwell_ms: float = 0.0,
                  session_id: Optional[str] = None) -> CognitiveEvent:
        """Simplified extraction for text-only input."""
        event = self.extract(
            text=text, domain=domain, subject_id=subject_id,
            subject_culture=subject_culture,
            subject_profession=subject_profession,
            environment_culture=environment_culture,
            paaa_stress=paaa_stress,
            gaze_dwell_ms=gaze_dwell_ms,
        )
        event.session_id = session_id
        return event
