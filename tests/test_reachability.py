"""
Reachability tests for the M2 friction layer.

The audit found that the headline M2 feature was gated behind numbers the
pipeline could not produce:

  * SARS through TAAAAgent maxed out at ~0.52 against documented thresholds of
    0.62 (balanced) and 0.75 (conservative);
  * only 2 of 5 RiskClass members were ever produced (`none`,
    `unresolved_ambiguity`);
  * RiskClass.IGNORANCE required user_confidence <= 0.35 while the extractor's
    floor with agent defaults is 0.415 — so the ignorance half of the
    framework's central distinction could not be produced at all;
  * GatedM2Memory.create_sandbox was unreachable, because the branch was gated
    on operational_update_allowed, which is False in OPERATIONAL mode.

These tests fail if any of that comes back. They go through TAAAAgent, not
through hand-constructed CognitiveEvents, because the hand-constructed path was
never the broken one.
"""

import itertools
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import components.gap_detector as gap_detector
import components.intervention_engine as intervention_engine
from components.friction_trigger import (
    CognitiveEvent, FrictionTriggerEngine, GatedM2Memory, LearningMode,
    M2Orchestrator, RiskClass, SafetyGovernor, TriggerState,
)
from components.signal_extractor import SignalExtractor
from core.taaa_agent import TAAAAgent


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Force the rule-based path so results do not depend on an API key."""
    monkeypatch.setattr(gap_detector, "_LLM_AVAILABLE", False)
    monkeypatch.setattr(intervention_engine, "_LLM_AVAILABLE", False)


# ── The sweep ────────────────────────────────────────────────────────────────

TEXTS = [
    "The supplier shall use reasonable efforts to restore the critical service "
    "as soon as possible.",
    "Obviously the approval process is clear. Everyone knows the risk of "
    "downtime, and as we agreed the sign-off is a formality.",
    "I think maybe we should consider a different approach. I'm not certain, "
    "I'm not sure, perhaps, could you clarify?",
    "He said yes. Then he remained silent and looked away. A long silence.",
    "Delivery is scheduled for 15 March 2026 at 09:00 CET.",
]
DOMAINS = ["daily", "clinical", "medical", "contract", "negotiation",
           "general", "project"]
CULTURES = [None, "western_northern_european", "east_asian", "talmudic_academic"]
ENVIRONMENTS = ["", "east_asian", "western_northern_european",
                "biomedical_professional"]
PROFESSIONS = [None, "doctor", "engineer_civil", "manager"]
STRESSES = [0.0, 0.5, 1.0]


def _sweep():
    """Run the cartesian product through TAAAAgent.process().

    Deliberately the full public path, not a hand-built CognitiveEvent: the
    defects being guarded here (the hardcoded domain, the pinned
    consequence_score) all lived between process() and the M2 orchestrator, and
    a test that constructs its own event walks straight past them.
    """
    agent = TAAAAgent(simulation_mode=True, verbose=False)

    # Patched here rather than via the function-scoped `no_llm` fixture, because
    # the sweep is module-scoped and would otherwise run outside it.
    with mock.patch.object(gap_detector, "_LLM_AVAILABLE", False), \
            mock.patch.object(intervention_engine, "_LLM_AVAILABLE", False):
        for n, (text, domain, culture, env, profession, stress) in enumerate(
                itertools.product(TEXTS, DOMAINS, CULTURES, ENVIRONMENTS,
                                  PROFESSIONS, STRESSES)):
            subject_id = f"s{n}"
            agent.register_subject(subject_id, culture=culture,
                                   profession=profession)
            result = agent.process(
                subject_id=subject_id,
                scenario=text,
                domain=domain,
                environment_context=env,
                stress_estimate=stress,
            )
            assert result.m2_decision is not None, \
                "non-emergency cycle scored no M2 decision"
            yield result.m2_decision


@pytest.fixture(scope="module")
def sweep_results():
    return list(_sweep())


def test_every_risk_class_is_reachable(sweep_results):
    """All five RiskClass members must be producible from real extractor output.

    Before the fixes only {none, unresolved_ambiguity} appeared:
      - IGNORANCE            needed user_confidence <= 0.35 vs a 0.415 floor
      - ACTIVE_INTERFERENCE  needed domain_distance >= 0.50, reachable
      - HIGH_CONSEQUENCE     needed consequence >= 0.80, pinned at 0.40 because
                             _propose_m2_update hardcoded domain="daily"
    """
    seen = {d.risk_class for d in sweep_results}
    missing = set(RiskClass) - seen
    assert not missing, f"unreachable RiskClass members: {sorted(m.value for m in missing)}"


def test_every_trigger_state_is_reachable(sweep_results):
    """INACTIVE / MONITORING / ACTIVE — the three states of Addendum v0.5 §5."""
    seen = {d.trigger.state for d in sweep_results}
    missing = set(TriggerState) - seen
    assert not missing, f"unreachable TriggerState members: {sorted(m.value for m in missing)}"


def test_documented_thresholds_are_inside_the_reachable_range(sweep_results):
    """The docstring's tuning points must be numbers the pipeline can hit.

    Fails if the reachable SARS maximum drops below the conservative tuning
    point of 0.65 — which is what the old 0.62/0.75 documentation did against a
    measured ceiling of 0.52.
    """
    scores = [d.trigger.score for d in sweep_results]
    assert min(scores) < FrictionTriggerEngine.MONITORING_THRESHOLD
    assert max(scores) >= 0.65, (
        f"max reachable SARS is {max(scores):.4f}; the documented conservative "
        f"threshold of 0.65 is unreachable"
    )
    assert max(scores) >= FrictionTriggerEngine.DEFAULT_THRESHOLD


def test_consequence_score_is_not_pinned(sweep_results):
    """domain must reach SignalExtractor. Pinned at 0.40 before the fix."""
    # Re-derive from the same inputs the sweep used.
    extractor = SignalExtractor()
    values = {
        extractor.from_text("x", domain=d).consequence_score for d in DOMAINS
    }
    assert len(values) > 1, f"consequence_score collapsed to {values}"
    assert max(values) >= 0.80


def test_ignorance_is_producible_through_the_agent():
    """The ignorance half of ignorance-vs-interference, end to end.

    The extractor's user_confidence floor with the behavioural signals the agent
    supplies is 0.10*0.65 + 0.20 + 0.15 = 0.415, so a cut-off of 0.35 was
    strictly unreachable. This asserts both the floor and that the cut-off sits
    above it.
    """
    from components.friction_trigger import SchemaRiskClassifier

    floor = 0.10 * 0.65 + 0.20 + 0.15
    assert abs(floor - 0.415) < 1e-9
    assert SchemaRiskClassifier.IGNORANCE_CONFIDENCE_MAX > floor

    agent = TAAAAgent(simulation_mode=True, verbose=False)
    agent.register_subject("hesitant", culture="western_northern_european")
    result = agent.process(
        subject_id="hesitant",
        scenario=("I think maybe we should wait. I'm not sure, perhaps, "
                  "could you clarify? I don't understand what was agreed."),
        domain="project",
        current_action="hesitates and looks around",
        environment_context="east_asian",
        stress_estimate=0.1,
    )
    proposal = result.m2_update_proposal
    assert proposal is not None
    assert proposal["risk_class"] == RiskClass.IGNORANCE.value, proposal
    assert proposal["recommendation"] == "provide_missing_context"


def test_high_consequence_schema_gap_needs_the_real_domain():
    """The same event is classified differently once `domain` is threaded.

    This is the regression test for taaa_agent.py hardcoding domain="daily".
    """
    extractor = SignalExtractor()
    orchestrator = M2Orchestrator()
    text = ("The vendor will use reasonable efforts to restore the critical "
            "service as soon as possible after downtime.")
    kwargs = dict(subject_culture="western_northern_european",
                  environment_culture="east_asian")

    as_daily = orchestrator.process(extractor.from_text(text, domain="daily", **kwargs))
    as_contract = orchestrator.process(extractor.from_text(text, domain="contract", **kwargs))

    assert as_daily.risk_class != RiskClass.HIGH_CONSEQUENCE_SCHEMA_GAP
    assert as_contract.risk_class == RiskClass.HIGH_CONSEQUENCE_SCHEMA_GAP
    assert as_contract.recommendation == "request_human_expert_review"
    assert as_contract.trigger.score > as_daily.trigger.score


def test_sandbox_branch_is_reachable_from_operational_observation():
    """GatedM2Memory.create_sandbox must be reachable in OPERATIONAL mode.

    It was not: the branch was gated on operational_update_allowed, which is
    False for OPERATIONAL by design. Capture is now a weaker permission than
    update, and the C0 -> C3 publication gate still holds.
    """
    memory = GatedM2Memory()
    orchestrator = M2Orchestrator(memory=memory)
    event = SignalExtractor().from_text(
        "The deadline is flexible: deliver as soon as possible, when convenient.",
        domain="project",
    )
    event.mode = LearningMode.OPERATIONAL

    decision = orchestrator.process(event)
    assert decision.risk_class != RiskClass.NONE
    assert decision.sandbox_update_created is True
    assert memory.counts["sandbox"] == 1
    # The invariant still holds: operational update is still refused ...
    assert decision.operational_update_allowed is False
    # ... and a C0 hypothesis still cannot be published operationally.
    with pytest.raises(KeyError):
        memory.publish_operational(decision.proposed_schema.id)


def test_high_risk_domains_still_withhold_sandbox_capture():
    """Capture is weaker than update, not unconditional."""
    governor = SafetyGovernor()
    operational_medical = CognitiveEvent("x", "medical", mode=LearningMode.OPERATIONAL)
    sandbox_medical = CognitiveEvent("x", "medical", mode=LearningMode.SANDBOX)
    operational_project = CognitiveEvent("x", "project", mode=LearningMode.OPERATIONAL)

    assert governor.sandbox_capture_allowed(operational_medical) is False
    assert governor.sandbox_capture_allowed(sandbox_medical) is True
    assert governor.sandbox_capture_allowed(operational_project) is True
    # The stronger permission is unchanged.
    assert governor.operational_update_allowed(operational_project) is False


def test_sars_weights_match_addendum_v0_5():
    """Addendum v0.5 §4: .25 / .30 / .20 / .15 / .10, threshold 0.55."""
    assert FrictionTriggerEngine.WEIGHTS == {
        "ambiguity":           0.25,
        "domain":              0.30,
        "consequence":         0.20,
        "confidence_mismatch": 0.15,
        "stress":              0.10,
    }
    assert FrictionTriggerEngine.DEFAULT_THRESHOLD == 0.55
    assert sum(FrictionTriggerEngine.WEIGHTS.values()) == pytest.approx(1.0)
