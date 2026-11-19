"""Structured output contracts for the review team and generated tests."""

from typing import Literal

from pydantic import BaseModel, Field


class ReviewFinding(BaseModel):
    severity: Literal["high", "medium", "low"]
    category: str
    message: str
    line: int | None = None
    suggestion: str


class GeneratedTest(BaseModel):
    name: str
    assertion: str = Field(description="Python assertion to run after the submitted module")
    purpose: str


class TeamReview(BaseModel):
    summary: str
    findings: list[ReviewFinding]
    coaching: str
    corrected_code: str
    tests: list[GeneratedTest]
