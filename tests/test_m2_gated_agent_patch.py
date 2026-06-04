"""Regression tests for gated M2 integration in TAAAAgent."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.taaa_agent import TAAAAgent


def test_daily_gap_creates_pending_proposal_without_mutating_m2_topology():
    agent = TAAAAgent(simulation_mode=True, verbose=False)
    profile = agent.register_subject(
        "david", culture="western_northern_european", profession="engineer_civil"
    )

    # This scenario should create a gap in most TAAA configurations.
    result = agent.process(
        subject_id="david",
        scenario=(
            "The supplier shall use reasonable efforts to restore the critical service "
            "as soon as possible. David clearly reads it as a hard SLA."
        ),
        domain="daily",
        current_action="approve_contract_clause",
        environment_context="east_asian",
        stress_estimate=0.25,
    )

    assert result.m2_update_proposal is not None
    assert len(profile.m2_update_queue) == 1
    assert profile.m2_topology == {}
    assert profile.m2_update_queue[0]["status"] == "pending_review"
    assert profile.m2_update_queue[0]["operational_update_allowed"] is False


def test_m2_proposal_requires_explicit_approval_to_enter_topology():
    agent = TAAAAgent(simulation_mode=True, verbose=False)
    profile = agent.register_subject(
        "david", culture="western_northern_european", profession="engineer_civil"
    )
    result = agent.process(
        subject_id="david",
        scenario=(
            "The supplier shall use reasonable efforts to restore the critical service "
            "as soon as possible. David clearly reads it as a hard SLA."
        ),
        domain="daily",
        current_action="approve_contract_clause",
        environment_context="east_asian",
        stress_estimate=0.20,
    )

    proposal_id = result.m2_update_proposal["proposal_id"]
    approved = agent.approve_m2_proposal("david", proposal_id, reviewer="marco")

    assert approved["status"] == "validated"
    assert approved["reviewer"] == "marco"
    assert len(profile.m2_topology) == 1
    assert profile.m2_update_queue[0]["status"] == "approved"
