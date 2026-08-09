"""
TAAA — Intervention Engine

Selects and generates the optimal intervention given:
  - Gap analysis (ignorance / interference / partial)
  - Interference prediction (schema strength, timing window)
  - Current M-level (M0 / M1 / M2)
  - Domain (emergency / daily)

Three intervention strategies:

  1. AR_SUBSTITUTION (M0)
     Transform the visual environment so the correct schema-pattern
     is presented instead of the one the person cannot decode.
     The American sees a familiar exit icon, not the Japanese kanji.
     Works below the level of cultural interpretation.

  2. PROCEDURAL_BYPASS (M0/M1)
     Provide instructions so elementary they operate below schema level:
     pure motor sequences. "Three steps forward. Turn left. Door."
     No concept required — only body movement.

  3. CALIBRATED_INTERRUPTION (M0)
     A pre-verbal haptic/visual signal that blocks the wrong action
     BEFORE the schema completes its activation.
     Must arrive in the timing window before the action is executed.
     Cannot use negation — that activates the schema.

  4. CULTURAL_BRIDGE (M1)
     Translate the concept into the user's cultural schema vocabulary.
     Used when System 2 is still accessible.

  5. DEEP_TRANSLATION (M2)
     Full bidirectional schema translation using personal topology.
     Daily domain only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from components.gap_detector import GapAnalysis, GapType, InterferencePrediction
from components.timing_controller import TimingDecision, MLevel, OutputType

logger = logging.getLogger("taaa.intervention_engine")

try:
    import anthropic
    _CLIENT = anthropic.Anthropic()
    _LLM_AVAILABLE = True
except Exception:
    _CLIENT = None
    _LLM_AVAILABLE = False


class InterventionStrategy(Enum):
    NONE                  = "none"
    AR_SUBSTITUTION       = "ar_substitution"
    PROCEDURAL_BYPASS     = "procedural_bypass"
    CALIBRATED_INTERRUPT  = "calibrated_interruption"
    CULTURAL_BRIDGE       = "cultural_bridge"
    DEEP_TRANSLATION      = "deep_translation"


@dataclass
class Intervention:
    """The complete intervention package to be executed."""
    strategy: InterventionStrategy
    m_level: str

    # AR output
    ar_active: bool
    ar_instruction: Optional[str] = None    # What to render on AR glasses
    ar_schema: Optional[str] = None         # Which M0 schema to instantiate

    # Haptic output
    haptic_active: bool = False
    haptic_pattern: str = "none"            # "stop" | "directional" | "warning" | "continuous"

    # Voice / text output
    voice_active: bool = False
    voice_message: Optional[str] = None     # Max 9 words (MAAA Regulatory Engine constraint)

    # Timing
    execute_after_ms: float = 0.0
    duration_ms: float = 2000.0

    # Metadata
    suppression_first: bool = False         # True = interrupt BEFORE providing info
    rationale: str = ""


TRANSLATION_SYSTEM = """You are the Intervention Engine of the TAAA (Translational Autopoietic Adaptive Agent).

Generate a cultural bridge or deep translation intervention.
Rules:
- BREVITY: voice messages maximum 9 words (MAAA Regulatory Engine constraint)
- No negation in M0 output ("don't turn right" ACTIVATES the wrong schema)
- Preserve cultural diversity: bridge, don't merge
- Output must be actionable, not explanatory

