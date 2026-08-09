"""
Regression tests for the defects found in the audit.

Each test names the defect it locks down. Every one of them fails if the
corresponding fix is reverted.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import components.gap_detector as gap_detector
import components.intervention_engine as intervention_engine
from components.gap_detector import GapType, detect_gap
from components.intervention_engine import InterventionEngine, InterventionStrategy
from components.outward_perception import OutwardPerceptionLayer, SilenceMonitor
from components.timing_controller import MLevel, RegressionCurveProfile
from core.bilateral_consent import CONSENT_MANAGER
from core.taaa_agent import TAAAAgent
from schema_memory.m0_archetypes import M0, Primitive
from schema_memory.m1_priors import M1
from validators.cultural_adversarial import CulturalAdversarialValidator


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr(gap_detector, "_LLM_AVAILABLE", False)
    monkeypatch.setattr(intervention_engine, "_LLM_AVAILABLE", False)


# ── A. Cross-subject state leak ──────────────────────────────────────────────

def test_timing_controller_is_per_subject_not_shared():
    """One shared TimingController mixed one person's stress into another's.

    Reproduction before the fix: Mark at stress 0.82, then David at 0.15, and
    David was reported at 0.373 — a different M-level and a different
    intervention strategy from the same input.
    """
    agent = TAAAAgent(simulation_mode=True, verbose=False)
    agent.register_subject("mark", culture="western_northern_european")
    agent.register_subject("david", culture="western_northern_european")

    agent.process("mark", "x", domain="daily", stress_estimate=0.82)
    together = agent.process("david", "x", domain="daily", stress_estimate=0.15)

    alone_agent = TAAAAgent(simulation_mode=True, verbose=False)
    alone_agent.register_subject("david", culture="western_northern_european")
    alone = alone_agent.process("david", "x", domain="daily", stress_estimate=0.15)

    assert together.timing.stress_estimate == alone.timing.stress_estimate, (
        f"David reads {together.timing.stress_estimate} after Mark but "
        f"{alone.timing.stress_estimate} alone — stress history is shared"
    )
    assert together.timing.current_m_level == alone.timing.current_m_level
    assert together.timing.stress_estimate == pytest.approx(0.15)
    assert together.timing.current_m_level == MLevel.M2


def test_registering_a_subject_does_not_recalibrate_other_subjects():
    """register_subject() used to call calibrate() on the one shared controller,
    so registering a second subject moved the first onto the second's curve."""
    agent = TAAAAgent(simulation_mode=True, verbose=False)
    responder = agent.register_subject(
        "responder", regression_curve=RegressionCurveProfile.emergency_professional())
    anxious = agent.register_subject(
        "anxious", regression_curve=RegressionCurveProfile.high_anxiety_trait())

    assert responder.timing_controller.curve.profile_id == "emergency_professional"
    assert anxious.timing_controller.curve.profile_id == "high_anxiety_trait"
    assert responder.timing_controller is not anxious.timing_controller

    # And the curves actually produce different M-levels at the same stress.
    hot_responder = agent.process("responder", "x", domain="daily", stress_estimate=0.50)
    hot_anxious = agent.process("anxious", "x", domain="daily", stress_estimate=0.50)
    assert hot_responder.timing.current_m_level == MLevel.M2
    assert hot_anxious.timing.current_m_level == MLevel.M0


# ── B. Crash on LLM failure ──────────────────────────────────────────────────

class _RaisingClient:
    class messages:
        @staticmethod
        def create(*args, **kwargs):
            raise RuntimeError("simulated API failure")


def test_deep_translation_survives_llm_failure(monkeypatch):
    """_deep_translation_llm's fallback re-entered itself with gap=None and
    crashed with AttributeError: 'NoneType' object has no attribute 'gap_type'.

    This is not a corner case: with `anthropic` installed (requirements.txt
    mandates it) and no valid API key, every M2 cycle with a gap hit it.
    """
    monkeypatch.setattr(intervention_engine, "_LLM_AVAILABLE", True)
    monkeypatch.setattr(intervention_engine, "_CLIENT", _RaisingClient)

    agent = TAAAAgent(simulation_mode=True, verbose=False)
    agent.register_subject("mark", culture="western_northern_european")

    result = agent.process(
        subject_id="mark",
        scenario=("Mark walks toward the platform. In American stations the exit "
                  "is opposite to the main flow, but in this station it is not."),
        domain="daily",
        current_action="walks toward the barrier confidently",
        environment_context="east_asian",
        stress_estimate=0.05,     # low stress → M2 → deep translation path
    )

    assert result.timing.current_m_level == MLevel.M2
    assert result.intervention.strategy == InterventionStrategy.DEEP_TRANSLATION
    assert result.intervention.voice_message


