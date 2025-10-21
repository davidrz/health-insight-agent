"""
Dashboard update service for handling real-time data changes.

This service monitors health data changes and triggers real-time
dashboard updates via WebSocket connections.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.domain.entities import HealthData
from app.domain.value_objects import InsightReport
from app.services.websocket_manager import websocket_manager
from app.services.dashboard_service import DashboardAggregationService
from app.infra import HealthDataRepository, InsightReportRepository
from app.infra.cache import cache_manager

logger = logging.getLogger(__name__)


class DashboardUpdateService:
    """Service for handling real-time dashboard updates."""
    
    def __init__(
        self,
        health_repo: HealthDataRepository,
        insight_repo: InsightReportRepository
    ):
        self.health_repo = health_repo
        self.insight_repo = insight_repo
        self.dashboard_service = DashboardAggregationService(health_repo, insight_repo)
    
    async def handle_health_data_update(
        self, 
        patient_id: str, 
        health_data: HealthData,
        update_type: str = "health_data_updated"
    ):
        """
        Handle health data update and trigger dashboard refresh.
        
        Args:
            patient_id: Patient identifier
            health_data: Updated health data
            update_type: Type of update (created, updated, deleted)
        """
        try:
            # Invalidate cached dashboard data
            await cache_manager.invalidate_patient_cache(patient_id)
            
            # Prepare update data
            update_data = {
                "patient_id": patient_id,
                "data_id": str(health_data.data_id),
                "timestamp": health_data.timestamp.isoformat(),
                "has_vitals": health_data.vitals is not None,
                "lab_results_count": len(health_data.lab_results),
                "symptoms_count": len(health_data.symptoms)
            }
            
            # Broadcast update to connected clients
            await websocket_manager.broadcast_patient_update(
                patient_id, update_type, update_data
            )
            
            # If this is a significant update, trigger dashboard refresh
            if self._is_significant_update(health_data):
                await self._trigger_dashboard_refresh(patient_id)
            
            logger.info(f"Processed {update_type} for patient {patient_id}")
            
        except Exception as e:
            logger.error(f"Failed to handle health data update for patient {patient_id}: {e}")
    
    async def handle_insight_report_update(
        self, 
        patient_id: str, 
        insight_report: InsightReport,
        update_type: str = "insight_report_updated"
    ):
        """
        Handle insight report update and trigger dashboard refresh.
        
        Args:
            patient_id: Patient identifier
            insight_report: Updated insight report
            update_type: Type of update (created, updated)
        """
        try:
            # Invalidate cached dashboard data
            await cache_manager.invalidate_patient_cache(patient_id)
            
            # Prepare update data
            update_data = {
                "patient_id": patient_id,
                "report_id": str(insight_report.report_id),
                "confidence_score": insight_report.confidence_score,
                "insights_count": len(insight_report.insights),
                "recommendations_count": len(insight_report.recommendations),
                "urgent_recommendations_count": len(insight_report.urgent_recommendations),
                "generated_at": insight_report.generated_at.isoformat()
            }
            
            # Add risk assessment info if available
            if insight_report.risk_assessment:
                update_data["overall_risk_level"] = insight_report.risk_assessment.overall_risk_level.value
                update_data["high_risk_factors_count"] = len(insight_report.risk_assessment.high_risk_factors)
            
            # Broadcast update to connected clients
            await websocket_manager.broadcast_patient_update(
                patient_id, update_type, update_data
            )
            
            # Always trigger dashboard refresh for insight reports
            await self._trigger_dashboard_refresh(patient_id)
            
            logger.info(f"Processed {update_type} for patient {patient_id}")
            
        except Exception as e:
            logger.error(f"Failed to handle insight report update for patient {patient_id}: {e}")
    
    async def handle_bulk_data_update(
        self, 
        patient_id: str, 
        update_count: int,
        update_type: str = "bulk_data_updated"
    ):
        """
        Handle bulk data update (multiple records at once).
        
        Args:
            patient_id: Patient identifier
            update_count: Number of records updated
            update_type: Type of bulk update
        """
        try:
            # Invalidate cached dashboard data
            await cache_manager.invalidate_patient_cache(patient_id)
            
            # Prepare update data
            update_data = {
                "patient_id": patient_id,
                "update_count": update_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Broadcast update to connected clients
            await websocket_manager.broadcast_patient_update(
                patient_id, update_type, update_data
            )
            
            # Always trigger dashboard refresh for bulk updates
            await self._trigger_dashboard_refresh(patient_id)
            
            logger.info(f"Processed {update_type} for patient {patient_id} ({update_count} records)")
            
        except Exception as e:
            logger.error(f"Failed to handle bulk data update for patient {patient_id}: {e}")
    
    async def _trigger_dashboard_refresh(self, patient_id: str):
        """Trigger dashboard refresh for a patient."""
        try:
            # Generate fresh dashboard data
            dashboard_data = await self.dashboard_service.get_dashboard_data(
                patient_id, force_refresh=True
            )
            
            # Broadcast dashboard refresh with new data
            await websocket_manager.broadcast_patient_update(
                patient_id,
                "dashboard_refresh",
                {
                    "dashboard_data": dashboard_data.dict(),
                    "refresh_timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to trigger dashboard refresh for patient {patient_id}: {e}")
    
    def _is_significant_update(self, health_data: HealthData) -> bool:
        """
        Determine if a health data update is significant enough to trigger refresh.
        
        Args:
            health_data: Health data to evaluate
            
        Returns:
            True if update is significant
        """
        # Consider update significant if it includes:
        # - Complete vital signs
        # - Lab results
        # - Multiple symptoms
        
        if health_data.has_complete_vitals():
            return True
        
        if len(health_data.lab_results) > 0:
            return True
        
        if len(health_data.symptoms) >= 2:
            return True
        
        return False
    
    async def broadcast_system_update(
        self, 
        update_type: str, 
        data: Dict[str, Any]
    ):
        """
        Broadcast system-wide update to all connected clients.
        
        Args:
            update_type: Type of system update
            data: Update data
        """
        try:
            await websocket_manager.broadcast_topic_update(
                "system", update_type, data
            )
            
            logger.info(f"Broadcasted system update: {update_type}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast system update: {e}")
    
    async def send_patient_notification(
        self, 
        patient_id: str, 
        notification_type: str,
        title: str,
        message: str,
        priority: str = "normal"
    ):
        """
        Send notification to a specific patient.
        
        Args:
            patient_id: Patient identifier
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            priority: Notification priority (low, normal, high, urgent)
        """
        try:
            notification_data = {
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "priority": priority,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await websocket_manager.broadcast_patient_update(
                patient_id, "notification", notification_data
            )
            
            logger.info(f"Sent {notification_type} notification to patient {patient_id}")
            
        except Exception as e:
            logger.error(f"Failed to send notification to patient {patient_id}: {e}")


class DashboardEventHandler:
    """Event handler for dashboard-related events."""
    
    def __init__(self, update_service: DashboardUpdateService):
        self.update_service = update_service
    
    async def on_health_data_created(self, patient_id: str, health_data: HealthData):
        """Handle health data creation event."""
        await self.update_service.handle_health_data_update(
            patient_id, health_data, "health_data_created"
        )
    
    async def on_health_data_updated(self, patient_id: str, health_data: HealthData):
        """Handle health data update event."""
        await self.update_service.handle_health_data_update(
            patient_id, health_data, "health_data_updated"
        )
    
    async def on_insight_report_created(self, patient_id: str, insight_report: InsightReport):
        """Handle insight report creation event."""
        await self.update_service.handle_insight_report_update(
            patient_id, insight_report, "insight_report_created"
        )
        
        # Send notification for high-confidence insights
        if insight_report.confidence_score >= 0.8:
            await self.update_service.send_patient_notification(
                patient_id,
                "new_insights",
                "New Health Insights Available",
                f"New health analysis completed with {len(insight_report.insights)} insights.",
                "normal"
            )
        
        # Send urgent notification for high-risk assessments
        if (insight_report.risk_assessment and 
            insight_report.risk_assessment.requires_immediate_attention):
            await self.update_service.send_patient_notification(
                patient_id,
                "urgent_attention",
                "Urgent Health Alert",
                "Your recent health analysis indicates conditions requiring immediate attention.",
                "urgent"
            )
    
    async def on_analysis_completed(self, patient_id: str, analysis_results: Dict[str, Any]):
        """Handle analysis completion event."""
        await self.update_service.broadcast_system_update(
            "analysis_completed",
            {
                "patient_id": patient_id,
                "analysis_type": analysis_results.get("type", "unknown"),
                "completion_time": datetime.utcnow().isoformat()
            }
        )
    
    async def on_system_maintenance(self, maintenance_type: str, message: str):
        """Handle system maintenance event."""
        await self.update_service.broadcast_system_update(
            "system_maintenance",
            {
                "maintenance_type": maintenance_type,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )