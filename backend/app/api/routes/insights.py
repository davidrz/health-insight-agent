"""
Health insights endpoints for the Health Insight Agent API.
"""

from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    InsightReportResponse, InsightReportsListResponse, ErrorResponse,
    PaginationParams
)
from app.api.auth import get_current_active_user, User
from app.infra.database import get_db_session
from app.infra.repositories import InsightReportRepository
from app.domain.value_objects import InsightReport


router = APIRouter()


@router.get(
    "/insights/{patient_id}",
    response_model=InsightReportsListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "No insights found"}
    },
    summary="Get patient insights",
    description="Retrieve health insight reports for a specific patient"
)
async def get_patient_insights(
    patient_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    include_low_confidence: bool = Query(False, description="Include low confidence insights"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve health insight reports for a patient.
    
    - **patient_id**: Unique identifier for the patient
    - **page**: Page number for pagination (starts from 1)
    - **page_size**: Number of reports per page (1-50)
    - **include_low_confidence**: Whether to include insights with confidence < 0.6
    
    Returns paginated list of insight reports ordered by generation date (newest first).
    """
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own insights"
        )
    
    try:
        insight_repo = InsightReportRepository(db)
        
        # Calculate offset for pagination
        offset = (page - 1) * page_size
        
        # Get insights with optional confidence filtering
        min_confidence = 0.0 if include_low_confidence else 0.6
        
        insights, total_count = await insight_repo.get_by_patient_id_paginated(
            patient_id=patient_id,
            limit=page_size,
            offset=offset,
            min_confidence=min_confidence
        )
        
        if not insights and page == 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No insights found for this patient"
            )
        
        # Convert to response schemas
        insight_schemas = [_convert_insight_to_schema(insight) for insight in insights]
        
        return InsightReportsListResponse(
            reports=insight_schemas,
            total_count=total_count,
            page=page,
            page_size=page_size,
            message=f"Retrieved {len(insights)} insight reports"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve insights"
        )


@router.get(
    "/insights/{patient_id}/latest",
    response_model=InsightReportResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "No insights found"}
    },
    summary="Get latest insights",
    description="Retrieve the most recent insight report for a patient"
)
async def get_latest_insights(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve the most recent insight report for a patient.
    
    - **patient_id**: Unique identifier for the patient
    
    Returns the latest insight report with all insights and recommendations.
    """
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own insights"
        )
    
    try:
        insight_repo = InsightReportRepository(db)
        latest_insight = await insight_repo.get_latest_by_patient_id(patient_id)
        
        if not latest_insight:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No insights found for this patient"
            )
        
        insight_schema = _convert_insight_to_schema(latest_insight)
        
        return InsightReportResponse(
            report=insight_schema,
            message="Latest insight report retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest insights"
        )


@router.get(
    "/insights/report/{report_id}",
    response_model=InsightReportResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Report not found"}
    },
    summary="Get insight report by ID",
    description="Retrieve a specific insight report by its ID"
)
async def get_insight_report(
    report_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve a specific insight report by its ID.
    
    - **report_id**: Unique identifier for the insight report
    
    Returns the complete insight report with all details.
    """
    try:
        insight_repo = InsightReportRepository(db)
        insight_report = await insight_repo.get_by_id(report_id)
        
        if not insight_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insight report not found"
            )
        
        # Validate patient access permissions
        if "patient" in current_user.roles and insight_report.patient_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patients can only access their own insight reports"
            )
        
        insight_schema = _convert_insight_to_schema(insight_report)
        
        return InsightReportResponse(
            report=insight_schema,
            message="Insight report retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve insight report"
        )


@router.get(
    "/insights/{patient_id}/urgent",
    response_model=InsightReportsListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"}
    },
    summary="Get urgent insights",
    description="Retrieve insight reports with urgent recommendations for a patient"
)
async def get_urgent_insights(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve insight reports containing urgent recommendations for a patient.
    
    - **patient_id**: Unique identifier for the patient
    
    Returns insight reports that contain urgent recommendations requiring immediate attention.
    """
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own insights"
        )
    
    try:
        insight_repo = InsightReportRepository(db)
        urgent_insights = await insight_repo.get_urgent_by_patient_id(patient_id)
        
        # Convert to response schemas
        insight_schemas = [_convert_insight_to_schema(insight) for insight in urgent_insights]
        
        return InsightReportsListResponse(
            reports=insight_schemas,
            total_count=len(insight_schemas),
            page=1,
            page_size=len(insight_schemas),
            message=f"Retrieved {len(urgent_insights)} urgent insight reports"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve urgent insights"
        )


def _convert_insight_to_schema(insight_report: InsightReport):
    """Convert domain InsightReport to API schema"""
    from app.api.schemas import (
        InsightReportSchema, HealthInsightSchema, RiskAssessmentSchema,
        RiskFactorSchema, RecommendationSchema
    )
    
    # Convert insights
    insights_schemas = [
        HealthInsightSchema(
            insight_type=insight.insight_type,
            title=insight.title,
            description=insight.description,
            confidence_score=insight.confidence_score,
            supporting_data=insight.supporting_data,
            generated_at=insight.generated_at
        )
        for insight in insight_report.insights
    ]
    
    # Convert risk assessment
    risk_assessment_schema = None
    if insight_report.risk_assessment:
        risk_factors_schemas = [
            RiskFactorSchema(
                name=factor.name,
                risk_level=factor.risk_level,
                probability=factor.probability,
                contributing_factors=factor.contributing_factors,
                mitigation_strategies=factor.mitigation_strategies
            )
            for factor in insight_report.risk_assessment.risk_factors
        ]
        
        risk_assessment_schema = RiskAssessmentSchema(
            overall_risk_level=insight_report.risk_assessment.overall_risk_level,
            risk_factors=risk_factors_schemas,
            assessment_summary=insight_report.risk_assessment.assessment_summary,
            confidence_score=insight_report.risk_assessment.confidence_score,
            assessed_at=insight_report.risk_assessment.assessed_at
        )
    
    # Convert recommendations
    recommendations_schemas = [
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
        for rec in insight_report.recommendations
    ]
    
    return InsightReportSchema(
        report_id=insight_report.report_id,
        patient_id=insight_report.patient_id,
        insights=insights_schemas,
        risk_assessment=risk_assessment_schema,
        recommendations=recommendations_schemas,
        confidence_score=insight_report.confidence_score,
        generated_at=insight_report.generated_at,
        metadata=insight_report.metadata
    )