def test_cultural_bridge_survives_llm_failure(monkeypatch):
    monkeypatch.setattr(intervention_engine, "_LLM_AVAILABLE", True)
    monkeypatch.setattr(intervention_engine, "_CLIENT", _RaisingClient)

    agent = TAAAAgent(simulation_mode=True, verbose=False)
    agent.register_subject("mark", culture="western_northern_european")
    result = agent.process(
        subject_id="mark",
        scenario="Mark assumes the queue works the way it does at home, but in "
                 "this station it is the opposite direction.",
        domain="daily",
        current_action="walks toward the front",
        environment_context="east_asian",
        stress_estimate=0.45,     # → M1 → cultural bridge path
    )
    assert result.timing.current_m_level == MLevel.M1
    assert result.intervention.strategy == InterventionStrategy.CULTURAL_BRIDGE


# ── C. Gap detection consumes the scenario, and emits no fake confidence ─────

def _ctx(culture="western_northern_european", env="east_asian"):
    return {
        "culture": culture,
        "environment_context": env,
        "m1_prior": M1.build_prior(culture=culture),
    }


def test_benign_scenario_is_not_an_emergency_stop():
    """'walks toward' in the action label used to be sufficient for
    INTERFERENCE with suppression_required=True — an emergency haptic stop for
    someone buying a coffee."""
    gap = detect_gap(
        scenario="He is buying a coffee at the station kiosk. Nothing is wrong.",
        subject_profile=_ctx(),
        current_action="walks toward the counter",
        domain="daily",
    )
    assert gap.gap_type == GapType.NONE
    assert gap.suppression_required is False


def test_rewording_the_action_label_does_not_erase_the_gap():
    """The scenario text was computed (`s = scenario.lower()`) and never used,
    so rewording the caller's action label flipped Shinjuku to NONE."""
    scenario = ("Mark is in Shinjuku station during a fire emergency. He is about "
                "to turn right because in American stations the exit is opposite "
                "to the main flow, but in this station the emergency exit is to "
                "the left. He is walking confidently toward the wrong exit.")

    labelled = detect_gap(scenario, _ctx(), "turns toward the right corridor "
                                            "— wrong direction — confidently", "emergency")
    reworded = detect_gap(scenario, _ctx(), "proceeds to the right corridor", "emergency")

    assert labelled.gap_type == GapType.INTERFERENCE
    assert reworded.gap_type == GapType.INTERFERENCE, \
        "gap detection is still driven only by the action label"
    assert reworded.evidence, "no evidence recorded for the classification"


def test_rules_path_reports_a_rule_id_and_no_confidence_number():
    """0.72 / 0.68 / 0.55 were literals surfaced through /process as `confidence`."""
    for scenario, action, expected in [
        ("Nothing unusual.", "waits", GapType.NONE),
        ("He does not know which platform. He stops and looks around.",
         "asks a member of staff", GapType.IGNORANCE),
    ]:
        gap = detect_gap(scenario, _ctx(), action, "daily")
        assert gap.gap_type is expected
        assert gap.detector == "rules"
        assert gap.confidence is None, \
            f"rules path emitted a confidence number: {gap.confidence}"
        assert gap.rule_id


def test_partial_is_reachable_without_an_api_key():
    """PARTIAL was unreachable on the rules path — the enum member existed but
    nothing could produce it, while the README advertised it."""
    gap = detect_gap(
        scenario=("He assumes the ticket gate works like the one at home, but "
                  "this station uses the opposite convention. He hesitates, "
                  "then looks around, uncertain."),
        subject_profile=_ctx(),
        current_action="walks toward the gate, then stops and looks",
        domain="daily",
    )
    assert gap.gap_type == GapType.PARTIAL
    assert gap.suppression_required is False


