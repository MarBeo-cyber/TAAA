"""
TAAA — Scenario 2 Updated: David / Tanaka-san
Bilateral Consent Model + Pre-Calibrated Signal + Debrief

Architecture changes from v0.3:
  - Both parties activate TAAA as cognitive translator (bilateral consent)
  - Outward perception monitors Tanaka-san's non-verbal signals
  - Trigger: pre-speech signals from David + active processing from Tanaka-san
  - In-moment intervention: ONLY pre-calibrated haptic signal (no text)
  - Debrief: full explanation delivered after natural pause

WHAT IS SIMULATED HERE
  OutwardPerceptionLayer runs in simulation_mode and replays a hand-written
  signal set; this script asks for the "processing" phase explicitly. MAABridge
  is a protocol sketch with no MAAA behind it (see core/maaa_bridge.py). What is
  real: the bilateral consent state machine in core/bilateral_consent.py, which
  genuinely gates the observation, and the MAAA 9-word constraint check.
"""

from __future__ import annotations

import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.bilateral_consent import CONSENT_MANAGER
from core.maaa_bridge import MAABridge
from components.outward_perception import OutwardPerceptionLayer
from schema_memory.m1_priors import M1
from core.taaa_agent import TAAAAgent


DIVIDER = "═" * 70


def run_bilateral_negotiation():
    """
    David (US) / Tanaka-san (JP) — bilateral TAAA session.

    Phase 1: Both parties activate the cognitive translator (consent)
    Phase 2: David makes a proposal, Tanaka-san responds "yes" + silence
    Phase 3: Outward perception reads Tanaka-san's processing signals
    Phase 4: Pre-calibrated haptic to David — "wait, active processing"
    Phase 5: David waits. Tanaka-san delivers indirect response.
    Phase 6: Natural pause — debrief card appears for David
    """

    print(f"\n{DIVIDER}")
    print("  SCENARIO 2 — David / Tanaka-san (Bilateral TAAA Session)")
    print("  Cognitive Translator Model — v0.4 Updated")
    print(f"{DIVIDER}\n")

    agent = TAAAAgent(simulation_mode=True, verbose=False)
    bridge = MAABridge(simulation_mode=True)
    outward = OutwardPerceptionLayer(simulation_mode=True)

    # ── Phase 1: Bilateral consent ────────────────────────────────────────────
    print("  FASE 1 — Attivazione traduttore cognitivo")
    print("  (Entrambe le parti attivano lo strumento consapevolmente)\n")

    # David initiates
    session = CONSENT_MANAGER.create_session(
        initiator_subject_id="david_us_executive",
        initiator_device_id="device_david_glasses",
        session_type="negotiation",
    )
    print(f"  David:      Traduttore cognitivo attivato [token: {session.invite_token}]")
    print("  → Condivide token con Tanaka-san\n")

    # Tanaka-san joins
    session = CONSENT_MANAGER.join_session(
        invite_token=session.invite_token,
        joiner_subject_id="tanaka_osaka",
        joiner_device_id="device_tanaka_glasses",
    )
    print("  Tanaka-san: Traduttore cognitivo accettato ✓")

    display = session.to_display()
    print("\n  Stato sessione:")
    print(f"    Livello consenso:       {display['consent_level'].upper()}")
    print(f"    Monitoring outward:     {'ATTIVO' if display['outward_active'] else 'INATTIVO'}")
    print(f"    Tipo:                   {display['session_type']}")
    print(f"    Nota:                   {display['interpreter_note']}")

    # Register subjects
    agent.register_subject("david_us_executive",
                           culture="western_northern_european", profession="manager", age=48)
    agent.register_subject("tanaka_osaka",
                           culture="east_asian", profession="manager", age=55)

    # M1 interference risk
    risk = M1.interference_risk("western_northern_european", "east_asian")
    print(f"\n  [M1] Rischio interferenza: {risk['risk'].upper()} "
          f"({risk['score']}) — {len(risk['conflict_dimensions'])} dimensioni conflitto")

    # ── Phase 2: The negotiation moment ───────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  FASE 2 — La proposta e il silenzio")
    print(f"{DIVIDER}\n")

    print("  David:      «Vorrei proporre una clausola di esclusiva 18 mesi.»")
    time.sleep(0.5)
    print("  Tanaka-san: «Yes.»")
    time.sleep(0.5)
    print("  Tanaka-san: [silenzio]")
    print()

    # ── Phase 3: Outward perception ───────────────────────────────────────────
    print("  [Outward Perception — lettura segnali non verbali di Tanaka-san]")

    # Check consent
    permitted, reason = CONSENT_MANAGER.check_outward_permitted("david_us_executive")
    print(f"  Outward monitoring: {'AUTORIZZATO — consenso bilaterale' if permitted else 'NEGATO: ' + reason}")

    obs = None
    if permitted:
        # sim_phase is explicit. The simulator used to pick a phase from
        # `time.time() % 10`, so this script narrated "elaborazione attiva"
        # while the layer was actually returning state=listening.
        obs = outward.observe(
            observer_subject_id="david_us_executive",
            interlocutor_profile={"culture": "east_asian", "subject_id": "tanaka_osaka"},
            scenario_context="after_yes_silence",
            sim_phase="processing",
        )
        sig = obs.signals
        print("  [SIMULAZIONE — segnali generati da uno script, non misurati]")
        print("\n  Segnali rilevati:")
        print(f"    Stato:              {sig.state.value}")
        print(f"    Sguardo:            {sig.gaze_direction}")
        print(f"    Pre-speech breath:  {'SÌ' if sig.pre_speech_breath else 'NO'}")
        print(f"    Silenzio attivo:    {'SÌ' if sig.silence_active else 'NO'}")
        print(f"    Micro-espressione:  {sig.micro_expression or '—'}")
        print(f"    Durata silenzio:    {sig.silence_duration_ms:.0f}ms (individuale, non timer)")
        # Derived from the property, not asserted alongside it.
        print(f"    Elaborazione attiva: {'SÌ — silenzio vivo, non vuoto' if sig.is_processing_active else 'NO'}")
        print(f"\n  Raccomandazione trigger: {obs.trigger_recommendation}")
        print("  [Il sistema NON misura la durata — legge i segnali]")

    # ── Phase 4: Pre-calibrated signal to David ───────────────────────────────
    print(f"\n{DIVIDER}")
    print("  FASE 3 — Intervento pre-calibrato (in-momento)")
    print(f"{DIVIDER}\n")

    if obs is None or obs.trigger_recommendation != "wait":
        state = obs.signals.state.value if obs else "non osservato"
        print(f"  Nessun intervento: la raccomandazione non è 'wait' "
              f"(stato interlocutore: {state}).")
        print("  Il TAAA resta silenzioso. Fine dello scenario.")
        CONSENT_MANAGER.end_session(session.session_id)
        return

    # Detect: David shows pre-speech signals (about to fill the silence)
    print("  [MAAA L3 — stato derivato dallo scenario, non da sensori]")
    maaa_state = bridge.get_human_state(scenario_stress=0.15)
    print(f"  Stato David:     {maaa_state.cognitive_state} | "
          f"receptivity={maaa_state.receptivity}")
    print("  David sta per:   INTERROMPERE il silenzio (assunzione dello scenario)")
    print()

    # Build pre-calibrated signal — NO text in real-time
    signal = bridge.build_pre_calibrated_signal("cultural_pause", m_level="M1")
    accepted = bridge.inject_to_maaa(signal)

    print("  Intervento TAAA → MAAA:")
    print("    Tipo:           segnale pre-calibrato (addestrato in setup)")
    print(f"    Aptico:         {signal.haptic_pattern}")
    print(f"    AR:             {signal.ar_overlay}")
    print(f"    Voce:           {'nessuna — NO testo in real-time' if not signal.voice_message else signal.voice_message}")
    print(f"    Urgenza:        {signal.urgency}")
    print(f"    Accettato dai filtri MAAA: {accepted}")
    if accepted:
        print("\n  David sente il buzz — sa (dal training) che significa: ASPETTA")
        print("  Non legge nulla. Non viene distratto. Non viene interrotto.")
    else:
        print("\n  Segnale rifiutato dai filtri MAAA — nessun buzz consegnato.")

    # ── Phase 5: David waits ──────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  FASE 4 — David aspetta. Tanaka-san risponde.")
    print(f"{DIVIDER}\n")

    time.sleep(0.3)
    print("  David:      [aspetta — rispetta il silenzio]")
    time.sleep(0.5)
    print("  Tanaka-san: «È un'idea interessante... Abbiamo alcune considerazioni")
    print("               interne da approfondire prima di procedere.»")
    print()
    print("  [Risposta indiretta — nel suo schema: proposta non accettata,")
    print("   ma formulata con rispetto della relazione]")

    # ── Phase 6: Debrief after natural pause ──────────────────────────────────
    print(f"\n{DIVIDER}")
    print("  FASE 5 — Debrief (pausa naturale, post-momento)")
    print(f"{DIVIDER}\n")

    debrief = bridge.build_debrief(
        schema_explanation=(
            "Il 'yes' di Tanaka-san = 'ho compreso la proposta'. "
            "Il silenzio = elaborazione rispettosa, non assenza. "
            "La sua risposta = rifiuto indiretto cortese. "
            "Schema: high-context, silence_as_respect."
        )
    )
    bridge.inject_to_maaa(debrief)

    print("  [Scheda debrief appare sugli occhiali di David — pausa naturale]")
    print("\n  ┌─────────────────────────────────────────────────────┐")
    print("  │  SCHEMA GAP — M1 Cultural Bridge                    │")
    print("  │                                                      │")
    print("  │  'Yes' di Tanaka-san = ho compreso la proposta      │")
    print("  │  Silenzio = elaborazione rispettosa, non assenza     │")
    print("  │  Risposta = rifiuto indiretto cortese                │")
    print("  │                                                      │")
    print("  │  silence_as_absence → silence_as_respect             │")
    print("  └─────────────────────────────────────────────────────┘")

    print("\n  Sessione TAAA:")
    print(f"    Iniezioni MAAA:    {bridge.injection_count}")
    print("    Monitoring:        bilaterale consensuale")
    print("    Testo in real-time: NESSUNO")
    print("    Schema preservati: entrambi — nessuna omologazione")

    # End session
    CONSENT_MANAGER.end_session(session.session_id)
    print("\n  [Sessione traduttore cognitivo chiusa]")


if __name__ == "__main__":
    run_bilateral_negotiation()
