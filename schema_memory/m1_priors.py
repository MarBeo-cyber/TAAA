"""
TAAA — Schema Memory Layer M1: Cultural / Professional Priors

M1 contains statistical distributions of cognitive schemas across
cultural and professional communities. It is the Bayesian prior
used before any individual M2 data is available.

Sources: Nisbett (2003), Hall (1976, 1983), Boroditsky (2001),
         Kahneman (2011), cross-cultural psychology literature.

M1 is NOT the model of the person. It is the starting point.
It converges toward M2 (personal schema topology) over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CulturalSchemaProfile:
    """Statistical schema tendencies for a cultural/professional community."""
    community_id: str
    label: str

    # Temporal schema (Hall 1976, Boroditsky 2001)
    time_structure: str          # "linear_continuous" | "episodic" | "mixed"
    time_orientation: str        # "future_focused" | "present_focused" | "past_focused"
    deadline_ontology: str       # "point_on_line" | "episode_end" | "relational"

    # Reasoning schema (Nisbett 2003)
    reasoning_style: str         # "analytic" | "holistic" | "mixed"
    causality_model: str         # "linear_causal" | "relational" | "network"
    contradiction_handling: str  # "resolve" | "tolerate" | "use_as_engine"

    # Communication schema (Hall 1976)
    context_level: str           # "low_context" | "high_context"
    silence_meaning: str         # "absence" | "response" | "respect" | "variable"
    directness: str              # "direct" | "indirect" | "layered"

    # Spatial schema
    spatial_orientation: str     # "landmark" | "cardinal" | "body_relative"
    personal_space_m: float      # typical comfortable distance

    # Epistemological schema
    knowledge_validation: str    # "method_first" | "result_first" | "authority"
    question_as_answer: bool     # Is posing a question a valid answer?

    # Risk schema
    risk_tolerance: str          # "high" | "medium" | "low"
    uncertainty_handling: str    # "eliminate" | "navigate" | "embrace"

    # Interference risk contexts (where M1 priors are likely to produce errors)
    high_interference_contexts: list[str] = field(default_factory=list)


# ── M1 Prior Database ─────────────────────────────────────────────────────────
# Statistical tendencies, NOT stereotypes.
# Used as Bayesian prior, immediately updated by individual evidence.
# Individual variation within any community is enormous.

M1_PRIORS: dict[str, CulturalSchemaProfile] = {

    "western_northern_european": CulturalSchemaProfile(
        community_id="western_northern_european",
        label="Western Northern European",
        time_structure="linear_continuous",
        time_orientation="future_focused",
        deadline_ontology="point_on_line",
        reasoning_style="analytic",
        causality_model="linear_causal",
        contradiction_handling="resolve",
        context_level="low_context",
        silence_meaning="absence",
        directness="direct",
        spatial_orientation="cardinal",
        personal_space_m=1.2,
        knowledge_validation="method_first",
        question_as_answer=False,
        risk_tolerance="medium",
        uncertainty_handling="eliminate",
        high_interference_contexts=[
            "polychronic_environment",
            "high_context_communication",
            "episodic_time_culture",
            "indirect_communication",
        ],
    ),

    "east_asian": CulturalSchemaProfile(
        community_id="east_asian",
        label="East Asian (China, Japan, Korea)",
        time_structure="mixed",
        time_orientation="past_present_balanced",
        deadline_ontology="relational",
        reasoning_style="holistic",
        causality_model="network",
        contradiction_handling="tolerate",
        context_level="high_context",
        silence_meaning="respect",
        directness="indirect",
        spatial_orientation="landmark",
        personal_space_m=0.9,
        knowledge_validation="result_first",
        question_as_answer=False,
        risk_tolerance="low",
        uncertainty_handling="navigate",
        high_interference_contexts=[
            "low_context_communication",
            "linear_time_environment",
            "direct_communication",
            "western_signage_systems",
        ],
    ),

    "middle_eastern": CulturalSchemaProfile(
        community_id="middle_eastern",
        label="Middle Eastern / Arabic",
        time_structure="episodic",
        time_orientation="present_focused",
        deadline_ontology="episode_end",
        reasoning_style="holistic",
        causality_model="relational",
        contradiction_handling="tolerate",
        context_level="high_context",
        silence_meaning="variable",
        directness="layered",
        spatial_orientation="landmark",
        personal_space_m=0.7,
        knowledge_validation="authority",
        question_as_answer=False,
        risk_tolerance="medium",
        uncertainty_handling="navigate",
        high_interference_contexts=[
            "monochronic_scheduling",
            "low_context_communication",
            "linear_deadline_culture",
        ],
    ),

    "talmudic_academic": CulturalSchemaProfile(
        community_id="talmudic_academic",
        label="Talmudic / Dialectical Academic",
        time_structure="linear_continuous",
        time_orientation="mixed",
        deadline_ontology="point_on_line",
        reasoning_style="dialectical",
        causality_model="network",
        contradiction_handling="use_as_engine",
        context_level="medium_context",
        silence_meaning="thought",
        directness="layered",
        spatial_orientation="cardinal",
        personal_space_m=1.0,
        knowledge_validation="method_first",
        question_as_answer=True,    # KEY: question IS a valid response
        risk_tolerance="medium",
        uncertainty_handling="navigate",
        high_interference_contexts=[
            "question_as_evasion_culture",
            "resolution_seeking_environment",
        ],
    ),

    "sub_saharan_african": CulturalSchemaProfile(
        community_id="sub_saharan_african",
        label="Sub-Saharan African (diverse)",
        time_structure="episodic",
        time_orientation="present_focused",
        deadline_ontology="episode_end",
        reasoning_style="holistic",
        causality_model="relational",
        contradiction_handling="tolerate",
        context_level="high_context",
        silence_meaning="respect",
        directness="indirect",
        spatial_orientation="landmark",
        personal_space_m=0.8,
        knowledge_validation="authority",
        question_as_answer=False,
        risk_tolerance="medium",
        uncertainty_handling="embrace",
        high_interference_contexts=[
            "monochronic_project_management",
            "linear_deadline_culture",
            "low_context_communication",
        ],
    ),

    "biomedical_professional": CulturalSchemaProfile(
        community_id="biomedical_professional",
        label="Biomedical Professional",
        time_structure="linear_continuous",
        time_orientation="future_focused",
        deadline_ontology="point_on_line",
        reasoning_style="analytic",
        causality_model="linear_causal",
        contradiction_handling="resolve",
        context_level="low_context",
        silence_meaning="absence",
        directness="direct",
        spatial_orientation="cardinal",
        personal_space_m=1.1,
        knowledge_validation="method_first",
        question_as_answer=False,
        risk_tolerance="low",
        uncertainty_handling="eliminate",
        high_interference_contexts=[
            "traditional_medicine_terminology",
            "patient_folk_illness_narrative",
            "high_context_patient_communication",
        ],
    ),

    "civil_engineering": CulturalSchemaProfile(
        community_id="civil_engineering",
        label="Civil / Structural Engineering",
        time_structure="linear_continuous",
        time_orientation="future_focused",
        deadline_ontology="point_on_line",
        reasoning_style="analytic",
        causality_model="linear_causal",
        contradiction_handling="resolve",
        context_level="low_context",
        silence_meaning="absence",
        directness="direct",
        spatial_orientation="cardinal",
        personal_space_m=1.2,
        knowledge_validation="method_first",
        question_as_answer=False,
        risk_tolerance="low",
        uncertainty_handling="eliminate",
        high_interference_contexts=[
            "it_system_terminology",
            "clinical_domain_vocabulary",
            "digital_infrastructure_concepts",
        ],
    ),
}


class M1Registry:
    """Manages cultural/professional prior profiles."""

    def __init__(self):
        self._profiles = M1_PRIORS
        self._profession_map = {
            "doctor": "biomedical_professional",
            "nurse": "biomedical_professional",
            "engineer_civil": "civil_engineering",
            "engineer_structural": "civil_engineering",
        }

    def get(self, community_id: str) -> Optional[CulturalSchemaProfile]:
        return self._profiles.get(community_id)

    def get_by_profession(self, profession: str) -> Optional[CulturalSchemaProfile]:
        cid = self._profession_map.get(profession.lower())
        return self._profiles.get(cid) if cid else None

    # Dimensions copied into the prior, and the source weights.
    PRIOR_DIMENSIONS = [
        "time_structure", "reasoning_style", "context_level", "silence_meaning",
        "directness", "deadline_ontology", "question_as_answer",
        "spatial_orientation", "knowledge_validation",
    ]
    SOURCE_WEIGHTS = {"culture": 0.5, "profession": 0.4}

    def build_prior(self, culture: Optional[str] = None,
                    profession: Optional[str] = None,
                    age: Optional[int] = None,
                    context: Optional[str] = None) -> dict:
        """
        Build a composite M1 prior from the available dimensions.

        These are categorical dimensions ("high_context" vs "low_context"), not
        numbers: there is no meaningful arithmetic mean of two of them. So the
        blend is per-dimension and explicit:

          - both sources agree  → the agreed value, source "culture+profession"
          - they disagree       → the higher-weighted source wins (culture 0.5
                                  beats profession 0.4) AND the loser's value is
                                  recorded in `contested_dimensions`
          - only one source     → that source

        The previous version sorted by weight, took the single winner for every
        dimension, and still advertised `profiles_used: ["culture","profession"]`.
        The profession profile never contributed anything. `dimension_sources`
        below now says, per dimension, which profile the value came from.

        This is the Bayesian prior — immediately updated by M2 evidence.
        """
        sources: dict[str, CulturalSchemaProfile] = {}
        if culture and culture in self._profiles:
            sources["culture"] = self._profiles[culture]
        if profession:
            prof_profile = self.get_by_profession(profession)
            if prof_profile:
                sources["profession"] = prof_profile

        if not sources:
            # No prior available — fall back to M0 only
            return {
                "m_level": "M0",
                "prior_available": False,
                "note": "No M1 prior for this profile. Operating on M0 only.",
            }

        ranked = sorted(sources.items(),
                        key=lambda kv: self.SOURCE_WEIGHTS[kv[0]], reverse=True)

        prior: dict = {
            "m_level": "M1",
            "prior_available": True,
            "profiles_used": [name for name, _ in ranked],
            "source_communities": {n: p.community_id for n, p in ranked},
            "source_weights": {n: self.SOURCE_WEIGHTS[n] for n, _ in ranked},
        }
        dimension_sources: dict[str, str] = {}
        contested: dict[str, dict] = {}

        for dim in self.PRIOR_DIMENSIONS:
            values = {name: getattr(p, dim) for name, p in ranked}
            winner_name, winner_profile = ranked[0]
            prior[dim] = getattr(winner_profile, dim)
            distinct = {v for v in values.values()}
            if len(distinct) == 1:
                dimension_sources[dim] = "+".join(values)
            else:
                dimension_sources[dim] = winner_name
                contested[dim] = values

        # Union: a context is high-interference if ANY source says so. Dropping
        # the profession's contexts here is how a doctor's clinical interference
        # contexts used to vanish behind their cultural profile.
        merged_contexts: list[str] = []
        for _, p in ranked:
            for ctx in p.high_interference_contexts:
                if ctx not in merged_contexts:
                    merged_contexts.append(ctx)

        prior["high_interference_contexts"] = merged_contexts
        prior["dimension_sources"] = dimension_sources
        prior["contested_dimensions"] = contested
        prior["note"] = ("Bayesian prior — update immediately with individual "
                         "evidence. Categorical dimensions are resolved by "
                         "source weight, not averaged; see contested_dimensions.")
        return prior

    def interference_risk(self, subject_profile_id: str,
                          environment_profile_id: str) -> dict:
        """
        Estimate interference risk between two schema profiles.
        High risk = high probability of active wrong schema activation.
        """
        subject = self.get(subject_profile_id)
        environment = self.get(environment_profile_id)
        if not subject or not environment:
            return {"risk": "unknown", "score": 0.5}

        conflicts = []
        if subject.time_structure != environment.time_structure:
            conflicts.append("temporal_schema_mismatch")
        if subject.reasoning_style != environment.reasoning_style:
            conflicts.append("reasoning_style_mismatch")
        if subject.context_level != environment.context_level:
            conflicts.append("context_level_mismatch")
        if subject.silence_meaning != environment.silence_meaning:
            conflicts.append("silence_interpretation_conflict")
        if subject.directness != environment.directness:
            conflicts.append("communication_style_conflict")
        if subject.question_as_answer != environment.question_as_answer:
            conflicts.append("epistemic_schema_conflict")

        score = len(conflicts) / 6.0
        return {
            "subject": subject_profile_id,
            "environment": environment_profile_id,
            "risk": "high" if score > 0.6 else "medium" if score > 0.3 else "low",
            "score": round(score, 2),
            "conflict_dimensions": conflicts,
            "note": "High score = high interference probability (not ignorance).",
        }


M1 = M1Registry()
