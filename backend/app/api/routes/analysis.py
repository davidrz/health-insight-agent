"""
Health analysis endpoints for the Health Insight Agent API.
"""

from uuid import UUID, uuid4
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AnalysisRequest, AnalysisResponse, ErrorResponse
)
from app.api.auth import get_current_active_user, User, require_roles
from app.infra.database import get_db_session
from app.infra import HealthDataRepository, InsightReportRepository
from app.agents.orchestrator import AgentOrchestrator
from app.domain.value_objects import InsightReport


router = APIRouter()


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid analysis request"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Patient data not found"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    },
    summary="Analyze health data",
    description="Trigger AI analysis of patient health data to generate insights and recommendations"
)
async def analyze_health_data(
    analysis_request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles(["healthcare_provider", "patient"])),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Analyze patient health data using AI agents to generate insights and recommendations.
    
    - **patient_id**: Unique identifier for the patient
    - **include_risk_assessment**: Whether to include risk assessment in analysis
    - **include_recommendations**: Whether to generate recommendations
    - **analysis_type**: Optional specific type of analysis to perform
    
    Returns analysis ID for tracking. Analysis runs in background and results are stored.
    """
    # Validate patient access permissions
    if "patient" in current_user.roles and analysis_request.patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only analyze their own health data"
        )
    
    try:
        # Check if patient has health data
        health_repo = HealthDataRepository(db)
        latest_health_data = await health_repo.get_latest_by_patient_id(analysis_request.patient_id)
        
        if not latest_health_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No health data found for this patient. Please upload health data first."
            )
        
        # Generate analysis ID
        analysis_id = uuid4()
        
        # Start background analysis
        background_tasks.add_task(
            _perform_health_analysis,
            analysis_id=analysis_id,
            patient_id=analysis_request.patient_id,
            include_risk_assessment=analysis_request.include_risk_assessment,
            include_recommendations=analysis_request.include_recommendations,
            analysis_type=analysis_request.analysis_type,
            db_session=db
        )
        
        return AnalysisResponse(
            analysis_id=analysis_id,
            patient_id=analysis_request.patient_id,
            status="processing",
            message="Health data analysis started. Results will be available shortly."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start health data analysis"
        )


@router.get(
    "/analyze/{analysis_id}/status",
    response_model=AnalysisResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        404: {"model": ErrorResponse, "description": "Analysis not found"}
    },
    summary="Get analysis status",
    description="Check the status of a health data analysis"
)
async def get_analysis_status(
    analysis_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Check the status of a health data analysis.
    
    - **analysis_id**: Unique identifier for the analysis
    
    Returns current status and results if analysis is complete.
    """
    try:
        # In a real implementation, you would track analysis status in database
        # For now, we'll check if an insight report exists for this analysis
        insight_repo = InsightReportRepository(db)
        
        # This is a simplified implementation - in production you'd have an analysis tracking table
        # For now, we'll assume analysis is complete if we can find recent insights
        # This is just for demonstration purposes
        
        return AnalysisResponse(
            analysis_id=analysis_id,
            patient_id="unknown",  # Would be tracked in real implementation
            status="completed",
            message="Analysis status check - this is a simplified implementation"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis status"
        )


async def _perform_health_analysis(
    analysis_id: UUID,
    patient_id: str,
    include_risk_assessment: bool,
    include_recommendations: bool,
    analysis_type: Optional[str],
    db_session: AsyncSession
):
    """
    Background task to perform health data analysis.
    
    This function orchestrates the AI analysis process and stores results.
    """
    try:
        # Get health data
        health_repo = HealthDataRepository(db_session)
        health_data = await health_repo.get_latest_by_patient_id(patient_id)
        
        if not health_data:
            # Log error - no health data found
            return
        
        # Initialize agent orchestrator
        orchestrator = AgentOrchestrator()
        
        # Perform analysis
        insight_report = await orchestrator.analyze_health_data(
            health_data=health_data,
            include_risk_assessment=include_risk_assessment,
            include_recommendations=include_recommendations,
            analysis_type=analysis_type
        )
        
        # Store results
        insight_repo = InsightReportRepository(db_session)
        await insight_repo.save(insight_report)
        
        # In a real implementation, you would also update analysis status in tracking table
        
    except Exception as e:
        # Log error and update analysis status to failed
        # In production, you would have proper error handling and status tracking
        pass