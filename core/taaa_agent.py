"""
TAAA — Core Agent Orchestrator
Translational Autopoietic Adaptive Agent

Integrates all components into a unified pipeline:
  1. Build subject profile (M0 + M1 prior + M2 if available)
  2. Detect schema gap (ignorance / interference / none)
  3. Predict interference details (if interference detected)
  4. Estimate timing / M-level (via TimingController + PAAA)
  5. Generate intervention (AR substitution / bypass / bridge / translation)
  6. Create gated M2 update proposal when cognitive friction is detected
  7. Return intervention package

Domain switching:
  emergency → M0/M1 only, sub-200ms target, no M2 update/proposal
  any other → M0+M1+M2, human timing, M2 proposals only; no automatic learning

`domain` is a free-form string. "emergency" is the only value with special
routing (M0 forcing, no M2 proposals). Every other value ("daily", "medical",
"contract", "negotiation", ...) runs the non-emergency pipeline and is passed
through unchanged to the SignalExtractor and the SafetyGovernor, which are the
components that actually know what a domain costs.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from schema_memory.m0_archetypes import M0
from schema_memory.m1_priors import M1
from components.gap_detector import (
    detect_gap, predict_interference,
    GapAnalysis, GapType, InterferencePrediction
)
from components.timing_controller import (
    TimingController, RegressionCurveProfile, TimingDecision, MLevel
)
from components.intervention_engine import InterventionEngine, Intervention
from components.signal_extractor import SignalExtractor
from components.friction_trigger import (
    M2Decision, M2Orchestrator, LearningMode, TriggerState
)

logger = logging.getLogger("taaa.agent")


@dataclass
class SubjectProfile:
    """Complete subject profile used by the TAAA pipeline."""
    subject_id: str
    culture: Optional[str] = None
    profession: Optional[str] = None
    age: Optional[int] = None
    environment_context: str = ""     # Current environment cultural context
    m1_prior: dict = field(default_factory=dict)
    m2_topology: dict = field(default_factory=dict)   # Validated operational topology only
    m2_update_queue: list[dict] = field(default_factory=list)  # Pending gated M2 proposals
    regression_curve: Optional[RegressionCurveProfile] = None
    interaction_count: int = 0
    # Per-subject timing controller. The regression curve AND the smoothing
    # history are individual: sharing one controller across subjects mixes one
    # person's stress into another person's M-level.
    timing_controller: Optional[TimingController] = None


@dataclass
class PipelineResult:
    """Complete result of one TAAA processing cycle."""
    tick: int
    timestamp: float
    latency_ms: float
    domain: str

    subject_profile: SubjectProfile
    gap: GapAnalysis
    interference: Optional[InterferencePrediction]
    timing: TimingDecision
    intervention: Intervention

    # Gated M2: was a pending update proposal created?
    m2_learning_event: bool = False  # backward-compatible alias: True means proposal, not automatic learning
    m2_update_proposal: Optional[dict] = None
    # The M2 decision for this cycle, present even when no proposal was queued.
    # The SARS score is computed either way; hiding it when it is below threshold
    # is what made `m2_proposals: 0` in the demo impossible to interpret.
    m2_decision: Optional[M2Decision] = None


class TAAAAgent:
    """
    TAAA — Translational Autopoietic Adaptive Agent.

    Main orchestrator. Integrates M0/M1/M2 schema memory,
    gap detection, interference prediction, timing control,
    and intervention generation.
    """

    def __init__(self, simulation_mode: bool = True, verbose: bool = True):
        self.simulation_mode = simulation_mode
        self.verbose = verbose

        # Core components
        self.m0 = M0
        self.m1 = M1
        # NOTE: there is deliberately no agent-level TimingController.
        # Each SubjectProfile owns one (see register_subject).
        self.intervention_engine = InterventionEngine()
        self.signal_extractor = SignalExtractor()
        self.m2_orchestrator = M2Orchestrator()

        # State
        self._tick = 0
        self._subjects: dict[str, SubjectProfile] = {}
        self._interaction_log: list[PipelineResult] = []

        # Optional observer, called once per completed cycle with
        # (event_type: str, payload: dict). The AR display server sets this to
        # its SSE push function (see api/ar_display.register_ar_routes) so the
        # HUD renders real pipeline output instead of canned values.
        self.event_sink: Optional[Callable[[str, dict], None]] = None

        logger.info("[TAAA] Agent initialized. simulation=%s", simulation_mode)

    # ── Subject Management ────────────────────────────────────────────────────

    def register_subject(self, subject_id: str,
                         culture: Optional[str] = None,
                         profession: Optional[str] = None,
                         age: Optional[int] = None,
                         regression_curve: Optional[RegressionCurveProfile] = None) -> SubjectProfile:
        """Register a new subject and build their initial M1 prior."""
        m1_prior = self.m1.build_prior(culture=culture, profession=profession, age=age)

        curve = regression_curve or RegressionCurveProfile.default_civilian()
        profile = SubjectProfile(
            subject_id=subject_id,
            culture=culture,
            profession=profession,
            age=age,
            m1_prior=m1_prior,
            regression_curve=curve,
            # One controller per subject. Registering a second subject must not
            # re-calibrate the first one, and must not inherit their stress EMA.
            timing_controller=TimingController(curve),
        )

        self._subjects[subject_id] = profile
        logger.info("[TAAA] Subject registered: %s (culture=%s, profession=%s)",
                    subject_id, culture, profession)
        return profile

    def get_subject(self, subject_id: str) -> Optional[SubjectProfile]:
        return self._subjects.get(subject_id)

    # ── Main Pipeline ─────────────────────────────────────────────────────────

    def process(self,
                subject_id: str,
                scenario: str,
                domain: str = "daily",
                current_action: Optional[str] = None,
                environment_context: str = "",
                stress_estimate: float = 0.2,
                paaa_hrv: Optional[float] = None,
                paaa_gsr: Optional[float] = None) -> PipelineResult:
        """
        Run one complete TAAA pipeline cycle.

        subject_id: registered subject
        scenario: natural language description of the situation
        domain: free-form. "emergency" forces the M0 path and suppresses M2
                proposals; anything else ("daily", "medical", "contract",
                "negotiation", ...) runs the standard pipeline and is passed
                through to the SignalExtractor / SafetyGovernor verbatim.
        current_action: what the person is doing / about to do
        environment_context: cultural context of the environment
        stress_estimate: 0–1 from MAAA L3 / PAAA
        paaa_hrv/gsr: real-time biometrics from PAAA
        """
        t0 = time.time()
        self._tick += 1

        profile = self._subjects.get(subject_id)
        if not profile:
            profile = self.register_subject(subject_id)
        profile.environment_context = environment_context
        profile.interaction_count += 1

        # ── Step 1: Build subject context dict ────────────────────────────────
        subject_ctx = {
            "subject_id": subject_id,
            "culture": profile.culture,
            "profession": profile.profession,
            "age": profile.age,
            "environment_context": environment_context,
            "m1_prior": profile.m1_prior,
            "m2_available": bool(profile.m2_topology),
            "interaction_count": profile.interaction_count,
        }

        # ── Step 2: Gap Detection ──────────────────────────────────────────────
        gap: GapAnalysis = detect_gap(
            scenario=scenario,
            subject_profile=subject_ctx,
            current_action=current_action,
            domain=domain,
        )

        # ── Step 3: Interference Prediction ───────────────────────────────────
        interference: Optional[InterferencePrediction] = None
        if gap.gap_type == GapType.INTERFERENCE:
            interference = predict_interference(gap, scenario, subject_ctx)

        # ── Step 4: Timing / M-level ───────────────────────────────────────────
        # Per-subject controller: stress history never crosses subjects.
        timing: TimingDecision = profile.timing_controller.decide(
            stress_estimate=stress_estimate,
            paaa_hrv=paaa_hrv,
            paaa_gsr=paaa_gsr,
            domain=domain,
            interference_timing_window_ms=(
                interference.timing_window_ms if interference else None
            ),
        )

        # Emergency domain: force M0 if stress significant
        if domain == "emergency" and stress_estimate > 0.4:
            timing.current_m_level = MLevel.M0

        # ── Step 5: Intervention Generation ───────────────────────────────────
        env_profile = {"context": environment_context} if environment_context else None
        intervention: Intervention = self.intervention_engine.generate(
            gap=gap,
            timing=timing,
            interference=interference,
            scenario=scenario,
            subject_profile=subject_ctx,
            environment_profile=env_profile,
            domain=domain,
        )

        # ── Step 6: Gated M2 proposal — non-emergency only, no auto learning ──
        m2_event = False
        m2_proposal = None
        m2_decision = None
        if domain != "emergency":
            m2_decision, m2_proposal = self._propose_m2_update(
                profile=profile,
                gap=gap,
                intervention=intervention,
                scenario=scenario,
                domain=domain,
                environment_context=environment_context,
                stress_estimate=stress_estimate,
            )
            m2_event = m2_proposal is not None

        # ── Step 7: Logging and output ─────────────────────────────────────────
        latency_ms = (time.time() - t0) * 1000
        result = PipelineResult(
            tick=self._tick,
            timestamp=time.time(),
            latency_ms=round(latency_ms, 2),
            domain=domain,
            subject_profile=profile,
            gap=gap,
            interference=interference,
            timing=timing,
            intervention=intervention,
            m2_learning_event=m2_event,
            m2_update_proposal=m2_proposal,
            m2_decision=m2_decision,
        )
        self._interaction_log.append(result)

        if self.verbose:
            self._print_result(result)

        if self.event_sink is not None:
            try:
                self.event_sink("pipeline_cycle", self.result_to_dict(result))
            except Exception as e:   # an observer must never break the pipeline
                logger.warning("[TAAA] event_sink failed: %s", e)

        return result

    @staticmethod
    def result_to_dict(r: PipelineResult) -> dict:
        """Serialise a PipelineResult. Single source of truth for /process,
        the AR event stream and anything else that renders a cycle."""
        return {
            "tick":       r.tick,
            "latency_ms": r.latency_ms,
            "domain":     r.domain,
            "subject_id": r.subject_profile.subject_id,
            "gap": {
                "type":                 r.gap.gap_type.value,
                "detector":             r.gap.detector,
                "rule_id":              r.gap.rule_id,
                "llm_confidence":       r.gap.confidence,
                "evidence":             r.gap.evidence,
                "active_schema":        r.gap.active_schema,
                "expected_schema":      r.gap.expected_schema,
                "suppression_required": r.gap.suppression_required,
                "rationale":            r.gap.rationale,
            },
            "interference": {
                "schema":    r.interference.schema_name,
                "strength":  r.interference.strength,
                "timing_ms": r.interference.timing_window_ms,
                "strategy":  r.interference.suppression_strategy,
            } if r.interference else None,
            "timing": {
                "m_level":     r.timing.current_m_level.value,
                "stress":      r.timing.stress_estimate,
                "output_type": r.timing.output_type.value,
                "delay_ms":    r.timing.delay_before_output_ms,
                "paaa_used":   r.timing.paaa_biometrics_used,
                "curve":       r.timing.rationale,
            },
            "intervention": {
                "strategy":          r.intervention.strategy.value,
                "m_level":           r.intervention.m_level,
                "ar_active":         r.intervention.ar_active,
                "ar_instruction":    r.intervention.ar_instruction,
                "ar_schema":         r.intervention.ar_schema,
                "haptic_active":     r.intervention.haptic_active,
                "haptic_pattern":    r.intervention.haptic_pattern,
                "voice_active":      r.intervention.voice_active,
                "voice_message":     r.intervention.voice_message,
                "suppression_first": r.intervention.suppression_first,
                "rationale":         r.intervention.rationale,
            },
            "m2_learning_event":  r.m2_learning_event,
            "m2_update_proposal": r.m2_update_proposal,
            "m2": {
                "sars":                       r.m2_decision.trigger.score,
                "trigger_state":              r.m2_decision.trigger.state.value,
                "risk_class":                 r.m2_decision.risk_class.value,
                "recommendation":             r.m2_decision.recommendation,
                "operational_update_allowed": r.m2_decision.operational_update_allowed,
                "sandbox_update_created":     r.m2_decision.sandbox_update_created,
            } if r.m2_decision else None,
        }

    def _propose_m2_update(self, profile: SubjectProfile, gap: GapAnalysis,
                           intervention: Intervention, scenario: str,
                           domain: str = "daily",
                           environment_context: str = "",
                           stress_estimate: float = 0.0
                           ) -> tuple[M2Decision, Optional[dict]]:
        """Create a gated M2 update proposal without mutating operational M2.

        Returns (decision, proposal). The decision is always returned so that
        the SARS score is visible even when nothing was queued.

        This replaces the earlier interaction-archaeology auto-update. Real-world
        daily interactions can suggest schema hypotheses, but they cannot modify
        profile.m2_topology directly. Promotion requires explicit validation via
        approve_m2_proposal().

        `domain` is the caller's real domain. It must reach the SignalExtractor
        (consequence_score) and the SafetyGovernor (HIGH_RISK_DOMAINS). It used
        to be hardcoded to "daily", which pinned consequence_score at the 0.40
        default and made every high-risk domain invisible to the governor.
        """
        event = self.signal_extractor.from_text(
            text=scenario,
            domain=domain,
            subject_id=profile.subject_id,
            subject_culture=profile.culture,
            subject_profession=profile.profession,
            environment_culture=environment_context or None,
            paaa_stress=stress_estimate,
        )
        event.mode = LearningMode.OPERATIONAL
        decision = self.m2_orchestrator.process(event)

        # Queue proposals only when the M2 friction trigger is active or a
        # concrete schema risk is detected. No-op for ordinary clear flows.
        if decision.trigger.state != TriggerState.ACTIVE and decision.risk_class.value == "none":
            return decision, None

        # In operational mode the SafetyGovernor must block direct updates.
        proposal = {
            "proposal_id": f"m2p_{len(profile.m2_update_queue)}",
            "status": "pending_review",
            "source": "operational_observation",
            "scenario_hash": hash(scenario[:100]),
            "domain": domain,
            "gap_type": gap.gap_type.value,
            "active_schema": gap.active_schema,
            "intervention": intervention.strategy.value,
            "m_level": str(intervention.m_level),
            "sars": decision.trigger.score,
            "trigger_state": decision.trigger.state.value,
            "risk_class": decision.risk_class.value,
            "recommendation": decision.recommendation,
            "operational_update_allowed": decision.operational_update_allowed,
            "sandbox_update_created": decision.sandbox_update_created,
            "notes": decision.notes,
        }
        profile.m2_update_queue.append(proposal)
        logger.debug("[TAAA] M2 proposal queued for %s: %s", profile.subject_id, proposal)
        return decision, proposal

    def approve_m2_proposal(self, subject_id: str, proposal_id: str,
                            reviewer: str = "human",
                            confidence_level: str = "C3_domain_validated") -> dict:
        """Promote a pending M2 proposal into operational topology after review.

        This is intentionally explicit and auditable. It is the only supported
        path from operational observation to profile.m2_topology.
        """
        profile = self._subjects.get(subject_id)
        if not profile:
            raise KeyError(f"Unknown subject: {subject_id}")
        for proposal in profile.m2_update_queue:
            if proposal["proposal_id"] == proposal_id:
                if proposal["status"] != "pending_review":
                    raise ValueError(f"Proposal already reviewed: {proposal_id}")
                key = f"validated_{len(profile.m2_topology)}"
                profile.m2_topology[key] = {
                    **proposal,
                    "status": "validated",
                    "reviewer": reviewer,
                    "confidence_level": confidence_level,
                }
                proposal["status"] = "approved"
                logger.info("[TAAA] M2 proposal approved for %s: %s", subject_id, proposal_id)
                return profile.m2_topology[key]
        raise KeyError(f"Proposal not found: {proposal_id}")

    def reject_m2_proposal(self, subject_id: str, proposal_id: str,
                           reviewer: str = "human", reason: str = "") -> dict:
        """Reject a pending M2 proposal without touching operational topology."""
        profile = self._subjects.get(subject_id)
        if not profile:
            raise KeyError(f"Unknown subject: {subject_id}")
        for proposal in profile.m2_update_queue:
            if proposal["proposal_id"] == proposal_id:
                if proposal["status"] != "pending_review":
                    raise ValueError(f"Proposal already reviewed: {proposal_id}")
                proposal["status"] = "rejected"
                proposal["reviewer"] = reviewer
                proposal["rejection_reason"] = reason
                logger.info("[TAAA] M2 proposal rejected for %s: %s", subject_id, proposal_id)
                return proposal
        raise KeyError(f"Proposal not found: {proposal_id}")

    def _print_result(self, r: PipelineResult):
        gap_icons = {
            "none": "○", "ignorance": "?", "interference": "⚠", "partial": "~"
        }
        strategy_icons = {
            "none": "—",
            "ar_substitution": "👁 AR",
            "procedural_bypass": "→ Bypass",
            "calibrated_interruption": "⛔ Interrupt",
            "cultural_bridge": "🌉 Bridge",
            "deep_translation": "🔄 Translate",
        }
        # The rule-based detector reports which rule fired, not a confidence
        # number: it has no calibration data to produce one.
        if r.gap.confidence is not None:
            gap_detail = f"llm_confidence={r.gap.confidence:.2f}"
        else:
            gap_detail = f"rule={r.gap.rule_id}"
        print(f"\n── Tick {r.tick:03d} | {r.latency_ms:.1f}ms | {r.domain.upper()}")
        print(f"  Gap:    {gap_icons.get(r.gap.gap_type.value,'?')} "
              f"{r.gap.gap_type.value.upper()} "
              f"({r.gap.detector}: {gap_detail})")
        if r.interference:
            print(f"  Interf: strength={r.interference.strength:.2f} "
                  f"window={r.interference.timing_window_ms}ms")
        print(f"  M-level: {r.timing.current_m_level.value} "
              f"(stress={r.timing.stress_estimate:.2f})")
        print(f"  Action: {strategy_icons.get(r.intervention.strategy.value,'?')} "
              f"{r.intervention.strategy.value}")
        if r.intervention.voice_message:
            print(f"  Voice:  \"{r.intervention.voice_message}\"")
        if r.intervention.haptic_active:
            print(f"  Haptic: {r.intervention.haptic_pattern}")
        if r.intervention.ar_active:
            print(f"  AR:     {r.intervention.ar_instruction}")

    # ── M0 Direct Access ──────────────────────────────────────────────────────

    def m0_instantiate(self, schema_name: str, context: dict) -> dict:
        return self.m0.instantiate(schema_name, context)

    def m0_visual_cliff(self) -> dict:
        return self.m0.visual_cliff_case()

    def m0_shinjuku(self) -> dict:
        return self.m0.shinjuku_case()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        total = len(self._interaction_log)
        if not total:
            return {"total_cycles": 0}
        gaps = [r.gap.gap_type.value for r in self._interaction_log]
        return {
            "total_cycles":      total,
            "gap_distribution":  {t: gaps.count(t) for t in set(gaps)},
            "m2_proposals":      sum(1 for r in self._interaction_log if r.m2_update_proposal),
            "m2_events":         sum(1 for r in self._interaction_log if r.m2_learning_event),
            "pending_m2_reviews": sum(len(s.m2_update_queue) for s in self._subjects.values()),
            "mean_latency_ms":   round(sum(r.latency_ms for r in self._interaction_log)/total, 2),
            "subjects":          len(self._subjects),
        }
