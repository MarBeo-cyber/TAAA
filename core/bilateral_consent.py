"""
TAAA — Bilateral Consent System

The outward perception layer (monitoring the interlocutor's non-verbal signals)
is architecturally IMPOSSIBLE to activate without bilateral explicit consent.

This is not a policy — it is a hard constraint in the code.

Framing: the TAAA is a cognitive translator, not a personal spy tool.
Both parties activate it knowingly, as they would activate an interpreter service.
A human interpreter in a negotiation room observes both parties —
this is the core of their role, transparent and consensual.

Consent levels:
  NONE          — no session, M0/M1 only on M1 priors
  UNILATERAL    — single party; no outward biometric monitoring permitted
  BILATERAL     — both parties consented; full cognitive translation active
  MULTILATERAL  — group session (future: connected to Level 6 collective module)

Session handshake:
  Party A registers intent → generates invite token
  Party B receives token → confirms consent → session activated
  Both parties see: session active, translator enabled
"""

from __future__ import annotations

import time
import uuid
import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("taaa.bilateral_consent")


class ConsentLevel(Enum):
    NONE         = "none"
    UNILATERAL   = "unilateral"
    BILATERAL    = "bilateral"
    MULTILATERAL = "multilateral"


class ConsentStatus(Enum):
    PENDING   = "pending"
    ACTIVE    = "active"
    EXPIRED   = "expired"
    REVOKED   = "revoked"


@dataclass
class ConsentParty:
    """One party in a bilateral session."""
    party_id: str
    subject_id: str          # TAAA subject profile ID
    device_id: str           # Physical device identifier
    consented_at: float
    consent_scope: list[str] = field(default_factory=lambda: [
        "outward_audio",         # Silence/pause detection from audio
        "outward_nonverbal",     # Micro-expression and posture analysis
        "schema_sharing",        # Share detected schema gaps with other party
        "session_logging",       # Log session events for M2 learning
    ])
    revoked: bool = False

    def revoke(self):
        self.revoked = True
        logger.info("[Consent] Party %s revoked consent", self.party_id)


@dataclass
class BilateralSession:
    """
    An active bilateral cognitive translation session.

    Both parties have explicitly consented.
    Outward perception is enabled for both.
    Both see identical session status on their devices.

    This is the cognitive translation room —
    both participants know the interpreter is active.
    """
    session_id: str
    invite_token: str
    status: ConsentStatus
    created_at: float
    expires_at: float             # Sessions expire (default: 4 hours)
    parties: dict[str, ConsentParty] = field(default_factory=dict)
    session_type: str = "negotiation"  # negotiation | medical | academic | general
    language_pair: Optional[tuple] = None
    notes: str = ""

    @property
    def consent_level(self) -> ConsentLevel:
        active_parties = [p for p in self.parties.values() if not p.revoked]
        if len(active_parties) == 0:
            return ConsentLevel.NONE
        if len(active_parties) == 1:
            return ConsentLevel.UNILATERAL
        if len(active_parties) == 2:
            return ConsentLevel.BILATERAL
        return ConsentLevel.MULTILATERAL

    @property
    def outward_monitoring_permitted(self) -> bool:
        """Outward biometric monitoring is ONLY permitted with bilateral consent."""
        return (self.consent_level == ConsentLevel.BILATERAL and
                self.status == ConsentStatus.ACTIVE and
                not self._is_expired())

    @property
    def is_active(self) -> bool:
        return self.status == ConsentStatus.ACTIVE and not self._is_expired()

    def _is_expired(self) -> bool:
        if time.time() > self.expires_at:
            self.status = ConsentStatus.EXPIRED
            return True
        return False

    def add_party(self, subject_id: str, device_id: str) -> ConsentParty:
        party_id = f"party_{len(self.parties) + 1}"
        party = ConsentParty(
            party_id=party_id,
            subject_id=subject_id,
            device_id=device_id,
            consented_at=time.time(),
        )
        self.parties[subject_id] = party
        if len(self.parties) >= 2:
            self.status = ConsentStatus.ACTIVE
            logger.info("[Consent] Session %s ACTIVATED — bilateral consent confirmed",
                        self.session_id[:8])
        return party

    def revoke_party(self, subject_id: str):
        if subject_id in self.parties:
            self.parties[subject_id].revoke()
            # If any party revokes, session falls back to unilateral
            logger.info("[Consent] Party %s revoked — session downgraded", subject_id)

    def to_display(self) -> dict:
        """What both parties see on their devices."""
        return {
            "session_id":       self.session_id[:8] + "...",
            "status":           self.status.value,
            "consent_level":    self.consent_level.value,
            "parties":          len([p for p in self.parties.values() if not p.revoked]),
            "outward_active":   self.outward_monitoring_permitted,
            "expires_in_min":   max(0, int((self.expires_at - time.time()) / 60)),
            "session_type":     self.session_type,
            "interpreter_note": (
                "Traduttore cognitivo attivo — entrambe le parti hanno dato consenso."
                if self.outward_monitoring_permitted else
                "Sessione unilaterale — solo M1 priors attivi."
            ),
        }


