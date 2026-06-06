[![AURA Framework](https://img.shields.io/badge/AURA-Level%206%20%7C%20TAAA-1F3864)](https://github.com/MarBeo-cyber/AURA)

# 🌐 TAAA — Translational Autopoietic Adaptive Agent

> **Schema memory and inter-schema translation for human-machine cognitive systems.**
> Fifth agent in the WAAA→MAAA→PAAA→SAAA→TAAA autopoietic ontology.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Working Paper](https://img.shields.io/badge/Working%20Paper-v0.4-orange)](docs/TAAA_Working_Paper_v04.pdf)
[![Family](https://img.shields.io/badge/Family-WAAA%20%E2%86%92%20TAAA-purple)](https://github.com/MarBeo-cyber/waaa)

---

## What is the TAAA?

The TAAA translates between **cognitive schemas** — not between languages. It addresses the gap between how different individuals *organise and interpret reality*, shaped by culture, profession, age, experiences, traumas, and context.

**The key distinction no existing system makes:**

| Condition | Description | Intervention |
|-----------|-------------|-------------|
| **Ignorance** | Schema absent — person doesn't know | Add information |
| **Interference** | Schema present but WRONG — person believes they know | Suppress first, then redirect |

The American in Shinjuku station during a fire doesn't think *"I don't know where the exit is."* He thinks *"I know where the exit is"* — and turns the wrong way with complete confidence. That is interference. It requires **suppression before correction**, not information addition.

---

## Schema Memory — A New Category

The TAAA introduces **Schema Memory** (M0/M1/M2), a type of memory that does not exist in current AI systems:

> *Which cognitive structures does this person use, in which contexts, with what degree of automatism?*

| Level | Content | Origin | Use |
|-------|---------|--------|-----|
| **M0** | Universal pre-cultural archetypes | Biological (pre-loaded) | Emergency floor — never learned |
| **M1** | Cultural/professional priors | Cross-cultural research | Bayesian prior at bootstrap |
| **M2** | Personal schema topology | Interaction archaeology | Daily domain only |

### M0: Biological Grounding

M0 is grounded in cross-species empirical evidence:

- **Visual cliff** (Gibson & Walk 1960): 6-8 month infants stop at drop edge. Replicated with kittens, chicks, lambs, rats. **Pre-cultural, cross-species.**
- **Neonatal reflexes**: Moro, grasping, suckling — present at birth, before any learning
- **Looming response**: 2-week-old infants avoid expanding objects

Formalised using **DISL primitives** (Hedblom et al. 2024) in **DSR** (Olivier & Bouraoui 2025).

---

## Architecture

```
TAAA Pipeline (one cycle):
  1. Build subject context (M0 + M1 prior + M2 if available)
  2. Gap Detection → ignorance / interference / partial / none
  3. Interference Prediction → schema strength, timing window
  4. Timing Controller → position on individual regression curve
  5. Intervention Engine → strategy selection + output generation
  6. Interaction Archaeology → M2 update (daily domain only)
```

### Timing Controller

The threshold between System 2 (cultural) and M0 is **not a switch — it is a cursor**. Each person has an individual regression curve calibrated in setup. PAAA provides real-time biometric position estimation (HRV, GSR).

Under acute stress, M0 becomes **more** accessible, not less. The person in panic is cognitively closer to the 7-month-old at the visual cliff than to their cultural self.

### Three Intervention Strategies

| Strategy | When | Mechanism |
|----------|------|-----------|
| **Calibrated Interruption** | Interference + M0 | Pre-verbal haptic stop → AR redirect. No negation. |
| **AR Substitution** | Ignorance + M0 | Replace unreadable environment elements with M0 icons |
| **Procedural Bypass** | M0 extreme | Motor-level instructions only: "Three steps. Left. Door." |
| **Cultural Bridge** | M1 | LLM-powered cultural schema adaptation |
| **Deep Translation** | M2 | Bidirectional personal schema translation |

---

## Quick Start

```bash
git clone https://github.com/MarBeo-cyber/taaa.git
cd taaa
pip install -r requirements.txt

# Run the three demo scenarios
python main_taaa.py demo

# REST API server
python main_taaa.py server
# → http://localhost:5004
```

### Demo Scenarios

```
Scenario 1 — Shinjuku Emergency (M0)
  Mark (US) in Tokyo station fire. Active wrong spatial schema.
  Expected: INTERFERENCE → calibrated_interruption → M0 → "Fermati. Segui la freccia."

Scenario 2 — David/Tanaka Negotiation (M1)
  'Yes' + silence: agreement (US schema) vs acknowledgement + respectful space (JP schema)
  Expected: HIGH interference risk (5 dimensions) → cultural_bridge → M1

Scenario 3 — Medical Consultation (M1/M2)
  Lin Mei (TCM framework) / biomedical doctor — incompatible body ontologies
  Expected: PARTIAL gap → deep_translation
```

### REST API

```bash
# M0 visual cliff (paradigm case — biological grounding)
curl http://localhost:5004/m0/visual_cliff

# M0 Shinjuku case
curl http://localhost:5004/m0/shinjuku

# Register a subject
curl -X POST http://localhost:5004/subject/register \
  -H "Content-Type: application/json" \
  -d '{"subject_id": "mark", "culture": "western_northern_european",
       "profession": "manager", "regression_curve": "default_civilian"}'

# Run pipeline cycle
curl -X POST http://localhost:5004/process \
  -H "Content-Type: application/json" \
  -d '{"subject_id": "mark", "scenario": "...", "domain": "emergency",
       "current_action": "turns toward wrong exit",
       "environment_context": "east_asian", "stress_estimate": 0.85}'

# M1 interference risk between two cultural profiles
curl "http://localhost:5004/m1/interference_risk?subject=western_northern_european&environment=east_asian"

# Cultural Adversarial Validator
curl -X POST http://localhost:5004/cav/validate \
  -H "Content-Type: application/json" \
  -d '{"scenario": "negotiation silence", "source_schema": "silence_as_absence",
       "target_schema": "silence_as_respect"}'
```

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

---

## Contributing

Priority areas:
- [ ] Full DISL primitive formalisation in NetworkX + Clingo
- [ ] M2 schema topology from longitudinal interaction data
- [ ] PAAA biometric integration (HRV real-time stream)
- [ ] Setup Phase 2: stress test calibration protocol
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
- Beozzi (2026). TAAA Working Paper v0.4.

---

## License

MIT — see [LICENSE](LICENSE).

*Marco G. Beozzi — Developed in collaboration with Claude (Anthropic)*
