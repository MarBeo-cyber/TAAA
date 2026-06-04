"""
TAAA — Outward Perception Layer

Monitors the interlocutor's non-verbal signals.
REQUIRES bilateral consent — architecturally enforced, not just policy.

The cognitive translator analogy:
A human interpreter reads micro-expressions of both parties.
This is their core function, transparent and consensual.
OutwardPerceptionLayer is the AI equivalent.

Signal categories:

  PROCESSING_SIGNALS — interlocutor is actively processing, not ready to respond
    - Gaze: slightly upward or lateral (internal retrieval)
    - Posture: stable, not opening toward speaker
    - No pre-speech breath pattern
    - Micro-expression: contemplation (brow slightly raised, slight lip tension)

  RESPONSE_READY_SIGNALS — interlocutor is about to respond
    - Gaze: returning to speaker
    - Posture: slight forward lean or opening
    - Pre-speech breath intake (universal, cross-cultural)
    - Micro-expression: resolution (expression relaxes toward response)

  DISCOMFORT_SIGNALS — interlocutor is experiencing schema friction
    - Micro-expression: confusion, surprise, controlled frustration
    - Slight head tilt (signal of processing unexpected input)
    - Increased blink rate (cognitive load)

Key insight (Ekman):
The TIMING of silence varies by individual (Tanaka-san: 1s, Yoko-san: 2s).
The SIGNALS of active processing are largely universal.
We read signals, not durations.
"""

from __future__ import annotations

import time
import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.bilateral_consent import CONSENT_MANAGER

logger = logging.getLogger("taaa.outward_perception")


class InterlocutorState(Enum):
    UNKNOWN          = "unknown"
    LISTENING        = "listening"
    PROCESSING       = "processing"       # Active thinking — do NOT interrupt
    RESPONSE_READY   = "response_ready"   # About to speak
    DISCOMFORT       = "discomfort"       # Schema friction detected
    AGREEMENT        = "agreement"
    INDIRECT_REFUSAL = "indirect_refusal" # High-context refusal pattern


@dataclass
class NonVerbalSignals:
    """Detected non-verbal signals from the interlocutor."""
    timestamp: float
    state: InterlocutorState
    confidence: float              # 0–1

    # Gaze
    gaze_direction: str            # "toward_speaker" | "internal" | "away"
    eye_contact: bool

    # Posture
    posture_opening: bool          # leaning toward = opening
    posture_stable: bool

    # Pre-speech signals
    pre_speech_breath: bool        # Universal: breath intake before speaking
    lip_movement: bool             # Pre-articulation movement

    # Micro-expressions (Ekman universal categories)
    micro_expression: Optional[str] = None  # "contemplation" | "discomfort" | "agreement"

    # Active silence indicator
    silence_active: bool = False   # True = silence is processing, not absence
    silence_duration_ms: float = 0.0

    @property
    def is_processing_active(self) -> bool:
        """Key question: is this silence alive or empty?"""
        return (self.state == InterlocutorState.PROCESSING and
                self.silence_active and
                not self.pre_speech_breath)

    @property
    def about_to_speak(self) -> bool:
        return (self.pre_speech_breath or
                self.state == InterlocutorState.RESPONSE_READY)


@dataclass
class OutwardPerceptionResult:
    """Full outward perception output for one cycle."""
    timestamp: float
    permitted: bool
    denial_reason: Optional[str]
    signals: Optional[NonVerbalSignals]
    trigger_recommendation: Optional[str]  # "wait" | "ready_to_speak_now" | "discomfort_detected"


