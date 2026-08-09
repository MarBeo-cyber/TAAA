[![AURA Framework](https://img.shields.io/badge/AURA-Level%206%20%7C%20TAAA-1F3864)](https://github.com/MarBeo-cyber/AURA)

# 🌐 TAAA — Translational Autopoietic Adaptive Agent

> **Schema memory and inter-schema translation for human-machine cognitive systems.**
> Fifth agent in the WAAA→MAAA→PAAA→SAAA→TAAA autopoietic ontology.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Family](https://img.shields.io/badge/Family-WAAA%20%E2%86%92%20TAAA-purple)](https://github.com/MarBeo-cyber/waaa)

---

## Status

**Research prototype.** The architecture is the contribution; the implementation
is a reference skeleton for it. This section says exactly which is which, so that
nothing below has to be taken on trust.

| Component | State |
|---|---|
| Gap detection (ignorance / interference / partial / none) | **Heuristic.** With an API key: an LLM judgement. Without one: a keyword classifier over the scenario text and the caller's action label. It reports a `rule_id`, never a confidence number. |
| M0 archetypes | **Static table.** 8 hand-written `ImageSchema` literals with a primitive index. No retrieval, no similarity. |
| M1 cultural/professional priors | **Static table.** 7 hand-written profiles. `M1.interference_risk` is a real computation over 6 declared dimensions. `build_prior` resolves categorical dimensions by source weight and records which source supplied each one. |
| M2 personal topology | **Proposal ledger, not learned memory.** Observations queue reviewable proposals; only `approve_m2_proposal()` writes to `m2_topology`. Nothing is learned automatically — that is the design, not a limitation. |
| SARS friction trigger | **Real arithmetic** over signals computed by `SignalExtractor` from text and (optional) behavioural inputs. Weights and thresholds match Addendum v0.5 §4. |
| Timing controller | **Real formula.** HRV/GSR fusion and an EMA over a per-subject regression curve. The curves themselves are hand-set defaults, not calibrated on anyone. |
| Bilateral consent | **Implemented and enforced.** SHA-256 invite token, per-party revoke, 4h expiry checked on every read; `OutwardPerceptionLayer.observe` is genuinely gated on it. |
| Outward perception | **Simulated.** Replays one of three scripted signal sets, chosen by the caller. No computer vision. |
| Cultural Adversarial Validator | **Cycle real, scoring not.** The G→P→C→R rounds run against the LLM. The scores are text-shape heuristics and are named `*_heuristic`. With no working LLM the endpoint says so and returns `null`, not a number. |
| AR display (`/ar`) | **Live.** Server-Sent Events driven by `TAAAAgent.process`. The repo-root `TAAA_AR_Display_8_1.html` is a **non-functional design mock-up** — a storyboard of typed constants. |
| `core/maaa_bridge.py` | **Unimplemented protocol sketch.** Message shapes and constraint checks only. No MAAA process exists here and the pipeline does not import it. |

Not implemented, despite appearing in Addendum v0.5 §5 and §10:
`ContinuousTranslationLayer`, `CognitiveBridgeEngine`, `M2ProposalQueue` as a
separate module, `TAAAOrchestrator`, `xaaa_bridge`, and the "at least 3 distinct
events" rule for M2 proposals (the code proposes on a single event). See
[docs/ADDENDUM_v0_5_ERRATA.md](docs/ADDENDUM_v0_5_ERRATA.md).

No API key is required for anything in this README. Every LLM path falls back to
a rule-based branch, and CI runs with no key set.

---

## What is the TAAA?

The TAAA translates between **cognitive schemas** — not between languages. It addresses the gap between how different individuals *organise and interpret reality*, shaped by culture, profession, age, experiences, traumas, and context.

**The key distinction no existing system makes:**

| Condition | Description | Intervention |
|-----------|-------------|-------------|
| **Ignorance** | Schema absent — person doesn't know | Add information |
| **Interference** | Schema present but WRONG — person believes they know | Suppress first, then redirect |

The American in Shinjuku station during a fire doesn't think *"I don't know where the exit is."* He thinks *"I know where the exit is"* — and turns the wrong way with complete confidence. That is interference. It requires **suppression before correction**, not information addition.

This distinction is not decorative. It is carried all the way down into the code
and it is tested: `tests/test_reachability.py` fails if either half of it becomes
unproducible. That test exists because both halves once were — `RiskClass.IGNORANCE`
required a `user_confidence` of 0.35 or below while the extractor's floor was
0.415, so for a long time the framework could not report ignorance at all.

---

## Schema Memory

The TAAA proposes **Schema Memory** (M0/M1/M2) as a memory category distinct from
the ones current AI systems keep. Conversational memory records *what was said*;
retrieval memory records *what is true*. Neither records:

> *Which cognitive structures does this person use, in which contexts, with what degree of automatism?*

That question is the contribution. What follows is the argument for the category,
followed by an honest account of what this repository implements of it.

| Level | Content | Origin | Use |
|-------|---------|--------|-----|
| **M0** | Universal pre-cultural archetypes | Biological (pre-loaded) | Emergency floor — never learned |
| **M1** | Cultural/professional priors | Cross-cultural research | Bayesian prior at bootstrap |
| **M2** | Personal schema topology | Reviewed proposals from observation | Non-emergency domains only |

**What is implemented.** M0 is a table of 8 `ImageSchema` literals in
`schema_memory/m0_archetypes.py` with an index from primitive to schema. M1 is a
table of 7 `CulturalSchemaProfile` literals in `schema_memory/m1_priors.py`,
plus two real computations over them: `interference_risk` (a count of conflicting
dimensions out of 6) and `build_prior` (per-dimension resolution between the
cultural and professional profiles, recording agreement, contest and source).
M2 is a per-subject dict that starts empty and is written only by
`approve_m2_proposal()`.

**What is not implemented.** There is no retrieval, no similarity search, no
embedding, and no learned topology. M0 and M1 are hand-written knowledge, not
induced knowledge. Calling this a working schema memory would be a category
error: it is a *scaffold* for one, with the gating and provenance machinery built
first, deliberately — see the next section.

### M2 is proposal-only, on purpose

The most dangerous function in a system like this is silent self-modification of
its model of a person. So M2 cannot be written by observation:

```
observation → SARS score → risk class → proposal queued (status=pending_review)
                                      → m2_topology UNCHANGED
                                      → approve_m2_proposal(reviewer=…) → m2_topology
```

`SafetyGovernor.operational_update_allowed()` returns `False` for every
operational event, unconditionally. `GatedM2Memory.publish_operational()` raises
`PermissionError` below confidence level C3. Scenario 4 of the demo prints the
whole gate, before and after review.

### M0: biological grounding

M0 is grounded in cross-species empirical evidence:

- **Visual cliff** (Gibson & Walk 1960): 6-8 month infants stop at drop edge. Replicated with kittens, chicks, lambs, rats. **Pre-cultural, cross-species.**
- **Neonatal reflexes**: Moro, grasping, suckling — present at birth, before any learning
- **Looming response**: 2-week-old infants avoid expanding objects

Formalised using **DISL primitives** (Hedblom et al. 2024) in **DSR** (Olivier &
Bouraoui 2025). One primitive, `BOUNDARY`, is a TAAA extension and is marked as
such in the enum — it is not from DISL Table 1.

---

## Architecture

```
TAAA Pipeline (one cycle):
  1. Build subject context (M0 + M1 prior + M2 if available)
  2. Gap Detection → ignorance / interference / partial / none
  3. Interference Prediction → schema strength, timing window
  4. Timing Controller → position on individual regression curve  (per subject)
  5. Intervention Engine → strategy selection + output generation
  6. M2 friction trigger → queue a reviewable proposal (never a write)
```

### Timing Controller

The threshold between System 2 (cultural) and M0 is **not a switch — it is a cursor**. Each person has an individual regression curve. PAAA would provide real-time biometric position estimation (HRV, GSR); the fusion formula is implemented, the biometrics are supplied by the caller.

Under acute stress, M0 becomes **more** accessible, not less. The person in panic is cognitively closer to the 7-month-old at the visual cliff than to their cultural self.

Each `SubjectProfile` owns its own `TimingController`. Both the curve and the
stress-smoothing history are individual; sharing one controller across subjects
mixed one person's stress into another's M-level.

### Intervention Strategies

| Strategy | When | Mechanism |
|----------|------|-----------|
| **Calibrated Interruption** | Interference + M0 | Pre-verbal haptic stop → AR redirect. No negation. |
| **AR Substitution** | Ignorance + M0 | Replace unreadable environment elements with M0 icons |
| **Procedural Bypass** | M0 extreme | Motor-level instructions only: "Three steps. Left. Door." |
| **Cultural Bridge** | M1 | LLM cultural adaptation, with a fixed rule-based fallback |
| **Deep Translation** | M2 | LLM bidirectional translation, with a fixed rule-based fallback |

Without an API key the M1 and M2 strategies emit one fixed Italian sentence each.
They are placeholders for the translation, not the translation.

### SARS — the M2 friction trigger

```
SARS = 0.25·ambiguity + 0.30·domain_distance + 0.20·consequence
     + 0.15·confidence_mismatch + 0.10·stress
```

Weights and the 0.55 escalation threshold follow Addendum v0.5 §4. Trigger states
are `inactive` / `monitoring` / `ACTIVE`.

Measured over a 6,720-combination sweep through `TAAAAgent`
(`tests/test_reachability.py`), the reachable SARS range is **0.060 – 0.732**, and
all five `RiskClass` values and all three trigger states occur. Tuning points,
all inside that range: 0.45 sensitive, **0.55 default**, 0.65 conservative. The
test fails if the reachable maximum ever falls below 0.65 again — it used to be
0.534, against a documented "balanced" threshold of 0.62.

---

## Quick Start

```bash
git clone https://github.com/MarBeo-cyber/taaa.git
cd taaa
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"      # pytest, pyflakes

python main_taaa.py demo     # four demo scenarios
python -m pytest -q          # 48 tests, no API key needed
python main_taaa.py server   # → http://localhost:5004
```

### Demo scenarios — actual output

`python main_taaa.py demo`, no API key. These are transcripts, not intentions.
The `latency_ms` figures vary between runs; everything else is stable.

**Scenario 1 — Shinjuku Emergency (M0)**
Mark (US) in a Tokyo station fire. Active wrong spatial schema.

```
── Tick 001 | 5.0ms | EMERGENCY
  Gap:    ⚠ INTERFERENCE (rules: rule=interference_automaticity_and_stated_mismatch)
  Interf: strength=0.75 window=350ms
  M-level: M0 (stress=0.92)
  Action: ⛔ Interrupt calibrated_interruption
  Voice:  "Fermati. Segui la freccia verde."
  Haptic: sharp_stop
  AR:     STOP_THEN_ARROW_CORRECT_DIRECTION
```

**Scenario 2 — David / Tanaka Negotiation**
`'yes'` + silence: agreement (US schema) vs acknowledgement + respectful space (JP schema).

```
  [M1 Interference Risk Analysis]
  Risk level: HIGH (score=0.83)
  Conflict dimensions: temporal_schema_mismatch, reasoning_style_mismatch,
                       context_level_mismatch, silence_interpretation_conflict,
                       communication_style_conflict

── Tick 002 | 1.8ms | NEGOTIATION       (David)
  Gap:    ⚠ INTERFERENCE (rules: rule=interference_automaticity_and_stated_mismatch)
  M-level: M2 (stress=0.15)
  Action: 🔄 Translate deep_translation

── Tick 003 | 0.7ms | NEGOTIATION       (Tanaka-san)
  Gap:    ○ NONE (rules: rule=none_no_signal)
  M-level: M2 (stress=0.35)
  Action: — none
```

The asymmetry is honest output, not a bug being hidden. David's scenario text
states the divergence outright ("In US business culture … In Japanese culture …");
Tanaka's does not, and the keyword classifier requires the situation to state a
mismatch before it will call interference. Both sides are detected only on the
LLM path. The M1 risk score of 0.83 is bidirectional and is computed, not typed.

**Scenario 3 — Medical Consultation**
Lin Mei (TCM framework) / Dr. Chen (biomedical framework) — incompatible body ontologies.

```
── Tick 004 | 1.3ms | MEDICAL
  Gap:    ? IGNORANCE (rules: rule=ignorance_uncertainty_markers)
  M-level: M2 (stress=0.20)
  Action: 🔄 Translate deep_translation
```

`IGNORANCE`, not `PARTIAL`. The scenario says the doctor "doesn't have access to
this mapping" and Lin Mei "cannot answer in this frame" — uncertainty markers with
no automaticity marker beside them. Earlier versions of this README advertised
`PARTIAL → deep_translation` here; the code printed `Gap=NONE, Strategy=none`.

**Scenario 4 — Contract Clause (gated M2 proposal queue)**

```
── Tick 005 | 0.7ms | CONTRACT
  Gap:    ○ NONE (rules: rule=none_no_signal)
  M-level: M1 (stress=0.35)

  [M2 Friction Trigger — scores computed by SignalExtractor]
  SARS:             0.5638  (threshold 0.55)
  Trigger state:    active
  Risk class:       high_consequence_schema_gap
  Recommendation:   request_human_expert_review
  Operational update allowed: False

  [Gate — before review]
  Pending proposals: 1
  m2_topology:       {}   ← untouched

  [Gate — after explicit human review]
  Reviewer:          marco
  Confidence level:  C3_domain_validated
  m2_topology keys:  ['validated_0']
```

The gap detector says `none` while the M2 layer scores 0.5638 and asks for expert
review. That is the two layers disagreeing, and it is worth reading as a result:
nothing in the phrasing looks like a schema gap, and the risk is entirely in the
word "reasonable" sitting in a contract.

Session summary for the whole run:

```
  total_cycles: 5
  gap_distribution: {'interference': 2, 'none': 2, 'ignorance': 1}
  m2_proposals: 1
  m2_events: 1
  pending_m2_reviews: 1
  mean_latency_ms: 1.9      # varies
  subjects: 5
```

### REST API

```bash
# Agent status + the SARS configuration actually in force
curl http://localhost:5004/status

# M0 visual cliff (paradigm case — biological grounding)
curl http://localhost:5004/m0/visual_cliff

# Register a subject
curl -X POST http://localhost:5004/subject/register \
  -H "Content-Type: application/json" \
  -d '{"subject_id": "mark", "culture": "western_northern_european",
       "profession": "manager", "regression_curve": "default_civilian"}'

# Run one pipeline cycle
curl -X POST http://localhost:5004/process \
  -H "Content-Type: application/json" \
  -d '{"subject_id": "mark",
       "scenario": "Mark is about to turn right because in American stations the exit is opposite to the main flow, but in this station the emergency exit is to the left. He is walking confidently toward the wrong exit.",
       "domain": "emergency", "current_action": "turns toward the right corridor",
       "environment_context": "east_asian", "stress_estimate": 0.85}'

# M1 interference risk between two cultural profiles
curl "http://localhost:5004/m1/interference_risk?subject=western_northern_european&environment=east_asian"

# Cultural Adversarial cycle (read the `caveat` field)
curl -X POST http://localhost:5004/cav/run \
  -H "Content-Type: application/json" \
  -d '{"scenario": "negotiation silence", "source_schema": "silence_as_absence",
       "target_schema": "silence_as_respect"}'
```

`domain` is free-form. `"emergency"` forces the M0 path and suppresses M2
proposals; anything else (`"daily"`, `"medical"`, `"contract"`, `"negotiation"`, …)
is passed through to `SignalExtractor` and `SafetyGovernor` verbatim, and it
matters: `"medical"` carries a consequence weight of 0.95 and triggers
`request_human_expert_review`, `"daily"` carries the 0.40 default.

Without an API key, `/process` returns `gap.llm_confidence: null` and a
`gap.rule_id` naming the rule that fired, with the matched substrings in
`gap.evidence`. There is no confidence number on the rules path because there is
no calibration data behind one.

`/process` also returns an `m2` block for every non-emergency cycle — `sars`,
`trigger_state`, `risk_class`, `recommendation`, `operational_update_allowed` —
whether or not a proposal was queued. The SARS score is computed either way, and
suppressing it below threshold is what made `m2_proposals: 0` uninterpretable.

`/cav/run` with no working LLM returns `heuristic_score: null`,
`adversarially_validated: false` and `score_basis: "unavailable_no_llm"`.

### AR display

```bash
python main_taaa.py server
# open http://localhost:5004/ar
```

The HUD subscribes to `GET /ar/stream` (Server-Sent Events) and renders whatever
`TAAAAgent.process` emits — including `gap: none`. The buttons `POST` to
`/ar/scenario/<name>`, which runs the real scenario functions.

`TAAA_AR_Display_8_1.html` in the repository root is a **non-functional design
mock-up**: a `setTimeout` storyboard whose displayed values are typed constants.
Keep it for the visual design; do not read numbers off it.

---

## The Autopoietic Ontology

| Agent | Function | Biological Analogy |
|-------|----------|--------------------|
| WAAA | Perceptual self-monitoring | Sensory reflex |
| MAAA | Emergency cognitive stabilisation | Amygdala / HPA axis |
| PAAA | Longitudinal neurofunctional monitoring | Immune / homeostasis |
| SAAA | Knowledge consolidation | Synaptic plasticity |
| **TAAA** | **Inter-schema translation** | **Hippocampus — schema indexer** |

→ [WAAA Repository](https://github.com/MarBeo-cyber/waaa)

The MAAA and PAAA integrations are protocol sketches in this repository, not live
connections. `core/maaa_bridge.py` defines message shapes and validates the MAAA
9-word emergency constraint; nothing else.

---

## Contributing

Priority areas, in rough order of how much they would change the honesty of the
Status table above:

- [ ] Replace keyword gap detection with something evaluated against labelled cases
- [ ] Calibrate at least one regression curve against real stress-test data
- [ ] Give M0/M1 actual retrieval (similarity over primitives, not `dict.get`)
- [ ] Compute the CAV sub-scores instead of proxying text shape
- [ ] Implement the addendum's "3 distinct events" rule for M2 proposals
- [ ] Full DISL primitive formalisation in NetworkX + Clingo
- [ ] PAAA biometric integration (HRV real-time stream)
- [ ] Cultural Adversarial Validator: multi-cultural LLM pairs beyond West/East
- [ ] AR rendering layer (Unity XR / WebXR)

---

## References

- Hedblom et al. (2024). The Diagrammatic Image Schema Language (DISL).
- Olivier & Bouraoui (2025). Grounding Agent Reasoning in Image Schemas. AAMAS 2025.
- Gibson & Walk (1960). The visual cliff. *Scientific American.*
- Nisbett (2003). *The Geography of Thought.*
- Hall (1976). *Beyond Culture.*
- Kahneman (2011). *Thinking, Fast and Slow.*
- Beozzi (2026). TAAA Working Paper v0.4 (`TAAA_Working_Paper_v04.docx`) and
  Addendum v0.5 (`docs/TAAA_Working_Paper_Addendum_v0_5.docx`), with
  [errata](docs/ADDENDUM_v0_5_ERRATA.md).

---

## License

MIT — see [LICENSE](LICENSE).

*Marco G. Beozzi — Developed in collaboration with Claude (Anthropic)*
