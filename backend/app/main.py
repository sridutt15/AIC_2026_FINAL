"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    health,
    ingestion,
    profiling,
    semantic_contract,
    data_quality,
    canonical_model,
    kpi,
    anomaly,
    drivers,
    evidence,
    persona,
    insights,
    recommendations,
    telemetry,
    feedback,
)
from app.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="KPI Intelligence-to-Action Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(profiling.router)
app.include_router(semantic_contract.router)
app.include_router(data_quality.router)
app.include_router(canonical_model.router)
app.include_router(kpi.router)
app.include_router(anomaly.router)
app.include_router(drivers.router)
app.include_router(evidence.router)
app.include_router(persona.router)
app.include_router(insights.router)
app.include_router(recommendations.router)
app.include_router(telemetry.router)
app.include_router(feedback.router)
