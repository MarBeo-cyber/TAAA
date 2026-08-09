"""
TAAA — MAAA Integration Bridge

Defines the protocol for bidirectional communication between
the TAAA and the MAAA (Metacognitive Autopoietic Adaptive Agent).

Integration points:

  MAAA → TAAA (sensor stream):
    - L1 Embodied Perception: camera frames, audio, IMU
    - L3 Human State: stress estimate, cognitive state, receptivity
    - L5 Continuity: session context, biographical memory

  TAAA → MAAA (output injection):
    - Translated schema content → injected into L4 Regulatory Engine
    - Pre-calibrated signal → delivered via L4 output channels
    - The TAAA respects MAAA's 4-filter Regulatory Engine:
      relevance, timing, brevity (max 9 words), urgency

  Domain routing:
    Emergency: TAAA-E operates as sub-module of MAAA with direct channel access
    Daily:     TAAA-D runs independently, uses MAAA only for sensor stream

STATUS: UNIMPLEMENTED PROTOCOL SKETCH.

This module defines the message shapes and the constraint checks for a TAAA↔MAAA
integration. There is no MAAA process in this repository, and nothing in the
TAAA pipeline imports this module: TAAAAgent, the REST API and the AR display
all run without it. Its only consumer is scenarios/negotiation_bilateral.py,
which drives it in simulation_mode to illustrate the protocol.

What is real here: TAAAInjection.validate() (the MAAA 9-word emergency
constraint), the injection log, and the pre-calibrated signal / debrief
builders. What is not real: any connection to a MAAA. `connect()` will attempt
an HTTP call and fall back to simulation; `get_human_state()` in simulation mode
returns values derived from the scenario_stress argument you pass it, not from
any sensor.

Do not cite this module as evidence that TAAA integrates with MAAA.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("taaa.maaa_bridge")


# ── Message types ─────────────────────────────────────────────────────────────

@dataclass
class MAAAStateUpdate:
    """Incoming from MAAA L3 — human state of the wearer."""
    timestamp: float
    stress_estimate: float       # 0–1
    cognitive_state: str         # "calm" | "alert" | "stressed" | "panicking" etc.
    receptivity: float           # 0–1
    decision_capacity: float     # 0–1
    panic_score: float
    hrv_ms: Optional[float]
    gsr: Optional[float]

    @property
    def is_ready_for_cultural_info(self) -> bool:
        """Is the wearer cognitively ready to process cultural bridge information?"""
        return self.receptivity > 0.60 and self.cognitive_state in ("calm", "alert")

    @property
    def m_level_from_maaa(self) -> str:
        """MAAA's estimate of appropriate M-level for this user state."""
        if self.stress_estimate > 0.80 or self.panic_score > 0.75:
            return "M0"
        if self.stress_estimate > 0.50:
            return "M1"
        return "M2"


@dataclass
class MAAASensorFrame:
    """Incoming from MAAA L1 — raw sensor data."""
    timestamp: float
    scene_condition: str         # "normal" | "smoky" | "dark" | "collapsed"
    ambient_db: float
    voice_detected: bool
    motion_magnitude: float
    environment_quality: float   # 0–1


@dataclass
class TAAAInjection:
    """
    TAAA content to inject into MAAA L4 Regulatory Engine output.
    Respects MAAA's 4-filter constraints.
    """
    timestamp: float
    domain: str                  # "emergency" | "daily"
    injection_type: str          # "schema_translation" | "pre_calibrated_signal" | "debrief"

    # Voice content (respects MAAA 9-word limit)
    voice_message: Optional[str]    # Max 9 words if emergency; longer if daily debrief

    # AR overlay
    ar_overlay: Optional[str]

    # Haptic
    haptic_pattern: Optional[str]

    # Metadata
    m_level: str
    urgency: str                 # "silent" | "ambient" | "normal" | "elevated" | "critical"
    schema_context: Optional[str] = None  # For debrief mode

    def validate(self) -> tuple[bool, str]:
        """Check that injection respects MAAA constraints."""
        if self.domain == "emergency":
            if self.voice_message and len(self.voice_message.split()) > 9:
                return False, f"voice_message_exceeds_9_words: {len(self.voice_message.split())}"
        return True, "ok"


# ── Bridge ────────────────────────────────────────────────────────────────────

