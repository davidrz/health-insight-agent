"""
SageMaker agent implementation for ML-based health analysis.

This module implements health analysis agents that use AWS SageMaker
for risk prediction and anomaly detection.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import time

from .base import HealthAgent, AgentTask, AgentResponse, AgentType, AgentStatus
from ..infra.aws_sagemaker import (
    get_sagemaker_client, SageMakerServiceError, 
    HealthMetrics, TimeSeriesData, RiskAssessment, AnomalyReport
)
from ..domain.entities import HealthData, VitalSigns, LabResult
from ..domain.value_objects import (
    RiskFactor, RiskLevel, HealthInsight, InsightType,
    Recommendation, RecommendationType, RecommendationPriority
)

logger = logging.getLogger(__name__)


class SageMakerRiskAgent(HealthAgent):
    """Health analysis agent using AWS SageMaker for risk prediction."""
    
    def __init__(self, agent_id: str = "sagemaker-risk-agent"):
        super().__init__(agent_id, AgentType.SAGEMAKER_RISK)
        self.sagemaker_client = get_sagemaker_client()
        
        logger.info(f"SageMaker risk agent initialized: {agent_id}")
    
    async def execute_task(self, task: AgentTask) -> AgentResponse:
        """
        Execute a risk prediction task using SageMaker.
        
        Args:
            task: The task to execute
            
        Returns:
            AgentResponse: Result of the task execution
        """
        start_time = time.time()
        
        try:
            self._set_status(AgentStatus.RUNNING)
            
            if not task.health_data:
                raise ValueError("Health data is required for risk prediction")
            
            # Convert health data to metrics format
            health_metrics = self._convert_to_health_metrics(
                task.health_data, task.parameters
            )
            
            # Predict risk factors using SageMaker
            risk_assessment = await self.sagemaker_client.predict_risk_factors(health_metrics)
            
            # Convert to domain objects
            result = self._convert_risk_assessment_result(
                risk_assessment, task.health_data.patient_id
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            self._update_task_stats(True)
            self._set_status(AgentStatus.IDLE)
            
            return AgentResponse(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=True,
                result=result,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"SageMaker risk prediction failed: {e}"
            
            logger.error(f"Task {task.task_id} failed: {error_msg}")
            
            self._update_task_stats(False)
            self._set_status(AgentStatus.ERROR)
            
            return AgentResponse(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                error_message=error_msg,
                execution_time_ms=execution_time
            )
    
    def _convert_to_health_metrics(
        self, 
        health_data: HealthData, 
        parameters: Dict[str, Any]
    ) -> HealthMetrics:
        """Convert health data to SageMaker HealthMetrics format."""
        
        # Extract basic demographics from parameters
        age = parameters.get("age", 0)
        gender = parameters.get("gender", "unknown")
        
        # Initialize metrics data
        metrics_data = {
            "age": age,
            "gender": gender,
            "smoking": parameters.get("smoking", False),
            "exercise_frequency": parameters.get("exercise_frequency", 0)
        }
        
        # Extract vital signs
        if health_data.vitals:
            vitals = health_data.vitals
            metrics_data.update({
                "heart_rate": vitals.heart_rate or 0,
                "blood_pressure_systolic": vitals.blood_pressure_systolic or 0,
                "blood_pressure_diastolic": vitals.blood_pressure_diastolic or 0
            })
        
        # Extract lab results
        for lab_result in health_data.lab_results:
            if lab_result.test_type.value == "cholesterol_total":
                metrics_data["cholesterol"] = lab_result.value
            elif lab_result.test_type.value == "blood_glucose":
                metrics_data["glucose"] = lab_result.value
        
        # Calculate BMI if height and weight provided
        height_m = parameters.get("height_m")
        weight_kg = parameters.get("weight_kg")
        if height_m and weight_kg and height_m > 0:
            metrics_data["bmi"] = weight_kg / (height_m ** 2)
        else:
            metrics_data["bmi"] = parameters.get("bmi", 0)
        
        # Extract family history
        if health_data.medical_history:
            metrics_data["family_history"] = health_data.medical_history.family_history
        
        return HealthMetrics(metrics_data)
    
    def _convert_risk_assessment_result(
        self, 
        risk_assessment: RiskAssessment, 
        patient_id: str
    ) -> Dict[str, Any]:
        """Convert SageMaker risk assessment to domain format."""
        
        # Map risk score to risk level
        risk_score = risk_assessment.risk_score
        if risk_score >= 0.8:
            overall_risk_level = RiskLevel.VERY_HIGH
        elif risk_score >= 0.6:
            overall_risk_level = RiskLevel.HIGH
        elif risk_score >= 0.4:
            overall_risk_level = RiskLevel.MODERATE
        else:
            overall_risk_level = RiskLevel.LOW
        
        # Create risk factors
        risk_factors = []
        for factor_name in risk_assessment.risk_factors:
            # Determine individual risk level based on factor
            factor_risk_level = self._determine_factor_risk_level(factor_name, risk_score)
            
            risk_factor = RiskFactor(
                name=factor_name,
                risk_level=factor_risk_level,
                probability=min(risk_score + 0.1, 1.0),  # Slightly higher than overall
                contributing_factors=[factor_name],
                mitigation_strategies=self._get_mitigation_strategies(factor_name)
            )
            risk_factors.append(risk_factor)
        
        # Create health insights
        insights = [
            HealthInsight(
                insight_type=InsightType.RISK_FACTOR,
                title="ML-Based Risk Assessment",
                description=f"Machine learning analysis indicates {overall_risk_level.value} risk level with score {risk_score:.2f}",
                confidence_score=risk_assessment.confidence,
                supporting_data={
                    "risk_score": risk_score,
                    "risk_factors": risk_assessment.risk_factors,
                    "model_confidence": risk_assessment.confidence,
                    "source": "sagemaker_ml"
                }
            )
        ]
        
        # Create recommendations
        recommendations = []
        for rec_text in risk_assessment.recommendations:
            recommendation = Recommendation(
                recommendation_type=self._determine_recommendation_type(rec_text),
                priority=self._determine_recommendation_priority(overall_risk_level),
                title=f"ML Recommendation: {rec_text[:50]}...",
                description=rec_text,
                rationale=f"Based on ML risk assessment (score: {risk_score:.2f})",
                timeframe=self._determine_timeframe(overall_risk_level)
            )
            recommendations.append(recommendation)
        
        return {
            "risk_assessment": {
                "overall_risk_level": overall_risk_level.value,
                "risk_score": risk_score,
                "confidence": risk_assessment.confidence,
                "assessment_time": risk_assessment.assessment_time.isoformat()
            },
            "risk_factors": [factor.__dict__ for factor in risk_factors],
            "insights": [insight.__dict__ for insight in insights],
            "recommendations": [rec.__dict__ for rec in recommendations],
            "patient_id": patient_id,
            "analysis_type": "ml_risk_prediction"
        }
    
    def _determine_factor_risk_level(self, factor_name: str, overall_score: float) -> RiskLevel:
        """Determine risk level for individual factor."""
        # High-impact factors get higher risk levels
        high_impact_factors = ["High blood pressure", "High cholesterol", "Smoking", "Diabetes"]
        
        if any(high_factor in factor_name for high_factor in high_impact_factors):
            if overall_score >= 0.7:
                return RiskLevel.VERY_HIGH
            elif overall_score >= 0.5:
                return RiskLevel.HIGH
            else:
                return RiskLevel.MODERATE
        else:
            if overall_score >= 0.8:
                return RiskLevel.HIGH
            elif overall_score >= 0.6:
                return RiskLevel.MODERATE
            else:
                return RiskLevel.LOW
    
    def _get_mitigation_strategies(self, factor_name: str) -> List[str]:
        """Get mitigation strategies for a risk factor."""
        strategies_map = {
            "High blood pressure": [
                "Reduce sodium intake",
                "Regular cardiovascular exercise",
                "Stress management",
                "Maintain healthy weight"
            ],
            "High cholesterol": [
                "Heart-healthy diet",
                "Regular physical activity",
                "Limit saturated fats",
                "Consider statin therapy if recommended"
            ],
            "Smoking": [
                "Smoking cessation program",
                "Nicotine replacement therapy",
                "Behavioral counseling",
                "Support groups"
            ],
            "Obesity": [
                "Caloric restriction",
                "Regular exercise routine",
                "Nutritional counseling",
                "Weight management program"
            ],
            "Sedentary lifestyle": [
                "Increase daily physical activity",
                "Regular exercise schedule",
                "Active transportation",
                "Reduce sedentary time"
            ]
        }
        
        # Find matching strategies
        for key, strategies in strategies_map.items():
            if key.lower() in factor_name.lower():
                return strategies
        
        # Default strategies
        return ["Consult healthcare provider", "Regular health monitoring"]
    
    def _determine_recommendation_type(self, recommendation_text: str) -> RecommendationType:
        """Determine recommendation type from text."""
        text_lower = recommendation_text.lower()
        
        if any(word in text_lower for word in ["consult", "doctor", "physician", "provider"]):
            return RecommendationType.MEDICAL_CONSULTATION
        elif any(word in text_lower for word in ["monitor", "track", "check"]):
            return RecommendationType.MONITORING
        elif any(word in text_lower for word in ["test", "screening", "examination"]):
            return RecommendationType.DIAGNOSTIC_TEST
        elif any(word in text_lower for word in ["exercise", "diet", "lifestyle", "weight"]):
            return RecommendationType.LIFESTYLE_CHANGE
        else:
            return RecommendationType.MEDICAL_CONSULTATION
    
    def _determine_recommendation_priority(self, risk_level: RiskLevel) -> RecommendationPriority:
        """Determine recommendation priority based on risk level."""
        priority_map = {
            RiskLevel.VERY_HIGH: RecommendationPriority.URGENT,
            RiskLevel.HIGH: RecommendationPriority.HIGH,
            RiskLevel.MODERATE: RecommendationPriority.MEDIUM,
            RiskLevel.LOW: RecommendationPriority.LOW
        }
        return priority_map.get(risk_level, RecommendationPriority.MEDIUM)
    
    def _determine_timeframe(self, risk_level: RiskLevel) -> str:
        """Determine timeframe based on risk level."""
        timeframe_map = {
            RiskLevel.VERY_HIGH: "within 24 hours",
            RiskLevel.HIGH: "within 1 week",
            RiskLevel.MODERATE: "within 2 weeks",
            RiskLevel.LOW: "within 1 month"
        }
        return timeframe_map.get(risk_level, "within 2 weeks")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the SageMaker risk agent."""
        try:
            # Check SageMaker client health
            sagemaker_health = await self.sagemaker_client.health_check()
            
            agent_status = {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type.value,
                "status": "healthy" if sagemaker_health["status"] == "healthy" else "unhealthy",
                "sagemaker_service": sagemaker_health,
                "last_activity": self.last_activity.isoformat(),
                "task_stats": {
                    "total_tasks": self.total_tasks,
                    "successful_tasks": self.successful_tasks,
                    "error_count": self.error_count,
                    "success_rate": (
                        self.successful_tasks / self.total_tasks 
                        if self.total_tasks > 0 else 0.0
                    )
                }
            }
            
            return agent_status
            
        except Exception as e:
            return {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type.value,
                "status": "error",
                "error": str(e),
                "last_activity": self.last_activity.isoformat()
            }