def test_env_context_comparison_can_be_true():
    """`any(ctx in env_context ...)` compared M1 phrases like
    'high_context_communication' against culture ids like 'east_asian'. It was
    never true, for any call site, including the README's own curl examples."""
    conflict, evidence = gap_detector._schema_conflict(_ctx())
    assert conflict is True, "western/east-asian pair still reports no conflict"
    assert evidence

    # Same culture on both sides is a definite non-conflict, not "unknown".
    same, _ = gap_detector._schema_conflict(
        _ctx(env="western_northern_european"))
    assert same is False

    # Unknown environment must be tri-state None, never a silent False.
    unknown, _ = gap_detector._schema_conflict(_ctx(env="atlantis"))
    assert unknown is None

    # The literal-label path still works for callers who pass a context phrase.
    labelled, _ = gap_detector._schema_conflict(
        _ctx(env="high_context_communication"))
    assert labelled is True


# ── G. Smaller defects ───────────────────────────────────────────────────────

def test_m1_prior_actually_blends_culture_and_profession():
    """build_prior() advertised profiles_used ['culture','profession'] while the
    profession profile contributed nothing: culture (0.5) always won outright."""
    prior = M1.build_prior(culture="east_asian", profession="doctor")

    assert prior["profiles_used"] == ["culture", "profession"]
    assert prior["source_communities"] == {
        "culture": "east_asian", "profession": "biomedical_professional"}

    # Every dimension is attributed to a source ...
    assert set(prior["dimension_sources"]) == set(M1.PRIOR_DIMENSIONS)
    # ... at least one is genuinely contested between the two profiles ...
    assert prior["contested_dimensions"], "no dimension recorded as contested"
    assert prior["contested_dimensions"]["context_level"] == {
        "culture": "high_context", "profession": "low_context"}
    # ... and at least one is agreed by both, i.e. the profession contributed.
    assert any(src == "culture+profession"
               for src in prior["dimension_sources"].values())

    # The profession's interference contexts survive instead of being dropped.
    assert "traditional_medicine_terminology" in prior["high_interference_contexts"]
    assert "low_context_communication" in prior["high_interference_contexts"]


def test_falling_danger_uses_boundary_not_container():
    """`Primitive.BOUNDARY if hasattr(Primitive,'BOUNDARY') else CONTAINER`
    against an enum with no BOUNDARY silently shipped CONTAINER, while the
    schema's description and ar_output both talk about a boundary."""
    assert hasattr(Primitive, "BOUNDARY")
    schema = M0.get("FALLING_DANGER")
    labels = [p.label for p in schema.primitives]
    assert "BOUNDARY" in labels
    assert "CONTAINER" not in labels
    assert "BOUNDARY" in schema.ar_output


def test_llm_availability_is_actually_readable():
    """`agent.intervention_engine._LLM_AVAILABLE` targets a module global, so
    hasattr() was always False and /status reported "unknown" forever."""
    engine = InterventionEngine()
    assert isinstance(engine.llm_available, bool)
    assert engine.llm_available is intervention_engine._LLM_AVAILABLE


def test_outward_perception_is_deterministic():
    """_simulate_signals picked its phase from wall-clock `time.time() % 10`, so
    a demo could narrate a reading it had not taken."""
    session = CONSENT_MANAGER.create_session("observer_a", "dev_a",
                                             session_type="negotiation")
    CONSENT_MANAGER.join_session(session.invite_token, "other_b", "dev_b")
    try:
        layer = OutwardPerceptionLayer(simulation_mode=True)
        for _ in range(3):
            obs = layer.observe("observer_a", sim_phase="processing")
            assert obs.signals.state.value == "processing"
            assert obs.signals.silence_active is True
            assert obs.trigger_recommendation == "wait"

        listening = layer.observe("observer_a", sim_phase="listening")
        assert listening.signals.state.value == "listening"
        assert listening.trigger_recommendation is None

        with pytest.raises(ValueError):
            layer.observe("observer_a", sim_phase="daydreaming")
    finally:
        CONSENT_MANAGER.end_session(session.session_id)


def test_silence_monitor_does_not_self_certify_its_consent_requirement():
    """It used to return `"requires_bilateral": False` — a component declaring
    its own consent policy. That decision belongs to CONSENT_MANAGER."""
    frame = SilenceMonitor().process_audio_frame(rms_db=-55.0)
    assert "requires_bilateral" not in frame
    assert frame["audio_only"] is True
    assert frame["in_silence"] is True


