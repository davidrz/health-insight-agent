"""
Pydantic schemas for API request/response validation and serialization.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator
from enum import Enum

from app.domain.entities import (
    VitalType, LabResultType, SeverityLevel, RiskLevel
)
from app.domain.value_objects import (
    InsightType, RecommendationType, RecommendationPriority
)


# Base schemas
class BaseResponse(BaseModel):
    """Base response model with common fields"""
    success: bool = True
    message: str = "Operation completed successfully"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Authentication schemas
class TokenRequest(BaseModel):
    """JWT token request schema"""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT token response schema"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# Health data schemas
class VitalSignsSchema(BaseModel):
    """Schema for vital signs data"""
    heart_rate: Optional[int] = Field(None, ge=40, le=200, description="Heart rate in BPM")
    blood_pressure_systolic: Optional[int] = Field(None, ge=70, le=250, description="Systolic BP in mmHg")
    blood_pressure_diastolic: Optional[int] = Field(None, ge=40, le=150, description="Diastolic BP in mmHg")
    temperature: Optional[float] = Field(None, ge=35.0, le=42.0, description="Temperature in Celsius")
    respiratory_rate: Optional[int] = Field(None, ge=8, le=40, description="Respiratory rate per minute")
    oxygen_saturation: Optional[float] = Field(None, ge=70.0, le=100.0, description="Oxygen saturation percentage")
    measured_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LabResultSchema(BaseModel):
    """Schema for laboratory test results"""
    test_type: LabResultType
    value: float = Field(..., ge=0, description="Test result value")
    unit: str = Field(..., min_length=1, max_length=20)
    reference_range_min: Optional[float] = Field(None, ge=0)
    reference_range_max: Optional[float] = Field(None, ge=0)
    tested_at: Optional[datetime] = None
    lab_name: Optional[str] = Field(None, max_length=100)

    @validator('reference_range_max')
    def validate_reference_range(cls, v, values):
        if v is not None and 'reference_range_min' in values and values['reference_range_min'] is not None:
            if v <= values['reference_range_min']:
                raise ValueError('Reference range maximum must be greater than minimum')
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SymptomSchema(BaseModel):
    """Schema for patient symptoms"""
    name: str = Field(..., min_length=1, max_length=100)
    severity: SeverityLevel
    duration_days: Optional[int] = Field(None, ge=0, description="Duration in days")
    description: Optional[str] = Field(None, max_length=500)
    reported_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MedicalHistorySchema(BaseModel):
    """Schema for medical history"""
    conditions: List[str] = Field(default_factory=list, description="Medical conditions")
    medications: List[str] = Field(default_factory=list, description="Current medications")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")
    surgeries: List[str] = Field(default_factory=list, description="Previous surgeries")
    family_history: List[str] = Field(default_factory=list, description="Family medical history")
    last_updated: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthDataRequest(BaseModel):
    """Schema for health data upload request"""
    patient_id: str = Field(..., min_length=1, max_length=100)
    vitals: Optional[VitalSignsSchema] = None
    lab_results: List[LabResultSchema] = Field(default_factory=list)
    symptoms: List[SymptomSchema] = Field(default_factory=list)
    medical_history: Optional[MedicalHistorySchema] = None

    @validator('patient_id')
    def validate_patient_id(cls, v):
        if not v.strip():
            raise ValueError('Patient ID cannot be empty or whitespace')
        return v.strip()


class HealthDataResponse(BaseResponse):
    """Schema for health data upload response"""
    data_id: UUID
    patient_id: str
    timestamp: datetime


# Insight and analysis schemas
class HealthInsightSchema(BaseModel):
    """Schema for health insights"""
    insight_type: InsightType
    title: str
    description: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    supporting_data: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RiskFactorSchema(BaseModel):
    """Schema for risk factors"""
    name: str
    risk_level: RiskLevel
    probability: float = Field(..., ge=0.0, le=1.0)
    contributing_factors: List[str] = Field(default_factory=list)
    mitigation_strategies: List[str] = Field(default_factory=list)


class RiskAssessmentSchema(BaseModel):
    """Schema for risk assessment"""
    overall_risk_level: RiskLevel
    risk_factors: List[RiskFactorSchema] = Field(default_factory=list)
    assessment_summary: str = ""
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    assessed_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RecommendationSchema(BaseModel):
    """Schema for health recommendations"""
    recommendation_type: RecommendationType
    priority: RecommendationPriority
    title: str
    description: str
    rationale: str
    expected_outcome: Optional[str] = None
    timeframe: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class InsightReportSchema(BaseModel):
    """Schema for complete insight reports"""
    report_id: UUID
    patient_id: str
    insights: List[HealthInsightSchema] = Field(default_factory=list)
    risk_assessment: Optional[RiskAssessmentSchema] = None
    recommendations: List[RecommendationSchema] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    generated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class InsightReportResponse(BaseResponse):
    """Schema for insight report response"""
    report: InsightReportSchema


class InsightReportsListResponse(BaseResponse):
    """Schema for list of insight reports"""
    reports: List[InsightReportSchema]
    total_count: int
    page: int = 1
    page_size: int = 10


# Analysis request schemas
class AnalysisRequest(BaseModel):
    """Schema for health data analysis request"""
    patient_id: str = Field(..., min_length=1, max_length=100)
    include_risk_assessment: bool = True
    include_recommendations: bool = True
    analysis_type: Optional[str] = Field(None, description="Specific analysis type to perform")

    @validator('patient_id')
    def validate_patient_id(cls, v):
        if not v.strip():
            raise ValueError('Patient ID cannot be empty or whitespace')
        return v.strip()


class AnalysisResponse(BaseResponse):
    """Schema for analysis response"""
    analysis_id: UUID
    patient_id: str
    status: str = "completed"
    report: Optional[InsightReportSchema] = None


# Dashboard schemas
class HealthMetricSummary(BaseModel):
    """Schema for health metric summary"""
    metric_name: str
    current_value: Optional[float] = None
    trend: str = "stable"  # "improving", "declining", "stable"
    last_updated: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TimeSeriesDataPoint(BaseModel):
    """Schema for time series data point"""
    timestamp: str
    value: float
    unit: Optional[str] = None
    reference_range: Optional[Dict[str, Optional[float]]] = None


class TimeSeriesData(BaseModel):
    """Schema for time series data"""
    type: str
    data: Dict[str, List[TimeSeriesDataPoint]]
    metadata: Dict[str, Any]


class RiskDistributionData(BaseModel):
    """Schema for risk distribution data"""
    type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class DashboardData(BaseModel):
    """Schema for dashboard data"""
    patient_id: str
    health_metrics: List[HealthMetricSummary]
    recent_insights: List[HealthInsightSchema]
    urgent_recommendations: List[RecommendationSchema]
    overall_health_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    last_analysis_date: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DashboardResponse(BaseResponse):
    """Schema for dashboard response"""
    dashboard: DashboardData


class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime
    message_id: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebSocketConnectionStats(BaseModel):
    """Schema for WebSocket connection statistics"""
    total_connections: int
    patient_subscriptions: int
    topic_subscriptions: int
    active_patients: List[str]
    active_topics: List[str]


# Pagination schemas
class PaginationParams(BaseModel):
    """Schema for pagination parameters"""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


# Health check schemas
class HealthCheckResponse(BaseModel):
    """Enhanced health check response"""
    status: str
    version: str
    app_name: str
    timestamp: datetime
    services: Dict[str, str] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }