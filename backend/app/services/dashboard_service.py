"""
Dashboard data aggregation service for Health Insight Agent.

This service aggregates health metrics, manages real-time updates,
and provides data transformation for dashboard visualization.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from statistics import mean, median
from collections import defaultdict

from app.domain.entities import HealthData, VitalSigns, LabResult, RiskLevel
from app.domain.value_objects import InsightReport, HealthInsight, Recommendation
from app.domain.services import VitalSignsAnalysisService, RiskAssessmentService
from app.infra.cache import cache_manager
from app.infra import HealthDataRepository, InsightReportRepository
from app.api.schemas import (
    DashboardData, HealthMetricSummary, HealthInsightSchema, 
    RecommendationSchema
)

logger = logging.getLogger(__name__)


class DashboardAggregationService:
    """Service for aggregating and transforming dashboard data."""
    
    def __init__(
        self, 
        health_repo: HealthDataRepository,
        insight_repo: InsightReportRepository
    ):
        self.health_repo = health_repo
        self.insight_repo = insight_repo
        self.cache_ttl = 900  # 15 minutes for dashboard data
        
    async def get_dashboard_data(
        self, 
        patient_id: str,
        force_refresh: bool = False
    ) -> DashboardData:
        """
        Get comprehensive dashboard data for a patient.
        
        Args:
            patient_id: Patient identifier
            force_refresh: Skip cache and force data refresh
            
        Returns:
            Aggregated dashboard data
        """
        # Check cache first unless force refresh
        if not force_refresh:
            cached_data = await cache_manager.get_dashboard_data(patient_id)
            if cached_data:
                logger.info(f"Retrieved dashboard data from cache for patient {patient_id}")
                return DashboardData(**cached_data)
        
        # Aggregate fresh data
        dashboard_data = await self._aggregate_dashboard_data(patient_id)
        
        # Cache the result
        await cache_manager.cache_dashboard_data(
            patient_id, 
            dashboard_data.dict(), 
            self.cache_ttl
        )
        
        logger.info(f"Generated fresh dashboard data for patient {patient_id}")
        return dashboard_data
    
    async def _aggregate_dashboard_data(self, patient_id: str) -> DashboardData:
        """Aggregate dashboard data from various sources."""
        # Get recent health data (last 30 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        health_data_list = await self.health_repo.get_by_patient_id_and_date_range(
            patient_id, start_date, end_date
        )
        
        # Get recent insight reports
        insight_reports, _ = await self.insight_repo.get_by_patient_id_paginated(
            patient_id, limit=5, offset=0, min_confidence=0.7
        )
        
        # Generate health metrics
        health_metrics = await self._generate_health_metrics(health_data_list)
        
        # Extract recent insights
        recent_insights = self._extract_recent_insights(insight_reports)
        
        # Extract urgent recommendations
        urgent_recommendations = self._extract_urgent_recommendations(insight_reports)
        
        # Calculate overall health score
        overall_health_score = await self._calculate_overall_health_score(
            health_data_list, insight_reports
        )
        
        # Get last analysis date
        last_analysis_date = (
            insight_reports[0].generated_at if insight_reports else None
        )
        
        return DashboardData(
            patient_id=patient_id,
            health_metrics=health_metrics,
            recent_insights=recent_insights,
            urgent_recommendations=urgent_recommendations,
            overall_health_score=overall_health_score,
            last_analysis_date=last_analysis_date
        )
    
    async def _generate_health_metrics(
        self, 
        health_data_list: List[HealthData]
    ) -> List[HealthMetricSummary]:
        """Generate health metric summaries with trends."""
        if not health_data_list:
            return []
        
        metrics = []
        
        # Group data by metric type
        vital_metrics = self._extract_vital_metrics(health_data_list)
        lab_metrics = self._extract_lab_metrics(health_data_list)
        
        # Generate vital sign metrics
        for metric_name, values in vital_metrics.items():
            if values:
                current_value = values[0][0]  # Most recent value
                trend = self._calculate_trend([v[0] for v in values])
                last_updated = values[0][1]  # Most recent timestamp
                
                metrics.append(HealthMetricSummary(
                    metric_name=metric_name,
                    current_value=current_value,
                    trend=trend,
                    last_updated=last_updated
                ))
        
        # Generate lab result metrics
        for metric_name, values in lab_metrics.items():
            if values:
                current_value = values[0][0]  # Most recent value
                trend = self._calculate_trend([v[0] for v in values])
                last_updated = values[0][1]  # Most recent timestamp
                
                metrics.append(HealthMetricSummary(
                    metric_name=metric_name,
                    current_value=current_value,
                    trend=trend,
                    last_updated=last_updated
                ))
        
        return metrics
    
    def _extract_vital_metrics(
        self, 
        health_data_list: List[HealthData]
    ) -> Dict[str, List[Tuple[float, datetime]]]:
        """Extract vital sign metrics from health data."""
        metrics = defaultdict(list)
        
        for health_data in health_data_list:
            if not health_data.vitals:
                continue
                
            vitals = health_data.vitals
            timestamp = vitals.measured_at
            
            if vitals.heart_rate is not None:
                metrics["Heart Rate (BPM)"].append((float(vitals.heart_rate), timestamp))
            
            if vitals.blood_pressure_systolic is not None:
                metrics["Systolic BP (mmHg)"].append(
                    (float(vitals.blood_pressure_systolic), timestamp)
                )
            
            if vitals.blood_pressure_diastolic is not None:
                metrics["Diastolic BP (mmHg)"].append(
                    (float(vitals.blood_pressure_diastolic), timestamp)
                )
            
            if vitals.temperature is not None:
                metrics["Temperature (°C)"].append((vitals.temperature, timestamp))
            
            if vitals.respiratory_rate is not None:
                metrics["Respiratory Rate (BPM)"].append(
                    (float(vitals.respiratory_rate), timestamp)
                )
            
            if vitals.oxygen_saturation is not None:
                metrics["Oxygen Saturation (%)"].append(
                    (vitals.oxygen_saturation, timestamp)
                )
        
        return metrics
    
    def _extract_lab_metrics(
        self, 
        health_data_list: List[HealthData]
    ) -> Dict[str, List[Tuple[float, datetime]]]:
        """Extract lab result metrics from health data."""
        metrics = defaultdict(list)
        
        for health_data in health_data_list:
            for lab_result in health_data.lab_results:
                metric_name = f"{lab_result.test_type.value.replace('_', ' ').title()} ({lab_result.unit})"
                metrics[metric_name].append((lab_result.value, lab_result.tested_at))
        
        return metrics
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from a list of values (most recent first)."""
        if len(values) < 2:
            return "stable"
        
        # Use linear regression for trend calculation
        n = len(values)
        if n < 3:
            # Simple comparison for small datasets
            recent_avg = mean(values[:2])
            older_avg = mean(values[-2:])
        else:
            # Compare recent third vs older third
            third = max(1, n // 3)
            recent_avg = mean(values[:third])
            older_avg = mean(values[-third:])
        
        change_percent = ((recent_avg - older_avg) / older_avg * 100) if older_avg != 0 else 0
        
        if change_percent > 5:
            return "improving"
        elif change_percent < -5:
            return "declining"
        else:
            return "stable"
    
    def _extract_recent_insights(
        self, 
        insight_reports: List[InsightReport]
    ) -> List[HealthInsightSchema]:
        """Extract recent high-confidence insights."""
        insights = []
        
        for report in insight_reports[:3]:  # Last 3 reports
            for insight in report.high_confidence_insights:
                insights.append(HealthInsightSchema(
                    insight_type=insight.insight_type,
                    title=insight.title,
                    description=insight.description,
                    confidence_score=insight.confidence_score,
                    supporting_data=insight.supporting_data,
                    generated_at=insight.generated_at
                ))
        
        return insights[:5]  # Limit to 5 most recent
    
    def _extract_urgent_recommendations(
        self, 
        insight_reports: List[InsightReport]
    ) -> List[RecommendationSchema]:
        """Extract urgent recommendations."""
        recommendations = []
        
        for report in insight_reports:
            for rec in report.urgent_recommendations:
                recommendations.append(RecommendationSchema(
                    recommendation_type=rec.recommendation_type,
                    priority=rec.priority,
                    title=rec.title,
                    description=rec.description,
                    rationale=rec.rationale,
                    expected_outcome=rec.expected_outcome,
                    timeframe=rec.timeframe,
                    created_at=rec.created_at
                ))
        
        return recommendations[:3]  # Limit to 3 most urgent
    
    async def _calculate_overall_health_score(
        self, 
        health_data_list: List[HealthData],
        insight_reports: List[InsightReport]
    ) -> Optional[float]:
        """Calculate overall health score based on data and insights."""
        if not health_data_list and not insight_reports:
            return None
        
        base_score = 100.0
        
        # Deduct points based on vital sign abnormalities
        if health_data_list and health_data_list[0].vitals:
            vitals_analysis = VitalSignsAnalysisService.analyze_vital_signs(
                health_data_list[0].vitals
            )
            
            abnormality_count = len(vitals_analysis.get("abnormalities", []))
            base_score -= abnormality_count * 10
        
        # Deduct points based on risk assessment
        if insight_reports and insight_reports[0].risk_assessment:
            risk_assessment = insight_reports[0].risk_assessment
            
            risk_deductions = {
                RiskLevel.LOW: 0,
                RiskLevel.MODERATE: 15,
                RiskLevel.HIGH: 35,
                RiskLevel.VERY_HIGH: 60
            }
            
            base_score -= risk_deductions.get(risk_assessment.overall_risk_level, 0)
            base_score -= len(risk_assessment.high_risk_factors) * 10
            
            # Apply confidence factor
            base_score *= risk_assessment.confidence_score
        
        return max(0.0, min(100.0, base_score))
    
    async def invalidate_patient_cache(self, patient_id: str) -> bool:
        """Invalidate cached dashboard data for a patient."""
        return await cache_manager.invalidate_patient_cache(patient_id)


class DashboardMetricsTransformer:
    """Service for transforming health data for visualization."""
    
    @staticmethod
    def transform_time_series_data(
        health_data_list: List[HealthData],
        metric_type: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Transform health data into time series format for charts.
        
        Args:
            health_data_list: List of health data
            metric_type: Type of metric to extract ('vitals' or 'labs')
            days: Number of days to include
            
        Returns:
            Time series data formatted for visualization
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Filter data by date range
        filtered_data = [
            data for data in health_data_list
            if start_date <= data.timestamp <= end_date
        ]
        
        if metric_type == "vitals":
            return DashboardMetricsTransformer._transform_vitals_time_series(filtered_data)
        elif metric_type == "labs":
            return DashboardMetricsTransformer._transform_labs_time_series(filtered_data)
        else:
            return {"error": f"Unknown metric type: {metric_type}"}
    
    @staticmethod
    def _transform_vitals_time_series(
        health_data_list: List[HealthData]
    ) -> Dict[str, Any]:
        """Transform vital signs into time series format."""
        series_data = {
            "heart_rate": [],
            "blood_pressure_systolic": [],
            "blood_pressure_diastolic": [],
            "temperature": [],
            "respiratory_rate": [],
            "oxygen_saturation": []
        }
        
        for health_data in reversed(health_data_list):  # Chronological order
            if not health_data.vitals:
                continue
                
            timestamp = health_data.vitals.measured_at.isoformat()
            vitals = health_data.vitals
            
            if vitals.heart_rate is not None:
                series_data["heart_rate"].append({
                    "timestamp": timestamp,
                    "value": vitals.heart_rate
                })
            
            if vitals.blood_pressure_systolic is not None:
                series_data["blood_pressure_systolic"].append({
                    "timestamp": timestamp,
                    "value": vitals.blood_pressure_systolic
                })
            
            if vitals.blood_pressure_diastolic is not None:
                series_data["blood_pressure_diastolic"].append({
                    "timestamp": timestamp,
                    "value": vitals.blood_pressure_diastolic
                })
            
            if vitals.temperature is not None:
                series_data["temperature"].append({
                    "timestamp": timestamp,
                    "value": vitals.temperature
                })
            
            if vitals.respiratory_rate is not None:
                series_data["respiratory_rate"].append({
                    "timestamp": timestamp,
                    "value": vitals.respiratory_rate
                })
            
            if vitals.oxygen_saturation is not None:
                series_data["oxygen_saturation"].append({
                    "timestamp": timestamp,
                    "value": vitals.oxygen_saturation
                })
        
        return {
            "type": "vitals_time_series",
            "data": series_data,
            "metadata": {
                "total_records": len(health_data_list),
                "date_range": {
                    "start": health_data_list[-1].timestamp.isoformat() if health_data_list else None,
                    "end": health_data_list[0].timestamp.isoformat() if health_data_list else None
                }
            }
        }
    
    @staticmethod
    def _transform_labs_time_series(
        health_data_list: List[HealthData]
    ) -> Dict[str, Any]:
        """Transform lab results into time series format."""
        series_data = defaultdict(list)
        
        for health_data in reversed(health_data_list):  # Chronological order
            for lab_result in health_data.lab_results:
                test_type = lab_result.test_type.value
                timestamp = lab_result.tested_at.isoformat()
                
                series_data[test_type].append({
                    "timestamp": timestamp,
                    "value": lab_result.value,
                    "unit": lab_result.unit,
                    "reference_range": {
                        "min": lab_result.reference_range_min,
                        "max": lab_result.reference_range_max
                    } if lab_result.reference_range_min is not None else None
                })
        
        return {
            "type": "labs_time_series",
            "data": dict(series_data),
            "metadata": {
                "total_records": len(health_data_list),
                "test_types": list(series_data.keys()),
                "date_range": {
                    "start": health_data_list[-1].timestamp.isoformat() if health_data_list else None,
                    "end": health_data_list[0].timestamp.isoformat() if health_data_list else None
                }
            }
        }
    
    @staticmethod
    def transform_risk_distribution(
        insight_reports: List[InsightReport]
    ) -> Dict[str, Any]:
        """Transform risk assessments into distribution data for charts."""
        if not insight_reports:
            return {"type": "risk_distribution", "data": {}, "metadata": {}}
        
        risk_counts = defaultdict(int)
        risk_factors_by_type = defaultdict(list)
        
        for report in insight_reports:
            if report.risk_assessment:
                # Count overall risk levels
                risk_counts[report.risk_assessment.overall_risk_level.value] += 1
                
                # Collect risk factors by type
                for risk_factor in report.risk_assessment.risk_factors:
                    risk_factors_by_type[risk_factor.name].append({
                        "risk_level": risk_factor.risk_level.value,
                        "probability": risk_factor.probability,
                        "assessed_at": report.generated_at.isoformat()
                    })
        
        return {
            "type": "risk_distribution",
            "data": {
                "overall_risk_distribution": dict(risk_counts),
                "risk_factors_by_type": dict(risk_factors_by_type)
            },
            "metadata": {
                "total_assessments": len(insight_reports),
                "unique_risk_factors": len(risk_factors_by_type)
            }
        }