def test_schemas_for_primitive_is_exercised():
    """Zero call sites before; kept because the primitive index is real."""
    exits = M0.schemas_for_primitive(Primitive.CONTAINER)
    assert [s.name for s in exits] == ["EXIT"]
    assert M0.schemas_for_primitive(Primitive.BOUNDARY)[0].name == "FALLING_DANGER"


# ── F. CAV honesty ───────────────────────────────────────────────────────────

def test_cav_no_key_path_says_so_instead_of_returning_0_5():
    """`composite_score: 0.5` read as a measured validation metric. It was the
    hardcoded no-LLM fallback."""
    report = CulturalAdversarialValidator().run_cycle(
        scenario="negotiation silence",
        source_schema="silence_as_absence",
        target_schema="silence_as_respect",
    )
    assert report.adversarially_validated is False
    assert report.score_basis == "unavailable_no_llm"
    assert report.heuristic_score is None
    assert report.proposals_evaluated == 0
    assert not hasattr(report, "composite_score")
    assert "template" in report.translation


def test_cav_shape_heuristics_are_named_for_what_they_measure():
    cav = CulturalAdversarialValidator()
    short = cav._shape_heuristics("no.")
    long_specific = cav._shape_heuristics(
        "A long proposal, because the two frames diverge, whereas a literal "
        "rendering would collapse them into one. " * 2)
    assert set(short) == {"fidelity_heuristic", "navigability_heuristic",
                          "diversity_heuristic", "robustness_heuristic"}
    assert long_specific["fidelity_heuristic"] > short["fidelity_heuristic"]
    assert long_specific["robustness_heuristic"] > short["robustness_heuristic"]
    # The merger test is a conjunction, and it can be false.
    assert cav._shape_heuristics(
        "we integrate both frames")["diversity_heuristic"] == 0.50


# ── E. The AR layer is wired ─────────────────────────────────────────────────

def test_ar_routes_are_registered_and_driven_by_the_pipeline():
    """register_ar_routes() was never called, so GET /ar returned 404, and
    push_ar_event() had zero call sites."""
    import json
    from main_taaa import create_app
    import api.ar_display as ar_display

    agent = TAAAAgent(simulation_mode=True, verbose=False)
    app = create_app(agent)
    client = app.test_client()

    assert agent.event_sink is ar_display.push_ar_event

    page = client.get("/ar")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "EventSource('/ar/stream')" in body
    assert "SCENARIOS" not in body, "scenario constants are back in the client"
    assert "conf=0.72" not in body

    # Drain the queue, run a real cycle, and check what was pushed.
    while not ar_display._ar_event_queue.empty():
        ar_display._ar_event_queue.get_nowait()

    agent.register_subject("mark", culture="western_northern_european")
    result = agent.process(
        subject_id="mark",
        scenario="Nothing unusual at the kiosk.",
        domain="daily",
        current_action="waits",
        stress_estimate=0.7,
    )
    event = ar_display._ar_event_queue.get_nowait()
    assert event["type"] == "pipeline_cycle"
    assert event["data"]["gap"]["type"] == result.gap.gap_type.value
    assert event["data"]["timing"]["stress"] == result.timing.stress_estimate
    # The payload is JSON-serialisable, i.e. it can actually reach the browser.
    json.dumps(event)


def test_process_endpoint_and_ar_stream_share_one_serialiser():
    from main_taaa import create_app

    agent = TAAAAgent(simulation_mode=True, verbose=False)
    client = create_app(agent).test_client()
    response = client.post("/process", json={
        "subject_id": "curl_user",
        "scenario": "He is buying a coffee at the station kiosk. Nothing is wrong.",
        "domain": "daily",
        "current_action": "walks toward the counter",
        "environment_context": "east_asian",
        "stress_estimate": 0.2,
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["gap"]["type"] == "none"
    assert body["gap"]["detector"] == "rules"
    assert body["gap"]["llm_confidence"] is None
    assert body["gap"]["rule_id"] == "none_no_signal"
    assert body["gap"]["suppression_required"] is False


def test_status_reports_llm_availability_and_sars_configuration():
    from main_taaa import create_app

    agent = TAAAAgent(simulation_mode=True, verbose=False)
    body = create_app(agent).test_client().get("/status").get_json()
    assert body["llm_available"] in (True, False)
    assert body["llm_available"] != "unknown"
    assert body["sars_threshold"] == 0.55
    assert body["sars_weights"]["domain"] == 0.30
    assert body["sars_weights"]["consequence"] == 0.20