class ConsentManager:
    """
    Manages bilateral consent sessions.

    The cognitive translator analogy:
    - Party A calls: "I need a cognitive interpreter for this meeting"
    - Invite token is generated and shared with Party B
    - Party B confirms: "I also want the cognitive interpreter"
    - Session is active — both see the interpreter is present
    - Either party can terminate at any moment (revoke)
    """

    SESSION_DURATION_H = 4.0    # Default session duration

    def __init__(self):
        self._sessions: dict[str, BilateralSession] = {}
        self._invite_tokens: dict[str, str] = {}   # token → session_id

    def create_session(self, initiator_subject_id: str,
                       initiator_device_id: str,
                       session_type: str = "negotiation",
                       duration_hours: float = SESSION_DURATION_H) -> BilateralSession:
        """
        Party A initiates a bilateral session.
        Returns session with invite token to share with Party B.
        """
        session_id = str(uuid.uuid4())
        invite_token = hashlib.sha256(
            f"{session_id}{time.time()}".encode()
        ).hexdigest()[:12].upper()

        session = BilateralSession(
            session_id=session_id,
            invite_token=invite_token,
            status=ConsentStatus.PENDING,
            created_at=time.time(),
            expires_at=time.time() + duration_hours * 3600,
            session_type=session_type,
        )
        session.add_party(initiator_subject_id, initiator_device_id)

        self._sessions[session_id] = session
        self._invite_tokens[invite_token] = session_id

        logger.info("[Consent] Session %s created by %s — token: %s",
                    session_id[:8], initiator_subject_id, invite_token)
        return session

    def join_session(self, invite_token: str,
                     joiner_subject_id: str,
                     joiner_device_id: str) -> Optional[BilateralSession]:
        """
        Party B joins with the invite token.
        This activates bilateral consent and enables outward monitoring.
        """
        session_id = self._invite_tokens.get(invite_token)
        if not session_id:
            logger.warning("[Consent] Invalid token: %s", invite_token)
            return None

        session = self._sessions.get(session_id)
        if not session or session._is_expired():
            return None

        if joiner_subject_id in session.parties:
            logger.warning("[Consent] Party already in session")
            return session

        session.add_party(joiner_subject_id, joiner_device_id)
        logger.info("[Consent] %s joined session %s — BILATERAL ACTIVE",
                    joiner_subject_id, session_id[:8])
        return session

    def get_session(self, session_id: str) -> Optional[BilateralSession]:
        return self._sessions.get(session_id)

    def get_session_for_subject(self, subject_id: str) -> Optional[BilateralSession]:
        for session in self._sessions.values():
            if (subject_id in session.parties and
                    session.is_active and
                    not session.parties[subject_id].revoked):
                return session
        return None

    def check_outward_permitted(self, subject_id: str) -> tuple[bool, str]:
        """
        The single point of truth for outward monitoring permission.
        Called by OutwardPerceptionLayer before any biometric analysis.
        """
        session = self.get_session_for_subject(subject_id)
        if not session:
            return False, "no_active_session"
        if not session.outward_monitoring_permitted:
            return False, f"consent_level={session.consent_level.value}"
        return True, "bilateral_consent_active"

    def end_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if session:
            session.status = ConsentStatus.REVOKED
            logger.info("[Consent] Session %s ended", session_id[:8])


# Global consent manager
CONSENT_MANAGER = ConsentManager()
