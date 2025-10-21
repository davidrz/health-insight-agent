"""
Dashboard endpoints for the Health Insight Agent API.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    DashboardResponse, DashboardData, HealthMetricSummary,
    ErrorResponse
)
from app.api.auth import get_current_active_user, User
from app.infra.database import get_db_session
from app.infra.repositories import HealthDataRepository, InsightReportRepository
from app.domain.entities import HealthData, VitalSigns
from app.domain.value_objects import InsightReport, RecommendationPriority


router = APIRouter()


@router.get(
    "/dashboard/{patient_id}",
    response_model=DashboardResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Patient data not found"}
    },
    summary="Get dashboard data",
    description="Retrieve comprehensive dashboard data for a patient including metrics, insights, and recommendations"
)
async def get_dashboard_data(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve comprehensive dashboard data for a patient.
    
    - **patient_id**: Unique identifier for the patient
    
    Returns dashboard data including:
    - Current health metrics and trends
    - Recent insights with high confidence
    - Urgent recommendations requiring attention
    - Overall health score
    - Last analysis date
    """
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own dashboard"
        )
    
    try:
        # Get repositories
        health_repo = HealthDataRepository(db)
        insight_repo = InsightReportRepository(db)
        
        # Get recent health data for metrics
        recent_health_data = await health_repo.get_by_patient_id(
            patient_id, limit=10, offset=0
        )
        
        if not recent_health_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No health data found for this patient"
            )
        
        # Get latest insights
        latest_insights = await insight_repo.get_by_patient_id_paginated(
            patient_id=patient_id,
            limit=5,
            offset=0,
            min_confidence=0.7  # Only high confidence insights for dashboard
        )
        
        # Build dashboard data
        dashboard_data = await _build_dashboard_data(
            patient_id=patient_id,
            health_data_list=recent_health_data,
            insight_reports=latest_insights[0] if latest_insights else []
        )
        
        return DashboardResponse(
            dashboard=dashboard_data,
            message="Dashboard data retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard data"
        )


async def _build_dashboard_data(
    patient_id: str,
    health_data_list: List[HealthData],
    insight_reports: List[InsightReport]
) -> DashboardData:
    """Build dashboard data from health records and insights"""
    from app.api.schemas import HealthInsightSchema, RecommendationSchema
    
    # Calculate health metrics summaries
    health_metrics = _calculate_health_metrics(health_data_list)
    
    # Get recent high-confidence insights
    recent_insights = []
    urgent_recommendations = []
    last_analysis_date = None
    overall_health_score = None
    
    if insight_reports:
        # Get the most recent report
        latest_report = insight_reports[0]
        last_analysis_date = latest_report.generated_at
        
        # Calculate overall health score based on risk assessment
        if latest_report.risk_assessment:
            overall_health_score = _calculate_health_score(latest_report.risk_assessment)
        
        # Collect recent insights (high confidence only)
        for report in insight_reports[:3]:  # Last 3 reports
            for insight in report.high_confidence_insights:
                recent_insights.append(
                    HealthInsightSchema(
                        insight_type=insight.insight_type,
                        title=insight.title,
                        description=insight.description,
                        confidence_score=insight.confidence_score,
                        supporting_data=insight.supporting_data,
                        generated_at=insight.generated_at
                    )
                )
        
        # Collect urgent recommendations
        for report in insight_reports:
            for rec in report.urgent_recommendations:
                urgent_recommendations.append(
                    RecommendationSchema(
                        recommendation_type=rec.recommendation_type,
                        priority=rec.priority,
                        title=rec.title,
                        description=rec.description,
                        rationale=rec.rationale,
                        expected_outcome=rec.expected_outcome,
                        timeframe=rec.timeframe,
                        created_at=rec.created_at
                    )
                )
    
    return DashboardData(
        patient_id=patient_id,
        health_metrics=health_metrics,
        recent_insights=recent_insights[:5],  # Limit to 5 most recent
        urgent_recommendations=urgent_recommendations[:3],  # Limit to 3 most urgent
        overall_health_score=overall_health_score,
        last_analysis_date=last_analysis_date
    )


def _calculate_health_metrics(health_data_list: List[HealthData]) -> List[HealthMetricSummary]:
    """Calculate health metric summaries from recent health data"""
    if not health_data_list:
        return []
    
    metrics = []
    
    # Get latest vitals for current values
    latest_data = health_data_list[0]
    if latest_data.vitals:
        vitals = latest_data.vitals
        
        # Heart rate metric
        if vitals.heart_rate is not None:
            trend = _calculate_trend([
                data.vitals.heart_rate for data in health_data_list 
                if data.vitals and data.vitals.heart_rate is not None
            ])
            metrics.append(HealthMetricSummary(
                metric_name="Heart Rate",
                current_value=float(vitals.heart_rate),
                trend=trend,
                last_updated=vitals.measured_at
            ))
        
        # Blood pressure systolic
        if vitals.blood_pressure_systolic is not None:
            trend = _calculate_trend([
                data.vitals.blood_pressure_systolic for data in health_data_list 
                if data.vitals and data.vitals.blood_pressure_systolic is not None
            ])
            metrics.append(HealthMetricSummary(
                metric_name="Blood Pressure (Systolic)",
                current_value=float(vitals.blood_pressure_systolic),
                trend=trend,
                last_updated=vitals.measured_at
            ))
        
        # Temperature
        if vitals.temperature is not None:
            trend = _calculate_trend([
                data.vitals.temperature for data in health_data_list 
                if data.vitals and data.vitals.temperature is not None
            ])
            metrics.append(HealthMetricSummary(
                metric_name="Temperature",
                current_value=vitals.temperature,
                trend=trend,
                last_updated=vitals.measured_at
            ))
    
    return metrics


def _calculate_trend(values: List[float]) -> str:
    """Calculate trend from a list of values"""
    if len(values) < 2:
        return "stable"
    
    # Simple trend calculation - compare first and last values
    first_val = values[-1]  # Most recent (first in list)
    last_val = values[0]    # Oldest
    
    change_percent = ((first_val - last_val) / last_val) * 100 if last_val != 0 else 0
    
    if change_percent > 5:
        return "improving" if first_val > last_val else "declining"
    elif change_percent < -5:
        return "declining" if first_val < last_val else "improving"
    else:
        return "stable"


def _calculate_health_score(risk_assessment) -> float:
    """Calculate overall health score from risk assessment"""
    from app.domain.entities import RiskLevel
    
    # Base score starts at 100
    base_score = 100.0
    
    # Deduct points based on overall risk level
    risk_deductions = {
        RiskLevel.LOW: 0,
        RiskLevel.MODERATE: 15,
        RiskLevel.HIGH: 35,
        RiskLevel.VERY_HIGH: 60
    }
    
    score = base_score - risk_deductions.get(risk_assessment.overall_risk_level, 0)
    
    # Additional deductions for high-risk factors
    high_risk_factors = len(risk_assessment.high_risk_factors)
    score -= high_risk_factors * 10
    
    # Apply confidence factor
    score *= risk_assessment.confidence_score
    
    # Ensure score is between 0 and 100
    return max(0.0, min(100.0, score))