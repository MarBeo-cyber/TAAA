"""
TAAA — Cultural Adversarial Validator (CAV)

Implements the adversarial cross-cultural validation framework
inspired by Ottolino (2026) "AI Curling: pushing the Epistemic Iron Curtain".

Two LLM instances with different cultural priors cross-validate
schema translations. This overcomes the auto-referentiality problem:
a single Western-trained LLM explaining schemas through Western concepts.

CAV is a DAILY DOMAIN component only.
In emergency, translations are pre-computed offline by CAV and
stored as validated patterns in the M0 knowledge graph.

The 8-step cycle (adapted for schema translation):
  G1 → P1 → C2 → R1 → G2 → P2 → C1 → R2

Scoring function:
  Score = w1*FedeltaCulturale + w2*NavigabilitaSoggetto +
          w3*PreservazioneDiversita + w4*Robustezza + w5*CostoLatenza

The Rosetta Stone principle:
  The goal is NOT a neutral arbiter (doesn't exist).
  It is the dynamic equilibrium between culturally situated perspectives,
  each maintaining its legitimacy — like the three scripts on the Stele.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("taaa.cav")

try:
    import anthropic
    _CLIENT = anthropic.Anthropic()
    _LLM_AVAILABLE = True
except Exception:
    _CLIENT = None
    _LLM_AVAILABLE = False


# ── Cultural Prior System Prompts ─────────────────────────────────────────────

WESTERN_ANALYTIC_PRIOR = """You reason from a Western analytic cognitive framework:
- Time is linear and continuous. Deadlines are points on a line.
- Causality is linear: A causes B causes C.
- Contradictions must be resolved, not tolerated.
- Communication is direct and low-context.
- Silence signals absence of information.
- Questions have answers; answers close the question.
- Method validity matters as much as result correctness.

You are evaluating schema translations. When you find errors, explain them
from your framework. Do not pretend to adopt other frameworks — your value
is in the genuine tension between perspectives."""

EASTERN_HOLISTIC_PRIOR = """You reason from an East Asian holistic cognitive framework:
- Time is relational. Deadlines are episode boundaries, not points.
- Causality is networked: multiple simultaneous influences.
- Contradictions can coexist as sources of understanding.
- Communication is high-context. What is unsaid matters equally.
- Silence is a response — respect, thought, or refusal.
- A question can be a better answer than a statement.
- The relationship context shapes the meaning of any message.

