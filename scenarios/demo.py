"""
TAAA — Demo Scenarios

Four scenarios:
  1. Shinjuku Emergency       — M0 intervention, interference suppression
  2. David/Tanaka Negotiation — cross-cultural schema gap, both directions
  3. Medical Consultation     — high-consequence domain routing
  4. Contract Clause          — the gated M2 proposal queue and its review step

Every "Expected" line in the docstrings below states what the code prints
without an API key. Where the rule-based detector disagrees with the narrative
intent of the scenario, the docstring says so rather than claiming the intent.

Run: python -c "from scenarios.demo import run_all; run_all()"
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.taaa_agent import TAAAAgent
from components.timing_controller import RegressionCurveProfile
from schema_memory.m0_archetypes import M0


DIVIDER = "─" * 70


def scenario_shinjuku(agent: TAAAAgent):
    """
    Scenario 1: Shinjuku station fire.
    Mark, American manager, about to turn in the WRONG direction
    because his habitual spatial schema ("exit is opposite to incoming flow")
    is active but wrong in this environment.

    Prints (rule-based detector, no API key):
      Gap=INTERFERENCE | Strategy=calibrated_interruption | M=M0
    """
    print(f"\n{'═'*70}")
    print("  SCENARIO 1 — SHINJUKU EMERGENCY")
    print("  Mark (US) in Tokyo station fire — interference schema active")
    print(f"{'═'*70}")

    # Show M0 visual cliff case for biological grounding
    print("\n  [M0 Biological Grounding — Visual Cliff Paradigm]")
    vc = agent.m0_visual_cliff()
    print(f"  Schema: {vc['schema']}")
    print(f"  Primitives: {', '.join(vc['primitives'])}")
    print(f"  AR output: {vc['ar_overlay']}")
    print(f"  Cross-species: {', '.join(vc['context']['cross_species'])}")

    print("\n  [Full Shinjuku M0 Scenario]")
    shinjuku = agent.m0_shinjuku()
    print(f"  Interference: {shinjuku['interference_detected']['interference_type'].upper()}")
    print(f"  Wrong direction predicted: {shinjuku['interference_detected']['wrong_direction']}")
    print(f"  Communication channel: {shinjuku['communication_channel']}")
    print(f"  Cultural translation required: {shinjuku['cultural_translation']}")

    print("\n  [TAAA Pipeline — Emergency Mode]")
    agent.register_subject(
        "mark_chicago",
        culture="western_northern_european",
        profession="manager",
        age=42,
        regression_curve=RegressionCurveProfile.default_civilian(),
    )

    result = agent.process(
        subject_id="mark_chicago",
        scenario=(
            "Mark is in Shinjuku station during a fire emergency. "
            "He can see smoke from the left corridor. He is about to turn right "
            "because in American stations the exit is opposite to the main flow, "
            "but in this station the emergency exit is to the left (toward the smoke side). "
            "He is walking confidently toward the wrong exit."
        ),
        domain="emergency",
        current_action="turns toward right corridor — wrong direction — confidently",
        environment_context="east_asian",
        stress_estimate=0.82,
        paaa_hrv=22.0,    # Very low HRV = high stress
        paaa_gsr=0.78,
    )

    print(f"\n  RESULT: Gap={result.gap.gap_type.value.upper()} "
          f"| Strategy={result.intervention.strategy.value} "
          f"| M={result.timing.current_m_level.value}")
    print(f"  Suppression first: {result.intervention.suppression_first}")
    if result.interference:
        print(f"  Schema strength: {result.interference.strength:.2f}")
        print(f"  Timing window: {result.interference.timing_window_ms}ms")
    print(f"  Rationale: {result.intervention.rationale}")


def scenario_negotiation(agent: TAAAAgent):
    """
    Scenario 2: David (US) / Tanaka-san (Japan) negotiation.
    David interprets 'yes' + silence as agreement.
    For Tanaka-san: 'yes' = 'I heard you', silence = respect before indirect refusal.

    Prints (rule-based detector, no API key):
      David:  deep_translation | M=M2   (gap INTERFERENCE)
      Tanaka: none             | M=M2   (gap NONE)

    The asymmetry is real, not a bug being hidden: David's scenario text states
    the divergence explicitly ("In US business culture ... In Japanese culture
    ..."), Tanaka's does not, and the keyword classifier needs the situation to
    state a mismatch before it will call INTERFERENCE. Both sides come out as
    interference only on the LLM path. See README → Status.
    """
    print(f"\n{'═'*70}")
    print("  SCENARIO 2 — INVISIBLE NEGOTIATION (Daily Domain)")
    print("  David (US executive) / Tanaka-san (Osaka) — schema gap both sides")
    print(f"{'═'*70}")

    # Register both subjects
    agent.register_subject(
        "david_us_executive",
        culture="western_northern_european",
        profession="manager",
        age=48,
    )
    agent.register_subject(
        "tanaka_osaka",
        culture="east_asian",
        profession="manager",
        age=55,
    )

    # Check M1 interference risk between the two profiles
    from schema_memory.m1_priors import M1
    risk = M1.interference_risk("western_northern_european", "east_asian")
    print("\n  [M1 Interference Risk Analysis]")
    print(f"  Risk level: {risk['risk'].upper()} (score={risk['score']})")
    print(f"  Conflict dimensions: {', '.join(risk['conflict_dimensions'])}")

    print("\n  [TAAA Pipeline — Daily Mode, David's perspective]")
    result_david = agent.process(
        subject_id="david_us_executive",
        scenario=(
            "David proposed a contract term. Tanaka-san responded 'yes' "
            "and then fell silent. David immediately started discussing next steps, "
            "interpreting the 'yes' as agreement. "
            "In US business culture, 'yes' after a proposal means agreement. "
            "In Japanese culture, 'yes' means 'I have understood your proposal', "
            "and the silence was a respectful space before an indirect refusal. "
            "David's interruption of the silence was perceived as aggressive pressure."
        ),
        # Real domain, not the generic "daily". It reaches SignalExtractor
        # (consequence_score) and SafetyGovernor unchanged.
        domain="negotiation",
        current_action="starts discussing implementation details — assumes agreement",
        environment_context="east_asian",
        stress_estimate=0.15,
    )

    print("\n  [TAAA Pipeline — Daily Mode, Tanaka-san's perspective]")
    result_tanaka = agent.process(
        subject_id="tanaka_osaka",
        scenario=(
            "Tanaka-san said 'yes' to acknowledge hearing David's proposal, "
            "then paused respectfully before preparing an indirect refusal. "
            "David immediately interrupted the silence and started planning next steps "
            "as if agreement had been reached. "
            "From Tanaka-san's perspective, this was aggressive and disrespectful."
        ),
        domain="negotiation",
        current_action="becoming withdrawn — perceives David as aggressive",
        environment_context="western_northern_european",
        stress_estimate=0.35,
    )

    print("\n  BIDIRECTIONAL RESULT:")
    print(f"  David: {result_david.intervention.strategy.value} | "
          f"M={result_david.timing.current_m_level.value}")
    print(f"  Tanaka: {result_tanaka.intervention.strategy.value} | "
          f"M={result_tanaka.timing.current_m_level.value}")


def scenario_medical(agent: TAAAAgent):
    """
    Scenario 3: Lin Mei (Chinese) / US biomedical doctor.
    Lin Mei describes symptoms in Traditional Chinese Medicine terms.
    Doctor has biomedical schema — two incompatible ontologies.

    Prints (rule-based detector, no API key):
      Gap=IGNORANCE | Strategy=deep_translation | M=M2
    IGNORANCE, not PARTIAL: the scenario says the doctor "doesn't have access to
    this mapping" and Lin Mei "cannot answer in this frame" — uncertainty
    markers with no automaticity marker alongside them.
    """
    print(f"\n{'═'*70}")
    print("  SCENARIO 3 — MEDICAL CONSULTATION (Daily Domain)")
    print("  Lin Mei (TCM framework) / Dr. Chen (biomedical framework)")
    print(f"{'═'*70}")

    agent.register_subject(
        "lin_mei_patient",
        culture="east_asian",
        age=58,
    )
    agent.register_subject(
        "dr_chen_biomedical",
        culture="western_northern_european",
        profession="doctor",
        age=45,
    )

    print("\n  [TAAA Pipeline — Doctor's perspective]")
    result = agent.process(
        subject_id="dr_chen_biomedical",
        scenario=(
            "Lin Mei, 58, describes symptoms as 'too much fire in the liver' "
            "and 'blocked energy'. She speaks fluent English but thinks in "
            "Traditional Chinese Medicine (TCM) framework. "
            "Dr. Chen has rigorous biomedical training and no TCM background. "
            "The gap is ontological: two incompatible ways of organizing the body. "
            "Lin Mei's description maps to possible clinical symptoms: "
            "liver inflammation, portal hypertension, or metabolic dysfunction — "
            "but the doctor doesn't have access to this mapping."
        ),
        # "medical" is a SafetyGovernor high-risk domain and a 0.95-consequence
        # domain in SignalExtractor. Passing "daily" here discarded both.
        domain="medical",
        current_action="asking biomedical clarification questions — Lin Mei cannot answer in this frame",
        environment_context="biomedical_professional",
        stress_estimate=0.20,
    )

    print(f"\n  RESULT: Gap={result.gap.gap_type.value.upper()} "
          f"| Strategy={result.intervention.strategy.value} "
          f"| M={result.timing.current_m_level.value}")
    if result.intervention.voice_message:
        print(f"  Suggested bridge: \"{result.intervention.voice_message}\"")


def scenario_contract_m2(agent: TAAAAgent):
    """
    Scenario 4: the gated M2 proposal queue.

    David initials an ambiguous SLA clause. The M2 layer scores the event,
    queues a proposal for review, and does NOT touch his operational schema
    topology. Promotion happens only through approve_m2_proposal().

    Prints (no API key): SARS≈0.56, trigger=active,
    risk=high_consequence_schema_gap, operational_update_allowed=False.
    """
    print(f"\n{'═'*70}")
    print("  SCENARIO 4 — CONTRACT CLAUSE (Gated M2 Proposal Queue)")
    print("  David initials 'reasonable efforts / as soon as possible'")
    print(f"{'═'*70}")

    profile = agent.get_subject("david_us_executive") or agent.register_subject(
        "david_us_executive",
        culture="western_northern_european", profession="manager", age=48,
    )

    result = agent.process(
        subject_id="david_us_executive",
        scenario=(
            "The draft clause says the supplier will use reasonable efforts to "
            "restore the critical service as soon as possible after any downtime "
            "incident. David obviously reads that as a four-hour hard SLA."
        ),
        domain="contract",
        current_action="initials the clause and moves to the next page",
        environment_context="east_asian",
        stress_estimate=0.45,
    )

    proposal = result.m2_update_proposal
    if not proposal:
        print("\n  No M2 proposal queued for this cycle.")
        return

    print("\n  [M2 Friction Trigger — scores computed by SignalExtractor]")
    print(f"  SARS:             {proposal['sars']}  "
          f"(threshold {agent.m2_orchestrator.trigger.threshold})")
    print(f"  Trigger state:    {proposal['trigger_state']}")
    print(f"  Risk class:       {proposal['risk_class']}")
    print(f"  Recommendation:   {proposal['recommendation']}")
    print(f"  Operational update allowed: {proposal['operational_update_allowed']}")

    print("\n  [Gate — before review]")
    print(f"  Pending proposals: {len(profile.m2_update_queue)}")
    print(f"  m2_topology:       {profile.m2_topology}   ← untouched")

    validated = agent.approve_m2_proposal(
        "david_us_executive", proposal["proposal_id"], reviewer="marco"
    )
    print("\n  [Gate — after explicit human review]")
    print(f"  Reviewer:          {validated['reviewer']}")
    print(f"  Confidence level:  {validated['confidence_level']}")
    print(f"  m2_topology keys:  {list(profile.m2_topology)}")


def run_all(agent: TAAAAgent | None = None):
    print(f"\n{DIVIDER}")
    print("  TAAA — Translational Autopoietic Adaptive Agent")
    print("  Demo Scenarios — Working Paper v0.4")
    print(f"{DIVIDER}")
    print("\n  M0 Registry:")
    summary = M0.summary()
    print(f"  Schemas: {summary['total_schemas']} total, "
          f"{summary['emergency_subset_count']} emergency-relevant")
    for s in summary['schemas'][:4]:
        print(f"    [{s['emergency_relevance']:.2f}] {s['name']} "
              f"({s['primitives']} primitives)")

    agent = agent or TAAAAgent(simulation_mode=True, verbose=True)

    scenario_shinjuku(agent)
    scenario_negotiation(agent)
    scenario_medical(agent)
    scenario_contract_m2(agent)

    print(f"\n{DIVIDER}")
    print("  Session Summary")
    print(f"{DIVIDER}")
    stats = agent.stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    run_all()