class MAABridge:
    """
    TAAA-MAAA integration bridge — protocol sketch, not a live integration.

    In production: would connect via local API / shared memory with a MAAA
    process. No such process exists in this repository.
    In simulation (the default, and the only mode exercised): derives state
    arithmetically from the scenario_stress argument. Nothing is measured.
    """

    def __init__(self, simulation_mode: bool = True,
                 maaa_host: str = "localhost",
                 maaa_port: int = 5002):
        self.simulation_mode = simulation_mode
        self.maaa_host = maaa_host
        self.maaa_port = maaa_port
        self._connected = False
        self._last_state: Optional[MAAAStateUpdate] = None
        self._injection_log: list[TAAAInjection] = []

        if not simulation_mode:
            self._connect()

    def _connect(self):
        """Production: establish connection to MAAA REST API."""
        try:
            import requests
            resp = requests.get(
                f"http://{self.maaa_host}:{self.maaa_port}/status",
                timeout=2.0
            )
            if resp.status_code == 200:
                self._connected = True
                logger.info("[MAABridge] Connected to MAAA at %s:%d",
                            self.maaa_host, self.maaa_port)
            else:
                logger.warning("[MAABridge] MAAA returned %d", resp.status_code)
        except Exception as e:
            logger.warning("[MAABridge] Cannot connect to MAAA: %s — simulation mode", e)
            self.simulation_mode = True

    def get_human_state(self, scenario_stress: float = 0.2) -> MAAAStateUpdate:
        """
        Get current human state from MAAA L3.
        In simulation: generates state from stress estimate.
        """
        if not self.simulation_mode and self._connected:
            return self._fetch_maaa_state()
        return self._simulate_state(scenario_stress)

    def _fetch_maaa_state(self) -> MAAAStateUpdate:
        """Production: fetch from MAAA /human endpoint."""
        try:
            import requests
            resp = requests.get(
                f"http://{self.maaa_host}:{self.maaa_port}/human",
                timeout=1.0
            )
            d = resp.json()
            return MAAAStateUpdate(
                timestamp=time.time(),
                stress_estimate=d.get("stress_score", 0.2),
                cognitive_state=d.get("state", "calm"),
                receptivity=d.get("receptivity", 0.8),
                decision_capacity=d.get("decision_capacity", 0.9),
                panic_score=d.get("panic_score", 0.0),
                hrv_ms=None,
                gsr=None,
            )
        except Exception as e:
            logger.warning("[MAABridge] Fetch failed: %s", e)
            return self._simulate_state(0.2)

    def _simulate_state(self, stress: float) -> MAAAStateUpdate:
        """Derive a MAAA-shaped state from the stress number the caller passed.
        A formula over one argument, not a reading."""
        receptivity = max(0.1, 1.0 - stress * 0.7)
        if stress > 0.80:
            state = "panicking"
        elif stress > 0.60:
            state = "stressed"
        elif stress > 0.35:
            state = "alert"
        else:
            state = "calm"

        update = MAAAStateUpdate(
            timestamp=time.time(),
            stress_estimate=stress,
            cognitive_state=state,
            receptivity=round(receptivity, 2),
            decision_capacity=round(max(0.1, receptivity * 0.95), 2),
            panic_score=max(0.0, stress - 0.5) * 2,
            hrv_ms=max(15.0, 60.0 - stress * 45.0),
            gsr=min(1.0, stress * 1.2),
        )
        self._last_state = update
        return update

    def inject_to_maaa(self, injection: TAAAInjection) -> bool:
        """
        Inject TAAA translation content into MAAA output channel.
        In production: POST to MAAA /taaa/inject endpoint.
        In simulation: log and return success.
        """
        valid, reason = injection.validate()
        if not valid:
            logger.warning("[MAABridge] Injection rejected: %s", reason)
            return False

        self._injection_log.append(injection)

        if not self.simulation_mode and self._connected:
            try:
                import requests
                resp = requests.post(
                    f"http://{self.maaa_host}:{self.maaa_port}/taaa/inject",
                    json={
                        "voice_message":  injection.voice_message,
                        "ar_overlay":     injection.ar_overlay,
                        "haptic_pattern": injection.haptic_pattern,
                        "urgency":        injection.urgency,
                        "m_level":        injection.m_level,
                    },
                    timeout=0.1,  # Must be fast
                )
                return resp.status_code == 200
            except Exception as e:
                logger.warning("[MAABridge] Inject failed: %s", e)
                return False

        logger.debug("[MAABridge] Injection logged (sim): %s | %s",
                     injection.injection_type, injection.voice_message)
        return True

    def build_pre_calibrated_signal(self,
                                    signal_type: str,
                                    m_level: str = "M1") -> TAAAInjection:
        """
        Build a pre-calibrated haptic/visual signal (no text in real-time).
        The wearer has been trained to recognise these patterns in setup.

        signal_type:
          "cultural_pause"   → amber peripheral dot + single haptic buzz
          "schema_gap"       → amber peripheral dot (no haptic)
          "response_imminent" → dim flash (interlocutor about to speak)
          "wait"             → double haptic pulse
        """
        signal_map = {
            "cultural_pause": {
                "haptic_pattern": "single_soft_buzz",
                "ar_overlay":     "AMBER_DOT_PERIPHERY",
                "voice_message":  None,   # NO text in real-time
                "urgency":        "ambient",
            },
            "schema_gap": {
                "haptic_pattern": None,
                "ar_overlay":     "AMBER_DOT_PERIPHERY_DIM",
                "voice_message":  None,
                "urgency":        "ambient",
            },
            "response_imminent": {
                "haptic_pattern": None,
                "ar_overlay":     "PERIPHERAL_DIM_FLASH",
                "voice_message":  None,
                "urgency":        "ambient",
            },
            "wait": {
                "haptic_pattern": "double_soft_pulse",
                "ar_overlay":     "AMBER_DOT_PERIPHERY",
                "voice_message":  None,
                "urgency":        "ambient",
            },
        }
        s = signal_map.get(signal_type, signal_map["schema_gap"])
        return TAAAInjection(
            timestamp=time.time(),
            domain="daily",
            injection_type="pre_calibrated_signal",
            voice_message=s["voice_message"],
            ar_overlay=s["ar_overlay"],
            haptic_pattern=s["haptic_pattern"],
            m_level=m_level,
            urgency=s["urgency"],
        )

    def build_debrief(self, schema_explanation: str,
                      timing: str = "after_natural_pause") -> TAAAInjection:
        """
        Build a debrief injection — full explanation delivered after the moment.
        No 9-word limit: the user is in a natural break, System 2 available.
        """
        return TAAAInjection(
            timestamp=time.time(),
            domain="daily",
            injection_type="debrief",
            voice_message=None,   # Debrief is visual/text, not voice
            ar_overlay=f"DEBRIEF_CARD: {schema_explanation[:80]}",
            haptic_pattern=None,
            m_level="M2",
            urgency="ambient",
            schema_context=schema_explanation,
        )

    @property
    def injection_count(self) -> int:
        return len(self._injection_log)

    @property
    def connected(self) -> bool:
        return self._connected or self.simulation_mode