Respond ONLY in JSON:
{
  "voice_message": "max 9 words, imperative, culturally adapted",
  "ar_instruction": "what to show on AR glasses",
  "cultural_bridge_explanation": "brief explanation of the schema mapping",
  "suppression_first": true/false
}"""


class InterventionEngine:
    """
    Selects and generates interventions based on gap analysis and M-level.
    """

    @property
    def llm_available(self) -> bool:
        """True when the anthropic client was constructed at import time.

        This is *not* a promise that calls will succeed: a client with no API
        key constructs fine and fails at request time. Every call site falls
        back to the rule-based path on any exception.
        """
        return _LLM_AVAILABLE

    def generate(self,
                 gap: GapAnalysis,
                 timing: TimingDecision,
                 interference: Optional[InterferencePrediction] = None,
                 scenario: str = "",
                 subject_profile: Optional[dict] = None,
                 environment_profile: Optional[dict] = None,
                 domain: str = "daily") -> Intervention:
        """Main entry point: generate the appropriate intervention."""

        if gap.gap_type == GapType.NONE:
            return Intervention(
                strategy=InterventionStrategy.NONE,
                m_level=timing.current_m_level.value,
                ar_active=False, rationale="No gap detected."
            )

        m_level = timing.current_m_level

        # Route to correct strategy
        if m_level == MLevel.M0:
            return self._m0_intervention(gap, interference, timing, domain)
        elif m_level == MLevel.M1:
            return self._cultural_bridge(gap, scenario, subject_profile,
                                         environment_profile, timing)
        else:  # M2
            return self._deep_translation(gap, scenario, subject_profile,
                                          environment_profile, timing)

    # ── M0 Interventions ──────────────────────────────────────────────────────

    def _m0_intervention(self, gap: GapAnalysis,
                         interference: Optional[InterferencePrediction],
                         timing: TimingDecision,
                         domain: str) -> Intervention:
        """Select M0 strategy based on gap type and interference details."""

        if gap.suppression_required and interference:
            # INTERFERENCE: must suppress FIRST, then redirect
            return self._calibrated_interrupt_then_redirect(gap, interference, timing)

        elif gap.gap_type == GapType.IGNORANCE:
            # IGNORANCE in M0 domain: AR substitution
            return self._ar_substitution(gap, timing)

        elif timing.output_type == OutputType.M0_SINGLE_IMPERATIVE:
            # Extreme stress: single imperative
            return Intervention(
                strategy=InterventionStrategy.PROCEDURAL_BYPASS,
                m_level="M0",
                ar_active=True,
                ar_instruction="LARGE_ARROW_FORWARD",
                ar_schema="SAFE_PATH",
                haptic_active=True,
                haptic_pattern="directional_pulse",
                voice_active=True,
                voice_message="Avanti.",
                suppression_first=False,
                rationale="Extreme M0: single motor instruction."
            )
        else:
            return self._ar_substitution(gap, timing)

    def _calibrated_interrupt_then_redirect(self,
                                             gap: GapAnalysis,
                                             interference: InterferencePrediction,
                                             timing: TimingDecision) -> Intervention:
        """
        Two-phase intervention for active interference:
        Phase 1: Interrupt the wrong schema (haptic stop — pre-verbal)
        Phase 2: Redirect with correct M0 output (AR + brief imperative)

        CRITICAL: No negation in Phase 1.
        A sharp haptic pulse stops the action without activating the wrong schema.
        """
        # Determine redirect schema from gap
        redirect_schema = "SAFE_PATH"
        ar_instruction = "STOP_THEN_ARROW_CORRECT_DIRECTION"

        # Voice message: imperative, positive, max 9 words, no negation
        voice = "Fermati. Segui la freccia verde."

        return Intervention(
            strategy=InterventionStrategy.CALIBRATED_INTERRUPT,
            m_level="M0",
            ar_active=True,
            ar_instruction=ar_instruction,
            ar_schema=redirect_schema,
            haptic_active=True,
            haptic_pattern="sharp_stop",       # Phase 1: interrupt
            voice_active=True,
            voice_message=voice,               # Phase 2: redirect (after 150ms)
            execute_after_ms=0.0,              # Haptic immediate
            duration_ms=2500.0,
            suppression_first=True,
            rationale=(
                f"Interference '{interference.schema_name}' "
                f"(strength={interference.strength:.2f}). "
                "Haptic interrupt → AR redirect. No negation."
            )
        )

    def _ar_substitution(self, gap: GapAnalysis,
                         timing: TimingDecision) -> Intervention:
        """
        Replace visual environment elements with M0-compatible versions.
        Japanese kanji exit sign → familiar icon for Western user.
        """
        return Intervention(
            strategy=InterventionStrategy.AR_SUBSTITUTION,
            m_level="M0",
            ar_active=True,
            ar_instruction="SUBSTITUTE_ENVIRONMENTAL_SIGNAGE_WITH_M0_ICONS",
            ar_schema="EXIT",
            haptic_active=True,
            haptic_pattern="directional_pulse",
            voice_active=False,               # AR substitution works silently
            suppression_first=False,
            rationale="Ignorance: replace unreadable schema with M0 equivalent."
        )

    # ── M1 Cultural Bridge ────────────────────────────────────────────────────

    def _cultural_bridge(self, gap: GapAnalysis, scenario: str,
                         subject_profile: Optional[dict],
                         environment_profile: Optional[dict],
                         timing: TimingDecision) -> Intervention:
        """Generate cultural bridge using LLM or rules."""
        if _LLM_AVAILABLE and subject_profile:
            return self._cultural_bridge_llm(gap, scenario, subject_profile,
                                             environment_profile, timing)
        return self._cultural_bridge_rules(gap, timing)

    def _cultural_bridge_llm(self, gap: GapAnalysis, scenario: str,
                              subject_profile: dict,
                              environment_profile: Optional[dict],
                              timing: TimingDecision) -> Intervention:
        prompt = f"""Gap: {gap.gap_type.value}