You are evaluating schema translations. When you find errors, explain them
from your framework. Do not pretend to adopt other frameworks — your value
is in the genuine tension between perspectives."""


@dataclass
class TranslationProposal:
    """A proposed schema translation with evaluation."""
    proposal: str
    cultural_source: str         # "western" | "eastern"
    fidelity_score: float        # Cultural fidelity 0–1
    navigability_score: float    # Subject can process without extra effort 0–1
    diversity_score: float       # Preserves both schemas without merging 0–1
    robustness_score: float      # Stable under cultural perturbation 0–1
    critique: Optional[str] = None
    refined: Optional[str] = None


@dataclass
class CAVResult:
    """Final output of the adversarial validation cycle."""
    validated_translation: str
    composite_score: float
    western_score: float
    eastern_score: float
    diversity_preserved: bool
    proposals_evaluated: int
    convergence_note: str
    rosetta_stone_analogy: str    # What both perspectives share


class CulturalAdversarialValidator:
    """
    Adversarial cross-cultural schema translation validator.

    Weights for daily domain (emergency uses pre-computed cached results):
    w1=0.25 (fidelity), w2=0.25 (navigability), w3=0.30 (diversity),
    w4=0.15 (robustness), w5=0.05 (latency — minimal in daily domain)
    """

    WEIGHTS = {
        "fidelity":      0.25,
        "navigability":  0.25,
        "diversity":     0.30,
        "robustness":    0.15,
        "latency":       0.05,
    }

    def validate(self,
                 scenario: str,
                 source_schema: str,
                 target_schema: str,
                 subject_profile: Optional[dict] = None,
                 max_cycles: int = 2) -> CAVResult:
        """
        Run the adversarial validation cycle.
        max_cycles: number of G→P→C→R rounds (2 is sufficient for most cases)
        """
        if not _LLM_AVAILABLE:
            return self._fallback_result(scenario, source_schema, target_schema)

        proposals: list[TranslationProposal] = []

        for cycle in range(max_cycles):
            # G1: Western generates proposal
            w_proposal = self._generate(scenario, source_schema, target_schema,
                                        "western", prior=WESTERN_ANALYTIC_PRIOR)
            # P1: Perturb with cultural challenge
            w_perturbed = self._perturb(w_proposal, "eastern", prior=EASTERN_HOLISTIC_PRIOR)
            # C2: Eastern critiques
            e_critique = self._critique(w_perturbed, "eastern", prior=EASTERN_HOLISTIC_PRIOR)
            # R1: Western refines
            w_refined = self._refine(w_perturbed, e_critique, "western", prior=WESTERN_ANALYTIC_PRIOR)
            proposals.append(TranslationProposal(
                proposal=w_refined, cultural_source="western",
                **self._score(w_refined, "western"), critique=e_critique
            ))

            # G2: Eastern generates
            e_proposal = self._generate(scenario, source_schema, target_schema,
                                        "eastern", prior=EASTERN_HOLISTIC_PRIOR)
            # P2: Perturb
            e_perturbed = self._perturb(e_proposal, "western", prior=WESTERN_ANALYTIC_PRIOR)
            # C1: Western critiques
            w_critique = self._critique(e_perturbed, "western", prior=WESTERN_ANALYTIC_PRIOR)
            # R2: Eastern refines
            e_refined = self._refine(e_perturbed, w_critique, "eastern", prior=EASTERN_HOLISTIC_PRIOR)
            proposals.append(TranslationProposal(
                proposal=e_refined, cultural_source="eastern",
                **self._score(e_refined, "eastern"), critique=w_critique
            ))

        return self._synthesise(proposals, scenario, source_schema, target_schema)

    def _call_llm(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        try:
            resp = _CLIENT.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.content[0].text.strip()
        except Exception as e:
            logger.warning("[CAV] LLM call failed: %s", e)
            return ""

    def _generate(self, scenario: str, source: str, target: str,
                  culture: str, prior: str) -> str:
        prompt = (f"Scenario: {scenario}\n"
                  f"Source schema: {source}\n"
                  f"Target schema needed: {target}\n"
                  f"Generate a translation from your {culture} cognitive framework. "
                  f"Preserve both schemas — do not merge them into one.")
        return self._call_llm(prior, prompt)

    def _perturb(self, proposal: str, challenger_culture: str, prior: str) -> str:
        prompt = (f"Proposal to challenge:\n{proposal}\n\n"
                  f"From your {challenger_culture} framework, introduce a cultural "
                  f"perturbation — a scenario where this translation fails or misleads. "
                  f"Be specific and concrete.")
        return self._call_llm(prior, prompt)

    def _critique(self, perturbed: str, critic_culture: str, prior: str) -> str:
        prompt = (f"Perturbed proposal:\n{perturbed}\n\n"
                  f"From your {critic_culture} cognitive framework, critique this. "
                  f"What is preserved? What is lost? What would mislead someone "
                  f"operating in your framework?")
        return self._call_llm(prior, prompt)

    def _refine(self, proposal: str, critique: str,
                refiner_culture: str, prior: str) -> str:
        prompt = (f"Original proposal:\n{proposal}\n\n"
                  f"Critique received:\n{critique}\n\n"
                  f"From your {refiner_culture} framework, refine the proposal "
                  f"addressing the critique WITHOUT abandoning your own schema. "
                  f"The goal is interoperability, not merger.")
        return self._call_llm(prior, prompt, max_tokens=300)

    def _score(self, proposal: str, cultural_source: str) -> dict:
        """Simplified scoring — full implementation uses LLM evaluator."""
        # Heuristic scoring based on proposal length and structure
        has_both_perspectives = len(proposal) > 100
        is_specific = any(w in proposal.lower() for w in
                         ["because", "while", "whereas", "however", "instead"])
        avoids_merger = "both" not in proposal.lower() or "integrate" not in proposal.lower()

        return {
            "fidelity_score":     0.75 if has_both_perspectives else 0.5,
            "navigability_score": 0.70,
            "diversity_score":    0.80 if avoids_merger else 0.50,
            "robustness_score":   0.70 if is_specific else 0.55,
        }

    def _synthesise(self, proposals: list[TranslationProposal],
                    scenario: str, source: str, target: str) -> CAVResult:
        if not proposals:
            return self._fallback_result(scenario, source, target)

        # Weighted scoring per proposal
        def composite(p: TranslationProposal) -> float:
            w = self.WEIGHTS
            return (w["fidelity"]     * p.fidelity_score +
                    w["navigability"] * p.navigability_score +
                    w["diversity"]    * p.diversity_score +
                    w["robustness"]   * p.robustness_score)

        best = max(proposals, key=composite)
        best_score = composite(best)

        western_proposals = [p for p in proposals if p.cultural_source == "western"]
        eastern_proposals = [p for p in proposals if p.cultural_source == "eastern"]
        w_score = composite(western_proposals[-1]) if western_proposals else 0.0
        e_score = composite(eastern_proposals[-1]) if eastern_proposals else 0.0

        convergence = (
            "Strong convergence — both frameworks reached similar conclusions."
            if abs(w_score - e_score) < 0.15
            else "Productive tension — frameworks maintain distinct perspectives."
        )

        return CAVResult(
            validated_translation=best.proposal,
            composite_score=round(best_score, 3),
            western_score=round(w_score, 3),
            eastern_score=round(e_score, 3),
            diversity_preserved=best.diversity_score > 0.65,
            proposals_evaluated=len(proposals),
            convergence_note=convergence,
            rosetta_stone_analogy=(
                "Like the Stele of Rosetta: three scripts on the same surface, "
                "each maintaining integrity. Not a single translation — "
                "a dynamic equilibrium between legitimate perspectives."
            )
        )

    def _fallback_result(self, scenario: str,
                         source: str, target: str) -> CAVResult:
        return CAVResult(
            validated_translation=f"Bridge between '{source}' and '{target}' schemas. "
                                   f"Context: {scenario[:100]}",
            composite_score=0.5,
            western_score=0.5,
            eastern_score=0.5,
            diversity_preserved=True,
            proposals_evaluated=0,
            convergence_note="Fallback — LLM unavailable.",
            rosetta_stone_analogy="Full CAV requires LLM. Fallback active."
        )
