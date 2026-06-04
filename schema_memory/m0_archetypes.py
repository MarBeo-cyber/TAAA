"""
TAAA — Schema Memory Layer M0: Universal Archetypes
Translational Autopoietic Adaptive Agent

M0 is the pre-cultural, pre-loaded layer of Schema Memory.
It formalises the DISL (Diagrammatic Image Schema Language) primitives
of Hedblom et al. (2024) using a DSR-inspired (Declarative Spatial
Reasoning) representation, implementable with qualitative constraints.

M0 is NEVER learned from individual interaction.
It is a formal theory Gamma pre-loaded at system initialisation.
Its models represent possible instantiations of universal schemas.

Biological grounding (Gibson & Walk 1960, cross-species evidence):
  - Visual cliff response: babies + kittens + chicks + lambs all stop
  - Neonatal reflexes: present at birth, before any cultural learning
  - Looming response: 2-week-old infants avoid expanding objects
  These establish M0 as pre-cultural, not merely cross-cultural.

References:
  Hedblom et al. (2024). The Diagrammatic Image Schema Language (DISL).
  Olivier & Bouraoui (2025). Grounding Agent Reasoning in Image Schemas.
  Gibson & Walk (1960). The visual cliff. Scientific American.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ── Primitive Classification (DISL Table 1) ───────────────────────────────────

class PrimitiveClass(Enum):
    SPATIAL         = "spatial"
    SPATIOTEMPORAL  = "spatiotemporal"
    FORCE_DYNAMIC   = "force_dynamic"


class Primitive(Enum):
    """All conceptual primitives from Hedblom et al. DISL (2024)."""
    # Spatial entity primitives
    OBJECT          = ("OBJECT",        PrimitiveClass.SPATIAL)
    CONTAINER       = ("CONTAINER",     PrimitiveClass.SPATIAL)
    PATH            = ("PATH",          PrimitiveClass.SPATIAL)
    REGION          = ("REGION",        PrimitiveClass.SPATIAL)
    DOWN            = ("DOWN",          PrimitiveClass.SPATIAL)
    UP              = ("UP",            PrimitiveClass.SPATIAL)

    # Spatial relational primitives
    LOCATION        = ("LOCATION",      PrimitiveClass.SPATIAL)
    START_PATH      = ("START_PATH",    PrimitiveClass.SPATIAL)
    END_PATH        = ("END_PATH",      PrimitiveClass.SPATIAL)
    CONTACT         = ("CONTACT",       PrimitiveClass.SPATIAL)
    CONTAINED       = ("CONTAINED",     PrimitiveClass.SPATIAL)
    PART_OF         = ("PART_OF",       PrimitiveClass.SPATIAL)
    SMALLER         = ("SMALLER",       PrimitiveClass.SPATIAL)
    LARGER          = ("LARGER",        PrimitiveClass.SPATIAL)

    # Spatial attributive primitives
    OPEN            = ("OPEN",          PrimitiveClass.SPATIAL)
    CLOSED          = ("CLOSED",        PrimitiveClass.SPATIAL)
    EMPTY           = ("EMPTY",         PrimitiveClass.SPATIAL)
    OCCUPIED        = ("OCCUPIED",      PrimitiveClass.SPATIAL)
    FULL            = ("FULL",          PrimitiveClass.SPATIAL)

    # Spatiotemporal primitives
    PERMANENCE      = ("PERMANENCE",    PrimitiveClass.SPATIOTEMPORAL)
    MOTION          = ("MOTION",        PrimitiveClass.SPATIOTEMPORAL)
    AT_REST         = ("AT_REST",       PrimitiveClass.SPATIOTEMPORAL)
    ANIMATE_MOTION  = ("ANIMATE_MOTION", PrimitiveClass.SPATIOTEMPORAL)
    INANIMATE_MOTION = ("INANIMATE_MOTION", PrimitiveClass.SPATIOTEMPORAL)

    # Force dynamic primitives
    LINK            = ("LINK",          PrimitiveClass.FORCE_DYNAMIC)
    ACTIVE_UMPH     = ("ACTIVE_UMPH",   PrimitiveClass.FORCE_DYNAMIC)
    PASSIVE_UMPH    = ("PASSIVE_UMPH",  PrimitiveClass.FORCE_DYNAMIC)

    def __init__(self, label: str, cls: PrimitiveClass):
        self.label = label
        self.primitive_class = cls


# ── Image Schemas (combinations of primitives) ────────────────────────────────

@dataclass
class ImageSchema:
    """
    A formal image schema: a small theory over DISL primitives.
    Each schema corresponds to a Gamma in DSR/Equilibrium Logic terms.
    Biological grounding documents the pre-cultural evidence.
    """
    name: str
    primitives: list[Primitive]
    description: str
    biological_grounding: str        # Empirical pre-cultural evidence
    emergency_relevance: float       # 0-1, priority in M0 emergency subset
    ar_output: str                   # What to render in AR for this schema
    haptic_pattern: str              # Haptic output pattern

    def __repr__(self):
        return f"ImageSchema({self.name}, primitives={len(self.primitives)}, emergency={self.emergency_relevance:.1f})"


# ── M0 Emergency Subset Taxonomy ─────────────────────────────────────────────
# The minimum sufficient set for emergency domain coverage.
# Selected by analysis of critical scenarios:
# evacuation, medical emergency, spatial disorientation.

M0_EMERGENCY_SCHEMAS: list[ImageSchema] = [

    ImageSchema(
        name="FALLING_DANGER",
        primitives=[Primitive.DOWN, Primitive.BOUNDARY if hasattr(Primitive, 'BOUNDARY')
                    else Primitive.CONTAINER, Primitive.ANIMATE_MOTION, Primitive.PASSIVE_UMPH],
        description=(
            "Discontinuity below the agent that would cause downward motion "
            "under gravity if boundary is crossed. The paradigm case is the visual cliff."
        ),
        biological_grounding=(
            "Gibson & Walk (1960): 6-8 month infants stop at transparent surface "
            "showing drop below. Replicated with kittens, chicks, lambs, rats. "
            "Cross-species universality establishes pre-cultural status."
        ),
        emergency_relevance=1.0,
        ar_output="RED_BOUNDARY_FLOOR + DOWN_ARROW + STOP_HAPTIC",
        haptic_pattern="continuous_vibration",
    ),

    ImageSchema(
        name="SAFE_PATH",
        primitives=[Primitive.PATH, Primitive.START_PATH, Primitive.END_PATH,
                    Primitive.ANIMATE_MOTION, Primitive.OPEN],
        description=(
            "A traversable route from current location to a goal (exit). "
            "Requires: path exists, is open (no obstruction), leads to END_PATH."
        ),
        biological_grounding=(
            "Neonatal orienting reflex: newborns orient toward open paths. "
            "SOURCE_PATH_GOAL is among the earliest spatial schemas documented "
            "in developmental psychology (Mandler & Canovas 2014)."
        ),
        emergency_relevance=1.0,
        ar_output="GREEN_ARROW_PATH + PULSING_DIRECTION",
        haptic_pattern="directional_pulse",
    ),

    ImageSchema(
        name="DANGER_ZONE",
        primitives=[Primitive.REGION, Primitive.CONTAINED, Primitive.CLOSED,
                    Primitive.PASSIVE_UMPH],
        description=(
            "A region with active force or hazard that the agent must not enter. "
            "The CONTAINER boundary marks exclusion, not inclusion."
        ),
        biological_grounding=(
            "Looming response: 2-week-old infants avoid regions where expanding "
            "objects (SMALLER->LARGER) indicate approach. Universally documented "
            "across species (Yonas et al. 1977)."
        ),
        emergency_relevance=0.95,
        ar_output="RED_REGION_OVERLAY + EXCLUSION_MARKING",
        haptic_pattern="warning_pulse",
    ),

    ImageSchema(
        name="STOP",
        primitives=[Primitive.AT_REST, Primitive.ANIMATE_MOTION],
        description=(
            "Transition from animate motion to rest. The most primitive "
            "emergency command: cessation of current trajectory."
        ),
        biological_grounding=(
            "Freeze response: universal across mammals under acute threat. "
            "Tonic immobility is the biological AT_REST under passive-UMPH (threat). "
            "Operates below voluntary control."
        ),
        emergency_relevance=1.0,
        ar_output="STOP_SIGN_AR + BLOCK_ARROW",
        haptic_pattern="sharp_stop",
    ),

    ImageSchema(
        name="STRUCTURAL_INSTABILITY",
        primitives=[Primitive.OBJECT, Primitive.PASSIVE_UMPH, Primitive.INANIMATE_MOTION,
                    Primitive.DOWN],
        description=(
            "An object subject to downward inanimate motion — potential collapse. "
            "Gravity (passive-UMPH) acts on structure, producing INANIMATE_MOTION downward."
        ),
        biological_grounding=(
            "Object permanence + gravity expectation: by 4 months infants expect "
            "unsupported objects to fall (Spelke et al. 1992). "
            "The gravity schema is one of the earliest physical intuitions."
        ),
        emergency_relevance=0.90,
        ar_output="INSTABILITY_MARKER + DOWN_FORCE_INDICATOR",
        haptic_pattern="escalating_vibration",
    ),

    ImageSchema(
        name="PERSON_IN_DISTRESS",
        primitives=[Primitive.ANIMATE_MOTION, Primitive.OBJECT, Primitive.CONTACT,
                    Primitive.PASSIVE_UMPH],
        description=(
            "Another animate entity subject to force (passive-UMPH) — someone "
            "who is hurt, trapped, or under active threat."
        ),
        biological_grounding=(
            "Biological motion detection is pre-cultural and cross-species. "
            "Johansson (1973): infants preferentially attend to point-light displays "
            "of animate motion. Distress signals in animate entities trigger "
            "universal approach/help responses."
        ),
        emergency_relevance=0.85,
        ar_output="PERSON_HIGHLIGHT + HELP_INDICATOR",
        haptic_pattern="double_pulse",
    ),

    ImageSchema(
        name="EXIT",
        primitives=[Primitive.CONTAINER, Primitive.OPEN, Primitive.PATH,
                    Primitive.END_PATH, Primitive.ANIMATE_MOTION],
        description=(
            "A CONTAINER (building, room) with an OPEN boundary that connects "
            "to a PATH leading outside. The universal escape schema."
        ),
        biological_grounding=(
            "Container schemas are among the earliest established (Mandler 1992). "
            "OBJECT_INTO/OUT_OF_CONTAINER documented in infants 3-5 months. "
            "EXIT is the OUT_OF_CONTAINER variant applied to animate self."
        ),
        emergency_relevance=0.95,
        ar_output="EXIT_ARROW + GREEN_BOUNDARY_OPENING",
        haptic_pattern="directional_pulse",
    ),

    ImageSchema(
        name="LINK_TO_SAFETY",
        primitives=[Primitive.LINK, Primitive.OBJECT, Primitive.ANIMATE_MOTION],
        description=(
            "A connection (rope, hand, cable) between the agent and a safe anchor "
            "or guide. LINK schema: two objects connected by a force-maintaining bond."
        ),
        biological_grounding=(
            "Grasping reflex: present at birth, activated by CONTACT. "
            "LINK schema = sustained CONTACT with active force maintenance. "
            "Among the first schemas established (Mandler & Canovas 2014)."
        ),
        emergency_relevance=0.75,
        ar_output="LINK_INDICATOR + FOLLOW_DIRECTION",
        haptic_pattern="sustained_vibration",
    ),
]

# ── Gravity as default rule (DSR/Equilibrium Logic) ──────────────────────────
# Formalised in Equilibrium Logic as:
#   □(∀x (¬∃y on(x,y) → moveDown(x)))
# Objects fall unless supported. Default negation: assume fall unless support proven.

GRAVITY_DEFAULT = {
    "name": "GRAVITY",
    "formal": "forall x: (not exists y: on(x,y)) -> moveDown(x)",
    "temporal": "always",
    "primitive": Primitive.PASSIVE_UMPH,
    "note": "Default rule — non-monotonic. Holds unless support proven."
}


# ── M0 Registry ──────────────────────────────────────────────────────────────

class M0Registry:
    """
    Pre-loaded M0 knowledge base. Immutable after initialisation.
    Provides schema lookup, instantiation, and AR/haptic output generation.
    """

    def __init__(self):
        self._schemas: dict[str, ImageSchema] = {
            s.name: s for s in M0_EMERGENCY_SCHEMAS
        }
        self._primitive_index: dict[Primitive, list[str]] = {}
        self._build_index()

    def _build_index(self):
        for schema in self._schemas.values():
            for prim in schema.primitives:
                self._primitive_index.setdefault(prim, []).append(schema.name)

    def get(self, name: str) -> Optional[ImageSchema]:
        return self._schemas.get(name)

    def all_schemas(self) -> list[ImageSchema]:
        return list(self._schemas.values())

    def emergency_subset(self, threshold: float = 0.85) -> list[ImageSchema]:
        """Returns schemas above emergency relevance threshold, sorted by priority."""
        return sorted(
            [s for s in self._schemas.values() if s.emergency_relevance >= threshold],
            key=lambda s: s.emergency_relevance, reverse=True
        )

    def schemas_for_primitive(self, primitive: Primitive) -> list[ImageSchema]:
        names = self._primitive_index.get(primitive, [])
        return [self._schemas[n] for n in names]

    def instantiate(self, schema_name: str, context: dict) -> dict:
        """
        Instantiate a schema for a specific context.
        Returns the AR/haptic output instructions.
        context: {location, direction, distance_m, stress_level, ...}
        """
        schema = self.get(schema_name)
        if not schema:
            return {"error": f"Unknown schema: {schema_name}"}

        output = {
            "schema": schema_name,
            "ar_overlay": schema.ar_output,
            "haptic": schema.haptic_pattern,
            "primitives": [p.label for p in schema.primitives],
            "context": context,
            "m_level": "M0",
        }

        # Context-specific AR parameterisation
        if "direction" in context:
            output["ar_direction_deg"] = context["direction"]
        if "distance_m" in context:
            output["ar_scale"] = min(1.0, 1.0 / max(0.5, context["distance_m"]))
        if "stress_level" in context:
            # Higher stress → stronger AR signal
            sl = context["stress_level"]
            output["ar_intensity"] = 0.6 + sl * 0.4
            output["haptic_intensity"] = 0.5 + sl * 0.5

        return output

    def visual_cliff_case(self) -> dict:
        """
        The paradigm case: visual cliff.
        FALLING_DANGER schema instantiation.
        Demonstrates M0 in action.
        """
        return self.instantiate("FALLING_DANGER", {
            "location": "floor_boundary",
            "direction": 180,   # toward drop
            "distance_m": 0.3,
            "stress_level": 0.7,
            "biological_reference": "Gibson & Walk (1960)",
            "cross_species": ["infant", "kitten", "chick", "lamb", "rat"],
        })

    def shinjuku_case(self) -> dict:
        """
        The Shinjuku emergency case from the TAAA working paper.
        American in Tokyo fire: wrong schema (exit direction) activated.
        M0 intervention: SAFE_PATH + STOP schemas.
        """
        return {
            "scenario": "Shinjuku station fire",
            "subject_profile": {"culture": "US", "schema_risk": "spatial_orientation"},
            "interference_detected": {
                "schema": "SAFE_PATH",
                "wrong_direction": True,
                "predicted_action": "turn_toward_wrong_exit",
                "interference_type": "active",
            },
            "m0_interventions": [
                self.instantiate("STOP", {
                    "direction": 270,  # wrong direction
                    "stress_level": 0.85,
                    "timing": "pre_action_50ms",
                }),
                self.instantiate("SAFE_PATH", {
                    "direction": 45,   # correct direction
                    "distance_m": 8.0,
                    "stress_level": 0.85,
                    "timing": "post_stop_200ms",
                }),
            ],
            "communication_channel": "M0_ONLY",
            "cultural_translation": "NONE_REQUIRED",
            "note": "M0 bypasses cultural schema processing entirely.",
        }

    def summary(self) -> dict:
        return {
            "total_schemas": len(self._schemas),
            "emergency_subset_count": len(self.emergency_subset()),
            "primitive_coverage": len(self._primitive_index),
            "schemas": [
                {"name": s.name, "emergency_relevance": s.emergency_relevance,
                 "primitives": len(s.primitives)}
                for s in sorted(self._schemas.values(),
                                key=lambda x: x.emergency_relevance, reverse=True)
            ]
        }


# Singleton — M0 is loaded once at system start
M0 = M0Registry()