class SageMakerAnomalyAgent(HealthAgent):
    """Health analysis agent using AWS SageMaker for anomaly detection."""
    
    def __init__(self, agent_id: str = "sagemaker-anomaly-agent"):
        super().__init__(agent_id, AgentType.SAGEMAKER_ANOMALY)
        self.sagemaker_client = get_sagemaker_client()
        
        logger.info(f"SageMaker anomaly agent initialized: {agent_id}")
    
    async def execute_task(self, task: AgentTask) -> AgentResponse:
        """
        Execute an anomaly detection task using SageMaker.
        
        Args:
            task: The task to execute
            
        Returns:
            AgentResponse: Result of the task execution
        """
        start_time = time.time()
        
        try:
            self._set_status(AgentStatus.RUNNING)
            
            # Get time series data from parameters
            time_series_data = task.parameters.get("time_series_data")
            if not time_series_data:
                raise ValueError("Time series data is required for anomaly detection")
            
            # Convert to TimeSeriesData format
            ts_data = TimeSeriesData(time_series_data)
            
            # Detect anomalies using SageMaker
            anomaly_report = await self.sagemaker_client.detect_anomalies(ts_data)
            
            # Convert to domain objects
            result = self._convert_anomaly_result(
                anomaly_report, 
                task.health_data.patient_id if task.health_data else "unknown"
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            self._update_task_stats(True)
            self._set_status(AgentStatus.IDLE)
            
            return AgentResponse(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=True,
                result=result,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            error_msg = f"SageMaker anomaly detection failed: {e}"
            
            logger.error(f"Task {task.task_id} failed: {error_msg}")
            
            self._update_task_stats(False)
            self._set_status(AgentStatus.ERROR)
            
            return AgentResponse(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                error_message=error_msg,
                execution_time_ms=execution_time
            )
    
    def _convert_anomaly_result(
        self, 
        anomaly_report: AnomalyReport, 
        patient_id: str
    ) -> Dict[str, Any]:
        """Convert SageMaker anomaly report to domain format."""
        
        # Create health insights for anomalies
        insights = []
        
        if anomaly_report.anomalies:
            for anomaly in anomaly_report.anomalies:
                severity = anomaly.get("severity", "moderate")
                
                insight = HealthInsight(
                    insight_type=InsightType.TREND_ANALYSIS,
                    title=f"Anomaly Detected: {severity.title()} Severity",
                    description=f"Unusual pattern detected at {anomaly.get('timestamp')} with value {anomaly.get('value')}",
                    confidence_score=min(anomaly.get("z_score", 2.0) / 4.0, 1.0),
                    supporting_data={
                        "anomaly_details": anomaly,
                        "anomaly_score": anomaly_report.anomaly_score,
                        "threshold": anomaly_report.threshold,
                        "source": "sagemaker_anomaly_detection"
                    }
                )
                insights.append(insight)
        else:
            # No anomalies detected
            insight = HealthInsight(
                insight_type=InsightType.TREND_ANALYSIS,
                title="Normal Pattern Detected",
                description="No significant anomalies detected in the health data patterns",
                confidence_score=0.9,
                supporting_data={
                    "anomaly_score": anomaly_report.anomaly_score,
                    "threshold": anomaly_report.threshold,
                    "source": "sagemaker_anomaly_detection"
                }
            )
            insights.append(insight)
        
        # Create recommendations based on anomalies
        recommendations = []
        
        if anomaly_report.anomaly_score > anomaly_report.threshold:
            # High anomaly score - recommend investigation
            priority = (
                RecommendationPriority.HIGH 
                if anomaly_report.anomaly_score > 0.8 
                else RecommendationPriority.MEDIUM
            )
            
            recommendation = Recommendation(
                recommendation_type=RecommendationType.MONITORING,
                priority=priority,
                title="Investigate Unusual Health Patterns",
                description="Anomalous patterns detected in health data require further investigation",
                rationale=f"Anomaly score {anomaly_report.anomaly_score:.2f} exceeds threshold {anomaly_report.threshold:.2f}",
                timeframe="within 1 week" if priority == RecommendationPriority.HIGH else "within 2 weeks"
            )
            recommendations.append(recommendation)
        
        return {
            "anomaly_report": {
                "anomaly_score": anomaly_report.anomaly_score,
                "threshold": anomaly_report.threshold,
                "anomalies_count": len(anomaly_report.anomalies),
                "detection_time": anomaly_report.detection_time.isoformat()
            },
            "anomalies": anomaly_report.anomalies,
            "insights": [insight.__dict__ for insight in insights],
            "recommendations": [rec.__dict__ for rec in recommendations],
            "patient_id": patient_id,
            "analysis_type": "anomaly_detection"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the SageMaker anomaly agent."""
        try:
            # Check SageMaker client health
            sagemaker_health = await self.sagemaker_client.health_check()
            
            agent_status = {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type.value,
                "status": "healthy" if sagemaker_health["status"] == "healthy" else "unhealthy",
                "sagemaker_service": sagemaker_health,
                "last_activity": self.last_activity.isoformat(),
                "task_stats": {
                    "total_tasks": self.total_tasks,
                    "successful_tasks": self.successful_tasks,
                    "error_count": self.error_count,
                    "success_rate": (
                        self.successful_tasks / self.total_tasks 
                        if self.total_tasks > 0 else 0.0
                    )
                }
            }
            
            return agent_status
            
        except Exception as e:
            return {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type.value,
                "status": "error",
                "error": str(e),
                "last_activity": self.last_activity.isoformat()
            }