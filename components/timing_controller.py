"""
TAAA — Timing Controller

The Timing Controller estimates the user's position on their individual
cognitive regression curve and selects the optimal intervention timing.

Key insight: the threshold between cultural processing (System 2)
and M0 (System 1) is NOT a binary switch. It is a continuous cursor
that moves along the individual regression curve as stress increases.

Under acute stress, System 2 is progressively disabled.
M0 becomes MORE accessible, not less.
The person in panic is cognitively closer to the 7-month-old
at the visual cliff than to their normal cultural self.

The regression curve is calibrated in setup Phase 2 (stress tests).
PAAA provides real-time biometric position estimation.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger("taaa.timing_controller")


class MLevel(Enum):
    """Current operating schema memory level."""
    M2 = "M2"   # Personal schema topology available
    M1 = "M1"   # Cultural/professional prior
    M0 = "M0"   # Universal archetypes only


class OutputType(Enum):
    """Recommended output format for current M-level."""
    RICH_DIALOGUE     = "rich_dialogue"      # M2: full translation, bidirectional
    CULTURAL_BRIDGE   = "cultural_bridge"    # M1: cultural prior adaptation
    M0_AR_HAPTIC      = "m0_ar_haptic"       # M0: AR overlay + haptic only
    M0_SINGLE_IMPERATIVE = "m0_single_imperative"  # M0 extreme: one word + gesture


@dataclass
class RegressionCurveProfile:
    """
    Individual regression curve: stress level → M-level.
    Calibrated in setup Phase 2.
    Determines how quickly this person shifts from System 2 to M0.
    """
    profile_id: str

    # Stress thresholds at which M-level transitions
    m2_to_m1_threshold: float      # stress > this → drop from M2 to M1
    m1_to_m0_threshold: float      # stress > this → drop from M1 to M0
    m0_pure_threshold: float       # stress > this → single imperative only

    # Shape of the curve
    regression_speed: str          # "fast" | "medium" | "slow"
    # fast = emergency responder; slow = high-stress tolerance individual

    # Biometric correlates (from PAAA calibration)
    hrv_m2_threshold: float        # HRV above this = M2 processing available
    hrv_m0_threshold: float        # HRV below this = M0 only
    gsr_interference_threshold: float  # GSR above this = high arousal

    @classmethod
    def default_civilian(cls) -> "RegressionCurveProfile":
        """Conservative default for uncalibrated civilian users."""
        return cls(
            profile_id="default_civilian",
            m2_to_m1_threshold=0.35,
            m1_to_m0_threshold=0.60,
            m0_pure_threshold=0.82,
            regression_speed="medium",
            hrv_m2_threshold=45.0,
            hrv_m0_threshold=25.0,
            gsr_interference_threshold=0.65,
        )

    @classmethod
    def emergency_professional(cls) -> "RegressionCurveProfile":
        """Calibrated profile for trained emergency responders."""
        return cls(
            profile_id="emergency_professional",
            m2_to_m1_threshold=0.55,
            m1_to_m0_threshold=0.78,
            m0_pure_threshold=0.92,
            regression_speed="slow",
            hrv_m2_threshold=35.0,
            hrv_m0_threshold=18.0,
            gsr_interference_threshold=0.80,
        )

    @classmethod
    def high_anxiety_trait(cls) -> "RegressionCurveProfile":
        """Profile for individuals with high trait anxiety."""
        return cls(
            profile_id="high_anxiety_trait",
            m2_to_m1_threshold=0.20,
            m1_to_m0_threshold=0.42,
            m0_pure_threshold=0.65,
            regression_speed="fast",
            hrv_m2_threshold=55.0,
            hrv_m0_threshold=35.0,
            gsr_interference_threshold=0.50,
        )


@dataclass
class TimingDecision:
    """Output of the Timing Controller for one cycle."""
    timestamp: float
    current_m_level: MLevel
    stress_estimate: float          # 0–1
    output_type: OutputType
    delay_before_output_ms: float   # wait before delivering (0 = immediate)
    intervention_window_ms: float   # time available to intervene
    paaa_biometrics_used: bool
    rationale: str


class TimingController:
    """
    Estimates position on individual cognitive regression curve.
    Decides M-level, output type, and delivery timing.

    In emergency domain: uses PAAA biometrics for real-time estimation.
    In daily domain: uses conversational signals + self-report.
    """

    def __init__(self, curve: Optional[RegressionCurveProfile] = None):
        self.curve = curve or RegressionCurveProfile.default_civilian()
        self._history: list[float] = []   # recent stress estimates
        self._last_decision: Optional[TimingDecision] = None

    def calibrate(self, curve: RegressionCurveProfile):
        """Update regression curve after setup Phase 2."""
        self.curve = curve
        logger.info("[TimingController] Calibrated: %s (speed=%s)",
                    curve.profile_id, curve.regression_speed)

    def decide(self,
               stress_estimate: float,
               paaa_hrv: Optional[float] = None,
               paaa_gsr: Optional[float] = None,
               domain: str = "daily",
               interference_timing_window_ms: Optional[int] = None) -> TimingDecision:
        """
        Compute timing decision for current moment.

        stress_estimate: 0–1 from MAAA L3 or PAAA
        paaa_hrv: HRV in ms (optional, from PAAA)
        paaa_gsr: galvanic skin response 0–1 (optional, from PAAA)
        domain: "emergency" | "daily"
        interference_timing_window_ms: from InterferencePrediction
        """
        # Fuse stress estimate with PAAA biometrics if available
        fused_stress = stress_estimate
        paaa_used = False

        if paaa_hrv is not None:
            # Low HRV = high stress
            hrv_stress = 1.0 - min(1.0, max(0.0,
                (paaa_hrv - self.curve.hrv_m0_threshold) /
                (self.curve.hrv_m2_threshold - self.curve.hrv_m0_threshold)
            ))
            fused_stress = 0.6 * stress_estimate + 0.4 * hrv_stress
            paaa_used = True

        if paaa_gsr is not None:
            gsr_stress = min(1.0, paaa_gsr / self.curve.gsr_interference_threshold)
            fused_stress = 0.7 * fused_stress + 0.3 * gsr_stress
            paaa_used = True

        # Smooth with recent history (exponential moving average)
        self._history.append(fused_stress)
        if len(self._history) > 10:
            self._history.pop(0)
        smoothed = sum(w * v for w, v in zip(
            [0.4, 0.2, 0.1, 0.1, 0.05, 0.05, 0.025, 0.025, 0.0125, 0.0125][:len(self._history)],
            reversed(self._history)
        )) / sum([0.4, 0.2, 0.1, 0.1, 0.05, 0.05, 0.025, 0.025, 0.0125, 0.0125][:len(self._history)])

        # Map stress → M-level using individual curve
        if smoothed >= self.curve.m0_pure_threshold:
            m_level = MLevel.M0
            output_type = OutputType.M0_SINGLE_IMPERATIVE
        elif smoothed >= self.curve.m1_to_m0_threshold:
            m_level = MLevel.M0
            output_type = OutputType.M0_AR_HAPTIC
        elif smoothed >= self.curve.m2_to_m1_threshold:
            m_level = MLevel.M1
            output_type = OutputType.CULTURAL_BRIDGE
        else:
            m_level = MLevel.M2
            output_type = OutputType.RICH_DIALOGUE

        # Emergency domain forces M0 if any significant stress
        if domain == "emergency" and smoothed > 0.45:
            m_level = MLevel.M0
            output_type = OutputType.M0_AR_HAPTIC if smoothed < self.curve.m0_pure_threshold \
                          else OutputType.M0_SINGLE_IMPERATIVE

        # Delivery timing
        delay_ms = 0.0
        window_ms = interference_timing_window_ms or 500.0

        if m_level == MLevel.M0 and output_type == OutputType.M0_SINGLE_IMPERATIVE:
            delay_ms = 0.0    # Immediate in extreme M0
        elif output_type == OutputType.M0_AR_HAPTIC:
            delay_ms = 50.0   # Minimal delay for AR rendering
        elif output_type == OutputType.CULTURAL_BRIDGE:
            delay_ms = 200.0  # Brief pause to avoid flooding
        else:
            delay_ms = 500.0  # Rich dialogue — human timing

        rationale = (
            f"stress={smoothed:.2f} → {m_level.value} "
            f"(curve: {self.curve.profile_id}, speed={self.curve.regression_speed})"
        )

        decision = TimingDecision(
            timestamp=time.time(),
            current_m_level=m_level,
            stress_estimate=round(smoothed, 3),
            output_type=output_type,
            delay_before_output_ms=delay_ms,
            intervention_window_ms=window_ms,
            paaa_biometrics_used=paaa_used,
            rationale=rationale,
        )
        self._last_decision = decision
        return decision

    @property
    def current_m_level(self) -> MLevel:
        if self._last_decision:
            return self._last_decision.current_m_level
        return MLevel.M2

    def regression_curve_summary(self) -> dict:
        return {
            "profile_id": self.curve.profile_id,
            "m2_to_m1_at_stress": self.curve.m2_to_m1_threshold,
            "m1_to_m0_at_stress": self.curve.m1_to_m0_threshold,
            "m0_pure_at_stress":  self.curve.m0_pure_threshold,
            "regression_speed":   self.curve.regression_speed,
            "note": "Cursor position on individual curve. Not a binary switch.",
        }
