"""
Infrastructure layer initialization.
"""

# Repository aliases for easier imports
from .repositories import (
    SQLAlchemyHealthDataRepository as HealthDataRepository,
    SQLAlchemyInsightReportRepository as InsightReportRepository,
    SQLAlchemyPatientRepository as PatientRepository
)

__all__ = [
    "HealthDataRepository",
    "InsightReportRepository", 
    "PatientRepository"
]