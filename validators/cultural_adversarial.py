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

Intended scoring function (design target, NOT what this file computes):
  Score = w1*FedeltaCulturale + w2*NavigabilitaSoggetto +
          w3*PreservazioneDiversita + w4*Robustezza + w5*CostoLatenza

WHAT IS ACTUALLY IMPLEMENTED
  The adversarial cycle (G→P→C→R, both directions) is real and runs against the
  LLM. The *scoring* is not. `_shape_heuristics` inspects the proposal's length
  and looks for a handful of connective words; it never measures cultural
  fidelity, navigability, diversity preservation or robustness. Its output is
  therefore named `heuristic_score`, is flagged by `score_basis`, and is None
  when no LLM ran. It is not a validation metric and must not be reported as one.

The Rosetta Stone principle:
  The goal is NOT a neutral arbiter (doesn't exist).
  It is the dynamic equilibrium between culturally situated perspectives,
  each maintaining its legitimacy — like the three scripts on the Stele.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("taaa.cav")


class _LLMUnavailable(RuntimeError):
    """The adversarial cycle could not be run. Not a scoring outcome."""


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
    """A proposed schema translation with its (heuristic) shape scores.

    Every *_heuristic field below is a function of the proposal's text shape —
    length and the presence of connective words — not of its cultural content.
    """
    proposal: str
    cultural_source: str            # "western" | "eastern"
    fidelity_heuristic: float       # proxy: proposal length
    navigability_heuristic: float   # constant; no navigability model exists
    diversity_heuristic: float      # proxy: absence of merger vocabulary
    robustness_heuristic: float     # proxy: presence of contrastive connectives
    critique: Optional[str] = None
    refined: Optional[str] = None


@dataclass
class CAVReport:
    """Output of the adversarial cycle.

    Named a report, not a result, and `heuristic_score`, not `composite_score`:
    nothing here is a validation metric. `adversarially_validated` is True only
    when the two-prior LLM cycle actually ran.
    """
    translation: str
    adversarially_validated: bool
    score_basis: str              # "text_shape_heuristic" | "unavailable_no_llm"
    heuristic_score: Optional[float]
    western_heuristic: Optional[float]
    eastern_heuristic: Optional[float]
    diversity_heuristic: Optional[float]
    proposals_evaluated: int
    convergence_note: str
    rosetta_stone_analogy: str    # What both perspectives share
    caveat: str = (
        "heuristic_score measures text shape (length, connectives), not "
        "cultural fidelity. Do not report it as a validation score."
    )


class CulturalAdversarialValidator:
    """
    Adversarial cross-cultural schema translation cycle.

    The cycle (two culturally primed model instances generating, perturbing,
    critiquing and refining each other's proposals) is implemented. The scoring
    is not: WEIGHTS below are applied to the text-shape heuristics in
    _shape_heuristics, which do not measure the quantities they are named after.

    Weights for daily domain (emergency uses pre-computed cached results):
    w1=0.25 (fidelity), w2=0.25 (navigability), w3=0.30 (diversity),
    w4=0.15 (robustness), w5=0.05 (latency — not currently applied)
    """

    WEIGHTS = {
        "fidelity":      0.25,
        "navigability":  0.25,
        "diversity":     0.30,
        "robustness":    0.15,
        "latency":       0.05,
    }

    def run_cycle(self,
                  scenario: str,
                  source_schema: str,
                  target_schema: str,
                  subject_profile: Optional[dict] = None,
                  max_cycles: int = 2) -> CAVReport:
        """
        Run the adversarial cycle. Renamed from validate(): without a working
        LLM nothing is validated, and even with one the scores are heuristics.

        max_cycles: number of G→P→C→R rounds (2 is sufficient for most cases)
        """
        if not _LLM_AVAILABLE:
            return self._unavailable_report(scenario, source_schema, target_schema)

        proposals: list[TranslationProposal] = []

        try:
            self._run_rounds(proposals, scenario, source_schema, target_schema,
                             max_cycles)
        except _LLMUnavailable as e:
            # A constructed client with no valid key looks available at import
            # time and fails at request time. Previously _call_llm swallowed
            # that and returned "", so the cycle "completed" on empty strings
            # and reported adversarially_validated=True with a score of 0.623.
            logger.warning("[CAV] adversarial cycle aborted: %s", e)
            return self._unavailable_report(scenario, source_schema, target_schema,
                                            reason=str(e))

        return self._synthesise(proposals, scenario, source_schema, target_schema)

    def _run_rounds(self, proposals: list, scenario: str, source_schema: str,
                    target_schema: str, max_cycles: int) -> None:
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
                **self._shape_heuristics(w_refined), critique=e_critique
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
                **self._shape_heuristics(e_refined), critique=w_critique
            ))

    def _call_llm(self, system: str, prompt: str, max_tokens: int = 400) -> str:
        """Raise rather than return "" — an empty proposal is not a proposal."""
        try:
            resp = _CLIENT.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.content[0].text.strip()
        except Exception as e:
            raise _LLMUnavailable(str(e)) from e
        if not text:
            raise _LLMUnavailable("model returned an empty response")
        return text

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

    def _shape_heuristics(self, proposal: str) -> dict:
        """Text-shape proxies. NOT cultural measurements.

        Every branch below is a hand-picked constant selected by the author, so
        the reachable range of the weighted combination is 0.5325 – 0.7075 — a
        span of 0.175 that is entirely determined by three string tests. Kept
        because it is the only thing available without an evaluator model, and
        renamed so nobody reads it as a validation score.
        """
        text = proposal.lower()
        is_long = len(proposal) > 100
        is_specific = any(w in text for w in
                          ["because", "while", "whereas", "however", "instead"])
        # False only when the proposal talks about BOTH merging and integrating.
        avoids_merger = not ("both" in text and "integrate" in text)

        return {
            "fidelity_heuristic":     0.75 if is_long else 0.5,
            "navigability_heuristic": 0.70,           # constant: no model
            "diversity_heuristic":    0.80 if avoids_merger else 0.50,
            "robustness_heuristic":   0.70 if is_specific else 0.55,
        }

    def _synthesise(self, proposals: list[TranslationProposal],
                    scenario: str, source: str, target: str) -> CAVReport:
        if not proposals:
            return self._unavailable_report(scenario, source, target)

        # Weighted combination of the shape heuristics above.
        def combined(p: TranslationProposal) -> float:
            w = self.WEIGHTS
            return (w["fidelity"]     * p.fidelity_heuristic +
                    w["navigability"] * p.navigability_heuristic +
                    w["diversity"]    * p.diversity_heuristic +
                    w["robustness"]   * p.robustness_heuristic)

        best = max(proposals, key=combined)
        best_score = combined(best)

        western_proposals = [p for p in proposals if p.cultural_source == "western"]
        eastern_proposals = [p for p in proposals if p.cultural_source == "eastern"]
        w_score = combined(western_proposals[-1]) if western_proposals else None
        e_score = combined(eastern_proposals[-1]) if eastern_proposals else None

        if w_score is not None and e_score is not None:
            convergence = (
                "Both proposals scored within 0.15 on the shape heuristic. This "
                "says nothing about whether the frameworks agree."
                if abs(w_score - e_score) < 0.15
                else "Shape heuristics differ by more than 0.15 between the two "
                     "proposals. Read the two texts; the number is not evidence."
            )
        else:
            convergence = "Only one cultural prior produced a proposal."

        return CAVReport(
            translation=best.proposal,
            adversarially_validated=True,
            score_basis="text_shape_heuristic",
            heuristic_score=round(best_score, 3),
            western_heuristic=round(w_score, 3) if w_score is not None else None,
            eastern_heuristic=round(e_score, 3) if e_score is not None else None,
            diversity_heuristic=best.diversity_heuristic,
            proposals_evaluated=len(proposals),
            convergence_note=convergence,
            rosetta_stone_analogy=(
                "Like the Stele of Rosetta: three scripts on the same surface, "
                "each maintaining integrity. Not a single translation — "
                "a dynamic equilibrium between legitimate perspectives."
            )
        )

    def _unavailable_report(self, scenario: str,
                            source: str, target: str,
                            reason: str = "no anthropic client") -> CAVReport:
        """No LLM: say so. Do not emit 0.5 as if it were a measurement."""
        logger.info("[CAV] no adversarial cycle: %s", reason)
        return CAVReport(
            translation=(f"[template, not a validated translation] Bridge between "
                         f"'{source}' and '{target}' schemas. "
                         f"Context: {scenario[:100]}"),
            adversarially_validated=False,
            score_basis="unavailable_no_llm",
            heuristic_score=None,
            western_heuristic=None,
            eastern_heuristic=None,
            diversity_heuristic=None,
            proposals_evaluated=0,
            convergence_note=(f"No adversarial cycle ran ({reason}). "
                              "Nothing was cross-validated."),
            rosetta_stone_analogy=("The adversarial cycle needs two culturally "
                                   "primed model instances. None were available."),
        )
