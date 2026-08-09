# Errata — TAAA Working Paper Addendum v0.5

The addendum (`TAAA_Working_Paper_Addendum_v0_5.docx`) is a design document. This
file records, section by section, where it and the code diverge, and which of the
two was changed. It supersedes the listed sections of the addendum; the .docx is
left untouched so the author's manuscript is not edited by tooling.

Nothing in the addendum's argument is retracted here. The ignorance/interference
distinction, the David/Tanaka case, the four-layer escalation model, the
minimal/bilateral/non-homologating bridge constraints and the M2 proposal-only
invariant all stand. What is corrected is the description of what the software
does today.

Every claim below was checked by running the code. Legend:
**[CODE FIXED]** — the code was wrong and now matches the addendum.
**[DOC WRONG]** — the addendum describes something that does not exist.

---

## §4 — SARS weights **[CODE FIXED]**

Addendum: `ambiguity .25 · domain .30 · consequence .20 · confidence_mismatch .15 · stress .10`.
Code before: `.25 / .25 / .25 / .15 / .10`.

`FrictionTriggerEngine.WEIGHTS` now matches the addendum, and
`tests/test_reachability.py::test_sars_weights_match_addendum_v0_5` fails if it
drifts again.

## §4 — Escalation threshold **[CODE FIXED]**

Addendum: default 0.55.
Code before: `DEFAULT_THRESHOLD = 0.50`, with a docstring offering 0.62
("balanced") and 0.75 ("conservative") as alternatives.

`DEFAULT_THRESHOLD` is now 0.55. The alternatives were unreachable: measured
through `TAAAAgent`, the SARS maximum was **0.534**, so neither 0.62 nor 0.75
could ever fire. After threading the caller's real domain into the M2 layer, the
reachable range over a 6,720-combination sweep is **0.060 – 0.732**, and the
documented tuning points are now 0.45 / 0.55 / 0.65 — all inside it and all
covered by a test that fails if the ceiling drops back below 0.65.

## §5 — Trigger states **[CODE FIXED]**

Addendum: three states, `INACTIVE / MONITORING / ACTIVE`.
Code before: two.

`TriggerState.MONITORING` now exists, for SARS in `[0.35, 0.55)`. This is not
cosmetic: the two realistic intercultural cases in the test suite — the contract
clause at 0.488 and the "yes plus silence" negotiation at 0.499 — both live in
that band and were previously reported as `INACTIVE`, which is not what the
pipeline was doing with them.

## §7 — "at least 3 distinct events" **[DOC WRONG]**

Addendum §7: a proposal requires "interferenza sullo stesso pattern inter-schema
rilevata in almeno 3 eventi comunicativi distinti con SARS score > soglia".

The code proposes on a **single** event (`TAAAAgent._propose_m2_update`). There is
no cross-event pattern accumulator anywhere in the repository. Treat the 3-event
rule as a design target, not a description.

## §7 — Proposal expiry **[DOC WRONG]**

Addendum §7: proposals have a configurable expiry, "Default: 7 giorni. Dopo la
scadenza, la proposta decade."

Not implemented. Proposals stay `pending_review` indefinitely. What *is*
implemented, and is the load-bearing half of the claim: no proposal ever becomes
operational without `approve_m2_proposal(reviewer=…)`, and
`GatedM2Memory.publish_operational` raises `PermissionError` below C3.

## §5 and §10 — Release tree and new components **[DOC WRONG]**

The addendum's §5 component table and §10 release tree list files that do not
exist in this repository:

| Listed | Status |
|---|---|
| `continuous_translation.py` (`ContinuousTranslationLayer`) | does not exist |
| `bridge.py` (`CognitiveBridgeEngine`) | does not exist |
| `m2_governor.py` (`M2ProposalQueue`) | does not exist as a module; the queue lives in `SubjectProfile.m2_update_queue` and is managed by `TAAAAgent` |
| `orchestrator.py` (`TAAAOrchestrator`) | does not exist; `core/taaa_agent.py` is the orchestrator |
| `xaaa_bridge.py` | does not exist |
| `models.py` (`WisdomTrace`, `BridgeOutput`, `M2Proposal`) | does not exist; the dataclasses live in `friction_trigger.py` |
| `tests/test_continuous_translation.py` | does not exist |
| `tests/test_friction_trigger.py` | does not exist under that name; coverage is in `tests/test_m2_integrated.py` |
| `tests/test_m2_governor.py` | does not exist under that name; coverage is in `tests/test_m2_gated_agent_patch.py` and `tests/test_reachability.py` |
| `examples/run_david_tanaka.py` | exists as `scenarios/negotiation_bilateral.py` |
| `web/TAAA_Continuous_Translation_Demo.html` | does not exist; the live HUD is `api/ar_display.py`, served at `/ar` |
| `maaa_bridge.py` "osservazione silenziosa in dominio emergenziale" | the file exists, but it is a protocol sketch with no MAAA behind it and nothing in the pipeline imports it |

The actual layout is the one in the repository root.

## §1.1 — "Dominio quotidiano … Implementato con ContinuousTranslationLayer operativo" **[DOC WRONG]**

There is no continuous observation layer. The pipeline is invoked per event by
the caller (`TAAAAgent.process`), which is the v0.4 reactive model. The v0.5
continuous-interpreter architecture is designed, not built.

## §3 / §6 — The four-layer escalation and the Rosetta bridge **[DOC WRONG, partially]**

L1 (linguistic) and L2 (pragmatic) do not exist as layers. What exists of L3 is
the SARS score plus `M1.interference_risk`, which does estimate inter-schema
distance over 6 declared dimensions and is used. What exists of L4 is the
proposal queue described above. The bilateral, minimal, non-homologating bridge
of §6 — including the homologation metric that regenerates an asymmetric bridge —
is not implemented; the M1/M2 interventions emit one fixed sentence each without
an LLM.

## Also corrected outside the addendum

The README's Working Paper badge pointed at `docs/TAAA_Working_Paper_v04.pdf`,
which does not exist. The working paper in this repository is
`TAAA_Working_Paper_v04.docx` at the root. The badge has been removed rather than
repointed.