Active schema: {gap.active_schema}
Expected schema: {gap.expected_schema}
Scenario: {scenario}
Subject: {json.dumps(subject_profile, ensure_ascii=False)}
Environment: {json.dumps(environment_profile or {}, ensure_ascii=False)}

Generate a cultural bridge intervention. Remember: max 9 words for voice."""

        try:
            resp = _CLIENT.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=400,
                system=TRANSLATION_SYSTEM,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
            data = json.loads(raw)
            return Intervention(
                strategy=InterventionStrategy.CULTURAL_BRIDGE,
                m_level="M1",
                ar_active=True,
                ar_instruction=data.get("ar_instruction", "CULTURAL_ADAPTATION_OVERLAY"),
                haptic_active=False,
                voice_active=True,
                voice_message=data.get("voice_message", ""),
                suppression_first=data.get("suppression_first", False),
                rationale=data.get("cultural_bridge_explanation", "M1 cultural bridge.")
            )
        except Exception as e:
            logger.warning("[InterventionEngine] LLM failed: %s", e)
            return self._cultural_bridge_rules(gap, timing)

    def _cultural_bridge_rules(self, gap: GapAnalysis,
                                timing: TimingDecision) -> Intervention:
        return Intervention(
            strategy=InterventionStrategy.CULTURAL_BRIDGE,
            m_level="M1",
            ar_active=True,
            ar_instruction="CULTURAL_SCHEMA_ADAPTATION",
            haptic_active=False,
            voice_active=True,
            voice_message="Contesto diverso. Segui le indicazioni locali.",
            suppression_first=gap.suppression_required,
            rationale="M1 cultural bridge (rule-based fallback)."
        )

    # ── M2 Deep Translation ───────────────────────────────────────────────────

    def _deep_translation(self, gap: GapAnalysis, scenario: str,
                           subject_profile: Optional[dict],
                           environment_profile: Optional[dict],
                           timing: TimingDecision) -> Intervention:
        """Full bidirectional schema translation — daily domain only."""
        if _LLM_AVAILABLE and subject_profile:
            return self._deep_translation_llm(gap, scenario, subject_profile,
                                              environment_profile)
        return self._deep_translation_rules()

    def _deep_translation_rules(self) -> Intervention:
        """Rule-based M2 output. Terminal: never re-enters the LLM path."""
        return Intervention(
            strategy=InterventionStrategy.DEEP_TRANSLATION,
            m_level="M2",
            ar_active=False,
            voice_active=True,
            voice_message="Schema diverso rilevato. Adattamento in corso.",
            rationale="M2 deep translation (rule-based fallback)."
        )

    def _deep_translation_llm(self, gap: GapAnalysis, scenario: str,
                               subject_profile: dict,
                               environment_profile: Optional[dict]) -> Intervention:
        prompt = f"""Full bidirectional schema translation.
Gap: {gap.gap_type.value} — {gap.active_schema} vs {gap.expected_schema}
Scenario: {scenario}
Subject personal topology: {json.dumps(subject_profile, ensure_ascii=False)}
Environment: {json.dumps(environment_profile or {}, ensure_ascii=False)}

Generate deep translation preserving diversity of both schemas.
Voice: max 9 words."""
        try:
            resp = _CLIENT.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                system=TRANSLATION_SYSTEM,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip().replace("```json","").replace("```","").strip()
            data = json.loads(raw)
            return Intervention(
                strategy=InterventionStrategy.DEEP_TRANSLATION,
                m_level="M2",
                ar_active=False,
                voice_active=True,
                voice_message=data.get("voice_message", ""),
                rationale=data.get("cultural_bridge_explanation", "M2 deep translation.")
            )
        except Exception as e:
            logger.warning("[InterventionEngine] LLM failed: %s", e)
            # Return the rule-based intervention directly. Re-entering
            # _deep_translation() here used to loop straight back into this
            # method with gap=None and crash on gap.gap_type outside the try.
            return self._deep_translation_rules()
