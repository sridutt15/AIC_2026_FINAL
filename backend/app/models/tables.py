"""SQLAlchemy models — a direct translation of the Phases 0–11 schema.

Same tables, same columns, same meaning as the original raw CREATE TABLE
strings; the only change is that they are now SQLAlchemy models backed by
Postgres (Supabase) instead of SQLite DDL. Tables without a PRIMARY KEY
in the original schema (profiles, anomalies, stage_timings) are declared
as plain Table objects — ORM classes require a primary key, so those
three are not ORM-mapped; this is a translation, not a redesign.
"""

from sqlalchemy import Column, Float, Integer, Table, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Source(Base):
    __tablename__ = "sources"

    source_id = Column(Text, primary_key=True)
    filename = Column(Text)
    grain = Column(Text)
    cadence = Column(Text)
    uploaded_at = Column(Text)


# profiles/anomalies/stage_timings have no PRIMARY KEY in the original schema;
# ORM classes require one, so these three are declared as plain Table objects
# (same DDL, just not ORM-mapped). create_all() still creates them.
profiles_table = Table(
    "profiles",
    Base.metadata,
    Column("source_id", Text),
    Column("profile_json", Text),
    Column("created_at", Text),
)

anomalies_table = Table(
    "anomalies",
    Base.metadata,
    Column("kpi_id", Text),
    Column("anomaly_json", Text),
    Column("detected_at", Text),
)

stage_timings_table = Table(
    "stage_timings",
    Base.metadata,
    Column("stage", Text),
    Column("latency_ms", Integer),
    Column("recorded_at", Text),
)


class SemanticContract(Base):
    __tablename__ = "semantic_contracts"

    source_id = Column(Text, primary_key=True)
    contract_json = Column(Text)
    updated_at = Column(Text)


class QualityReport(Base):
    __tablename__ = "quality_reports"

    source_id = Column(Text, primary_key=True)
    report_json = Column(Text)
    created_at = Column(Text)


class CanonicalDataset(Base):
    __tablename__ = "canonical_datasets"

    dataset_id = Column(Text, primary_key=True)
    source_ids = Column(Text)
    join_config_json = Column(Text)
    created_at = Column(Text)


class Kpi(Base):
    __tablename__ = "kpis"

    kpi_id = Column(Text, primary_key=True)
    dataset_id = Column(Text)
    definition_json = Column(Text)
    status = Column(Text)


class KpiComputation(Base):
    __tablename__ = "kpi_computations"

    kpi_id = Column(Text, primary_key=True)
    computation_json = Column(Text)
    computed_at = Column(Text)


class Finding(Base):
    __tablename__ = "findings"

    finding_id = Column(Text, primary_key=True)
    kpi_id = Column(Text)
    finding_type = Column(Text)
    finding_json = Column(Text)
    evidence_json = Column(Text)
    created_at = Column(Text)


class Persona(Base):
    __tablename__ = "personas"

    persona_id = Column(Text, primary_key=True)
    name = Column(Text)
    access_json = Column(Text)


class Insight(Base):
    __tablename__ = "insights"

    insight_id = Column(Text, primary_key=True)
    kpi_id = Column(Text)
    persona_id = Column(Text)
    text = Column(Text)
    generated_at = Column(Text)


class RecommendationPackage(Base):
    __tablename__ = "recommendation_packages"

    package_id = Column(Text, primary_key=True)
    kpi_id = Column(Text)
    package_json = Column(Text)
    created_at = Column(Text)


class LlmCall(Base):
    __tablename__ = "llm_calls"

    call_id = Column(Text, primary_key=True)
    kpi_id = Column(Text)
    package_hash = Column(Text)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    latency_ms = Column(Integer)
    cost_usd = Column(Float)
    # SQLite's BOOLEAN has NUMERIC affinity — the app stores/reads 0|1 as
    # plain integers (tests insert raw 1/0 and compare `cached = 1`), so the
    # faithful Postgres translation is INTEGER, not BOOLEAN.
    cached = Column(Integer)
    created_at = Column(Text)


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id = Column(Text, primary_key=True)
    target_type = Column(Text)
    target_id = Column(Text)
    verdict = Column(Text)
    note = Column(Text)
    created_at = Column(Text)


# --- Phase 11 extension tables ------------------------------------------------


class DriverWeightAdjustment(Base):
    __tablename__ = "driver_weight_adjustments"

    driver_type = Column(Text, primary_key=True)
    multiplier = Column(Float)
    updated_at = Column(Text)


class FeedbackMeta(Base):
    __tablename__ = "feedback_meta"

    feedback_id = Column(Text, primary_key=True)
    driver_type = Column(Text)
    created_at = Column(Text)