class OutwardPerceptionLayer:
    """
    Monitors interlocutor non-verbal signals.

    In production: uses AR forward camera + OpenFace 2 / MediaPipe
    for micro-expression analysis, combined with directional microphone
    for silence/pause/pre-speech breath detection.

    In simulation: generates realistic signal patterns based on
    cultural profile and scenario context.

    HARD CONSTRAINT: all methods check bilateral consent before
    any analysis. Returns empty/denied result if consent absent.
    """

    def __init__(self, simulation_mode: bool = True):
        self.simulation_mode = simulation_mode
        self._silence_start: Optional[float] = None
        self._last_state = InterlocutorState.UNKNOWN

    def observe(self, observer_subject_id: str,
                interlocutor_profile: Optional[dict] = None,
                scenario_context: str = "") -> OutwardPerceptionResult:
        """
        One observation cycle of the interlocutor.

        observer_subject_id: the WEARING party (e.g., David)
        interlocutor_profile: cultural/personal profile of the other party
        scenario_context: current conversation context
        """
        ts = time.time()

        # ── Consent check — hard gate ─────────────────────────────────────────
        permitted, reason = CONSENT_MANAGER.check_outward_permitted(observer_subject_id)
        if not permitted:
            return OutwardPerceptionResult(
                timestamp=ts,
                permitted=False,
                denial_reason=reason,
                signals=None,
                trigger_recommendation=None,
            )

        # ── Observation ───────────────────────────────────────────────────────
        if self.simulation_mode:
            signals = self._simulate_signals(interlocutor_profile, scenario_context)
        else:
            signals = self._observe_realtime()

        # ── Trigger recommendation ────────────────────────────────────────────
        trigger = None
        if signals.is_processing_active:
            trigger = "wait"          # Silence is alive — do NOT interrupt
        elif signals.about_to_speak:
            trigger = "response_imminent"  # Interlocutor about to respond
        elif signals.state == InterlocutorState.DISCOMFORT:
            trigger = "schema_friction_detected"
        elif signals.state == InterlocutorState.INDIRECT_REFUSAL:
            trigger = "indirect_refusal_pattern"

        return OutwardPerceptionResult(
            timestamp=ts,
            permitted=True,
            denial_reason=None,
            signals=signals,
            trigger_recommendation=trigger,
        )

    def _simulate_signals(self, profile: Optional[dict],
                          context: str) -> NonVerbalSignals:
        """
        Simulate realistic non-verbal signals.
        East Asian business context: high probability of active processing silence.
        """
        ts = time.time()
        culture = (profile or {}).get("culture", "unknown")

        # Simulate different phases of the negotiation silence
        elapsed = ts % 10   # Cycle through phases for demo purposes

        if elapsed < 3.0:
            # Active processing phase
            state = InterlocutorState.PROCESSING
            if self._silence_start is None:
                self._silence_start = ts
            silence_ms = (ts - self._silence_start) * 1000

            return NonVerbalSignals(
                timestamp=ts,
                state=state,
                confidence=0.82,
                gaze_direction="internal",
                eye_contact=False,
                posture_opening=False,
                posture_stable=True,
                pre_speech_breath=False,
                lip_movement=False,
                micro_expression="contemplation",
                silence_active=True,
                silence_duration_ms=silence_ms,
            )

        elif elapsed < 5.0:
            # Preparing to respond
            self._silence_start = None
            return NonVerbalSignals(
                timestamp=ts,
                state=InterlocutorState.RESPONSE_READY,
                confidence=0.78,
                gaze_direction="toward_speaker",
                eye_contact=True,
                posture_opening=True,
                posture_stable=False,
                pre_speech_breath=True,    # The universal signal
                lip_movement=False,
                micro_expression="resolution",
                silence_active=False,
                silence_duration_ms=0,
            )
        else:
            # Listening
            return NonVerbalSignals(
                timestamp=ts,
                state=InterlocutorState.LISTENING,
                confidence=0.90,
                gaze_direction="toward_speaker",
                eye_contact=True,
                posture_opening=True,
                posture_stable=True,
                pre_speech_breath=False,
                lip_movement=False,
                micro_expression=None,
                silence_active=False,
                silence_duration_ms=0,
            )

    def _observe_realtime(self) -> NonVerbalSignals:
        """
        Production: connect to AR camera + OpenFace 2 / MediaPipe.
        Replace this method with actual computer vision pipeline.
        """
        raise NotImplementedError(
            "Production outward perception requires "
            "AR forward camera + OpenFace 2 integration"
        )


# ── Pre-Speech Breath Detector (audio-based, lower privacy cost) ──────────────

class SilenceMonitor:
    """
    Audio-based silence and pre-speech detection.
    Lower privacy cost than video: detects acoustic patterns only.
    Usable with unilateral consent (no biometric facial data).

    Detects:
    - Silence duration and pattern
    - Pre-speech breath intake (acoustic signature)
    - Speech rate changes
    """

    SILENCE_THRESHOLD_DB = -40.0
    PRE_SPEECH_BREATH_PATTERN_MS = 150   # Typical pre-speech breath duration

    def __init__(self):
        self._silence_start: Optional[float] = None
        self._in_silence = False

    def process_audio_frame(self, rms_db: float,
                            is_breath_pattern: bool = False) -> dict:
        """Process one audio frame and return silence state."""
        ts = time.time()

        if rms_db < self.SILENCE_THRESHOLD_DB:
            if not self._in_silence:
                self._silence_start = ts
                self._in_silence = True
            silence_ms = (ts - self._silence_start) * 1000
        else:
            self._in_silence = False
            self._silence_start = None
            silence_ms = 0.0

        return {
            "in_silence":         self._in_silence,
            "silence_duration_ms": silence_ms,
            "pre_speech_breath":  is_breath_pattern,
            "audio_only":         True,   # No biometric data
            "requires_bilateral": False,  # Audio monitoring, not biometric
        }
