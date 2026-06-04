"""
TAAA — REST API + Main Entry Point

Endpoints:
  GET  /status                → agent status + M0 registry summary
  GET  /m0/schemas            → all M0 schemas
  GET  /m0/visual_cliff       → visual cliff case (biological grounding demo)
  GET  /m0/shinjuku           → Shinjuku emergency case
  POST /subject/register      → register a new subject
  GET  /subject/<id>          → subject profile + M2 topology size
  POST /process               → run one pipeline cycle
  GET  /m1/interference_risk  → M1 interference risk between two profiles
  POST /cav/validate          → Cultural Adversarial Validator
  POST /demo/<scenario>       → run a demo scenario
  GET  /stats                 → session statistics
"""

import sys
import os
import threading

sys.path.insert(0, os.path.dirname(__file__))

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

from flask import Flask, jsonify, request
from core.taaa_agent import TAAAAgent
from schema_memory.m0_archetypes import M0
from schema_memory.m1_priors import M1
from components.timing_controller import RegressionCurveProfile
from validators.cultural_adversarial import CulturalAdversarialValidator


def create_app(agent: TAAAAgent) -> Flask:
    app = Flask(__name__)
    cav = CulturalAdversarialValidator()

    @app.get("/status")
    def status():
        return jsonify({
            "agent": "TAAA v0.4",
            "m0_schemas": len(M0.all_schemas()),
            "m0_emergency_subset": len(M0.emergency_subset()),
            "subjects_registered": len(agent._subjects),
            "total_cycles": agent.stats().get("total_cycles", 0),
            "llm_available": agent.intervention_engine._LLM_AVAILABLE
                             if hasattr(agent.intervention_engine, '_LLM_AVAILABLE')
                             else "unknown",
        })

    @app.get("/m0/schemas")
    def m0_schemas():
        return jsonify({
            "summary": M0.summary(),
            "emergency_subset": [
                {
                    "name": s.name,
                    "primitives": [p.label for p in s.primitives],
                    "emergency_relevance": s.emergency_relevance,
                    "biological_grounding": s.biological_grounding[:150] + "...",
                    "ar_output": s.ar_output,
                    "haptic_pattern": s.haptic_pattern,
                }
                for s in M0.emergency_subset()
            ]
        })

    @app.get("/m0/visual_cliff")
    def visual_cliff():
        return jsonify(M0.visual_cliff_case())

    @app.get("/m0/shinjuku")
    def shinjuku():
        return jsonify(M0.shinjuku_case())

    @app.post("/subject/register")
    def register_subject():
        body = request.json or {}
        curve_type = body.get("regression_curve", "default_civilian")
        curves = {
            "default_civilian":       RegressionCurveProfile.default_civilian(),
            "emergency_professional": RegressionCurveProfile.emergency_professional(),
            "high_anxiety_trait":     RegressionCurveProfile.high_anxiety_trait(),
        }
        profile = agent.register_subject(
            subject_id=body.get("subject_id", "anonymous"),
            culture=body.get("culture"),
            profession=body.get("profession"),
            age=body.get("age"),
            regression_curve=curves.get(curve_type),
        )
        return jsonify({
            "subject_id": profile.subject_id,
            "m1_prior": profile.m1_prior,
            "regression_curve": profile.regression_curve.profile_id,
        })

    @app.get("/subject/<subject_id>")
    def get_subject(subject_id):
        profile = agent.get_subject(subject_id)
        if not profile:
            return jsonify({"error": "subject_not_found"}), 404
        return jsonify({
            "subject_id": profile.subject_id,
            "culture": profile.culture,
            "profession": profile.profession,
            "m1_prior": profile.m1_prior,
            "m2_events": len(profile.m2_topology),
            "interaction_count": profile.interaction_count,
            "regression_curve": profile.regression_curve.profile_id
                                 if profile.regression_curve else "default",
        })

    @app.post("/process")
    def process():
        body = request.json or {}
        result = agent.process(
            subject_id=body.get("subject_id", "anonymous"),
            scenario=body.get("scenario", ""),
            domain=body.get("domain", "daily"),
            current_action=body.get("current_action"),
            environment_context=body.get("environment_context", ""),
            stress_estimate=float(body.get("stress_estimate", 0.2)),
            paaa_hrv=body.get("paaa_hrv"),
            paaa_gsr=body.get("paaa_gsr"),
        )
        return jsonify({
            "tick":            result.tick,
            "latency_ms":      result.latency_ms,
            "domain":          result.domain,
            "gap": {
                "type":                result.gap.gap_type.value,
                "confidence":          result.gap.confidence,
                "active_schema":       result.gap.active_schema,
                "suppression_required": result.gap.suppression_required,
                "rationale":           result.gap.rationale,
            },
            "interference": {
                "schema":      result.interference.schema_name,
                "strength":    result.interference.strength,
                "timing_ms":   result.interference.timing_window_ms,
                "strategy":    result.interference.suppression_strategy,
            } if result.interference else None,
            "timing": {
                "m_level":          result.timing.current_m_level.value,
                "stress":           result.timing.stress_estimate,
                "output_type":      result.timing.output_type.value,
                "delay_ms":         result.timing.delay_before_output_ms,
                "paaa_used":        result.timing.paaa_biometrics_used,
            },
            "intervention": {
                "strategy":         result.intervention.strategy.value,
                "m_level":          result.intervention.m_level,
                "ar_active":        result.intervention.ar_active,
                "ar_instruction":   result.intervention.ar_instruction,
                "ar_schema":        result.intervention.ar_schema,
                "haptic_active":    result.intervention.haptic_active,
                "haptic_pattern":   result.intervention.haptic_pattern,
                "voice_active":     result.intervention.voice_active,
                "voice_message":    result.intervention.voice_message,
                "suppression_first": result.intervention.suppression_first,
                "rationale":        result.intervention.rationale,
            },
            "m2_learning_event": result.m2_learning_event,
        })

    @app.get("/m1/interference_risk")
    def interference_risk():
        subject = request.args.get("subject", "western_northern_european")
        environment = request.args.get("environment", "east_asian")
        return jsonify(M1.interference_risk(subject, environment))

    @app.post("/cav/validate")
    def cav_validate():
        body = request.json or {}
        result = cav.validate(
            scenario=body.get("scenario", ""),
            source_schema=body.get("source_schema", ""),
            target_schema=body.get("target_schema", ""),
            subject_profile=body.get("subject_profile"),
            max_cycles=int(body.get("max_cycles", 2)),
        )
        return jsonify({
            "validated_translation":  result.validated_translation,
            "composite_score":        result.composite_score,
            "western_score":          result.western_score,
            "eastern_score":          result.eastern_score,
            "diversity_preserved":    result.diversity_preserved,
            "proposals_evaluated":    result.proposals_evaluated,
            "convergence_note":       result.convergence_note,
            "rosetta_stone_analogy":  result.rosetta_stone_analogy,
        })

    @app.post("/demo/<scenario_name>")
    def demo(scenario_name):
        from scenarios.demo import (
            scenario_shinjuku, scenario_negotiation, scenario_medical
        )
        demos = {
            "shinjuku":    scenario_shinjuku,
            "negotiation": scenario_negotiation,
            "medical":     scenario_medical,
        }
        if scenario_name not in demos:
            return jsonify({"error": f"unknown demo '{scenario_name}'",
                            "available": list(demos.keys())}), 400
        demos[scenario_name](agent)
        return jsonify({"status": "run", "scenario": scenario_name,
                        "see_console": "Demo output printed to server console"})

    @app.get("/stats")
    def stats():
        return jsonify(agent.stats())

    return app


