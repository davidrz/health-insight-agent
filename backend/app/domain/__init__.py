"""
Health Insight Agent Domain Layer

This package contains the core domain logic including entities, value objects,
repository interfaces, and domain services following Clean Architecture principles.
"""

from .entities import (
    HealthData,
    VitalSigns,
    LabResult,
    Symptom,
    MedicalHistory,
    VitalType,
    LabResultType,
    SeverityLevel,
    RiskLevel
)

from .value_objects import (
    HealthInsight,
    RiskFactor,
    RiskAssessment,
    Recommendation,
    InsightReport,
    InsightType,
    RecommendationType,
    RecommendationPriority
)

from .repositories import (
    HealthDataRepository,
    InsightReportRepository,
    PatientRepository,
    RepositoryError,
    NotFoundError,
    DuplicateError,
    ValidationError
)

from .services import (
    HealthDataValidationService,
    VitalSignsAnalysisService,
    RiskAssessmentService,
    RecommendationService
)

__all__ = [
    # Entities
    "HealthData",
    "VitalSigns", 
    "LabResult",
    "Symptom",
    "MedicalHistory",
    "VitalType",
    "LabResultType",
    "SeverityLevel",
    "RiskLevel",
    
    # Value Objects
    "HealthInsight",
    "RiskFactor",
    "RiskAssessment", 
    "Recommendation",
    "InsightReport",
    "InsightType",
    "RecommendationType",
    "RecommendationPriority",
    
    # Repository Interfaces
    "HealthDataRepository",
    "InsightReportRepository",
    "PatientRepository",
    "RepositoryError",
    "NotFoundError",
    "DuplicateError",
    "ValidationError",
    
    # Domain Services
    "HealthDataValidationService",
    "VitalSignsAnalysisService",
    "RiskAssessmentService",
    "RecommendationService"
]