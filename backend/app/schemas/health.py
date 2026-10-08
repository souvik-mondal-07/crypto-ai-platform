"""Pydantic response models for health / root endpoints."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for GET /api/v1/health."""

    status: str = Field(..., examples=["ok", "degraded"])
    service: str = Field(..., examples=["crypto-ai-platform-backend"])
    database: str = Field(..., examples=["connected", "disconnected"])


class RootResponse(BaseModel):
    """Response model for GET /."""

    message: str = Field(..., examples=["Crypto AI Platform API"])
    version: str = Field(..., examples=["1.0.0"])