def main():
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    agent = TAAAAgent(simulation_mode=True, verbose=True)

    if mode == "demo":
        from scenarios.demo import run_all
        run_all()

    elif mode == "server":
        def _bg():
            pass  # No background loop needed — TAAA is event-driven
        app = create_app(agent)
        print(f"\n  TAAA REST API → http://localhost:5004")
        print("  Endpoints:")
        print("    GET  /m0/visual_cliff   → paradigm case (biological grounding)")
        print("    GET  /m0/shinjuku       → emergency intervention demo")
        print("    POST /subject/register  → register subject")
        print("    POST /process           → run pipeline cycle")
        print("    POST /cav/validate      → Cultural Adversarial Validator")
        print("    POST /demo/shinjuku     → Shinjuku scenario")
        print("    POST /demo/negotiation  → David/Tanaka negotiation")
        print("    POST /demo/medical      → Lin Mei medical consultation\n")
        app.run(host="0.0.0.0", port=5004, threaded=True)

    elif mode == "both":
        def _demo():
            import time; time.sleep(1)
            from scenarios.demo import run_all; run_all()
        t = threading.Thread(target=_demo, daemon=True)
        t.start()
        app = create_app(agent)
        app.run(host="0.0.0.0", port=5004, threaded=True)

    else:
        print("Usage: python main_taaa.py [demo|server|both]")


if __name__ == "__main__":
    main()
