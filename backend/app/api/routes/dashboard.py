"""
Dashboard endpoints for the Health Insight Agent API.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    DashboardResponse, DashboardData, HealthMetricSummary,
    ErrorResponse, BaseResponse
)
from app.api.auth import get_current_active_user, User
from app.infra.database import get_db_session
from app.infra import HealthDataRepository, InsightReportRepository
from app.domain.entities import HealthData, VitalSigns
from app.domain.value_objects import InsightReport, RecommendationPriority
from app.services.dashboard_service import DashboardAggregationService, DashboardMetricsTransformer
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)
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
    force_refresh: bool = Query(False, description="Force refresh of cached data"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve comprehensive dashboard data for a patient.
    
    - **patient_id**: Unique identifier for the patient
    - **force_refresh**: Skip cache and force data refresh
    
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
        
        # Create dashboard service
        dashboard_service = DashboardAggregationService(health_repo, insight_repo)
        
        # Get dashboard data (with caching)
        dashboard_data = await dashboard_service.get_dashboard_data(
            patient_id, force_refresh=force_refresh
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


@router.get(
    "/dashboard/{patient_id}/time-series",
    response_model=BaseResponse,
    summary="Get time series data for dashboard charts",
    description="Retrieve time series data for visualization in dashboard charts"
)
async def get_dashboard_time_series(
    patient_id: str,
    metric_type: str = Query(..., description="Type of metrics: 'vitals' or 'labs'"),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get time series data for dashboard visualization."""
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own data"
        )
    
    try:
        health_repo = HealthDataRepository(db)
        
        # Get health data for the specified period
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        health_data_list = await health_repo.get_by_patient_id_and_date_range(
            patient_id, start_date, end_date
        )
        
        # Transform data for visualization
        time_series_data = DashboardMetricsTransformer.transform_time_series_data(
            health_data_list, metric_type, days
        )
        
        return BaseResponse(
            success=True,
            message="Time series data retrieved successfully",
            **{"data": time_series_data}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve time series data"
        )


@router.get(
    "/dashboard/{patient_id}/risk-distribution",
    response_model=BaseResponse,
    summary="Get risk distribution data",
    description="Retrieve risk assessment distribution data for dashboard charts"
)
async def get_risk_distribution(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get risk distribution data for dashboard visualization."""
    # Validate patient access permissions
    if "patient" in current_user.roles and patient_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only access their own data"
        )
    
    try:
        insight_repo = InsightReportRepository(db)
        
        # Get recent insight reports
        insight_reports, _ = await insight_repo.get_by_patient_id_paginated(
            patient_id, limit=10, offset=0
        )
        
        # Transform data for visualization
        risk_data = DashboardMetricsTransformer.transform_risk_distribution(insight_reports)
        
        return BaseResponse(
            success=True,
            message="Risk distribution data retrieved successfully",
            **{"data": risk_data}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk distribution data"
        )


@router.post(
    "/dashboard/{patient_id}/invalidate-cache",
    response_model=BaseResponse,
    summary="Invalidate dashboard cache",
    description="Force invalidation of cached dashboard data for a patient"
)
async def invalidate_dashboard_cache(
    patient_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Invalidate cached dashboard data for a patient."""
    # Validate patient access permissions (only healthcare providers can invalidate cache)
    if "patient" in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients cannot invalidate cache"
        )
    
    try:
        health_repo = HealthDataRepository(db)
        insight_repo = InsightReportRepository(db)
        dashboard_service = DashboardAggregationService(health_repo, insight_repo)
        
        # Invalidate cache
        success = await dashboard_service.invalidate_patient_cache(patient_id)
        
        if success:
            # Notify connected WebSocket clients about cache invalidation
            await websocket_manager.broadcast_patient_update(
                patient_id,
                "cache_invalidated",
                {"message": "Dashboard cache has been invalidated"}
            )
        
        return BaseResponse(
            success=success,
            message="Dashboard cache invalidated successfully" if success else "Failed to invalidate cache"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate dashboard cache"
        )


@router.websocket("/dashboard/{patient_id}/ws")
async def dashboard_websocket_endpoint(
    websocket: WebSocket,
    patient_id: str,
    client_id: str = Query(..., description="Unique client identifier")
):
    """WebSocket endpoint for real-time dashboard updates."""
    try:
        # Connect client
        connection = await websocket_manager.connect(websocket, client_id, patient_id)
        
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                await websocket_manager.handle_message(client_id, data)
                
        except WebSocketDisconnect:
            pass
        
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
    
    finally:
        # Disconnect client
        await websocket_manager.disconnect(client_id)


@router.get(
    "/dashboard/websocket/stats",
    response_model=BaseResponse,
    summary="Get WebSocket connection statistics",
    description="Retrieve statistics about active WebSocket connections"
)
async def get_websocket_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get WebSocket connection statistics (admin only)."""
    # Only allow admin users to view connection stats
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    stats = websocket_manager.get_connection_stats()
    
    return BaseResponse(
        success=True,
        message="WebSocket statistics retrieved successfully",
        **{"data": stats}
    )