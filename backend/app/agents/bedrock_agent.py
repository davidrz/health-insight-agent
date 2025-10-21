"""
Bedrock agent implementation for natural language health insights.

This module implements a health analysis agent that uses AWS Bedrock
for generating natural language insights and symptom analysis.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import time

from .base import HealthAgent, AgentTask, AgentResponse, AgentType, AgentStatus
from ..infra.aws_bedrock import get_bedrock_client, BedrockServiceError
from ..domain.entities import HealthData
from ..domain.value_objects import (
    HealthInsight, InsightType, InsightReport, 
    Recommendation, RecommendationType, RecommendationPriority
)

logger = logging.getLogger(__name__)


class BedrockAgent(HealthAgent):
    """Health analysis agent using AWS Bedrock for natural language insights."""
    
    def __init__(self, agent_id: str = "bedrock-insights-agent"):
        super().__init__(agent_id, AgentType.BEDROCK_INSIGHTS)
        self.bedrock_client = get_bedrock_client()
        
        logger.info(f"Bedrock agent initialized: {agent_id}")
    
    async def execute_task(self, task: AgentTask) -> AgentResponse:
        """
        Execute a health analysis task using Bedrock.
        
        Args:
            task: The task to execute
            
        Returns:
            AgentResponse: Result of the task execution
        """
        start_time = time.time()
        
        try:
            self._set_status(AgentStatus.RUNNING)
            
            if not task.health_data:
                raise ValueError("Health data is required for Bedrock analysis")
            
            # Determine the type of analysis to perform
            analysis_type = task.parameters.get("analysis_type", "general_insights")
            
            if analysis_type == "general_insights":
                result = await self._generate_general_insights(task.health_data, task.parameters)
            elif analysis_type == "symptom_analysis":
                result = await self._analyze_symptoms(task.health_data, task.parameters)
            elif analysis_type == "risk_narrative":
                result = await self._generate_risk_narrative(task.health_data, task.parameters)
            else:
                raise ValueError(f"Unknown analysis type: {analysis_type}")
            
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
            error_msg = f"Bedrock analysis failed: {e}"
            
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
    
    async def _generate_general_insights(
        self, 
        health_data: HealthData, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate general health insights using Bedrock."""
        
        # Build context for Bedrock
        context = self._build_health_context(health_data)
        
        # Create prompt for general insights
        prompt = self._build_general_insights_prompt(health_data, parameters)
        
        try:
            # Generate insights using Bedrock
            insights_text = await self.bedrock_client.generate_insights(prompt, context)
            
            # Parse and structure the insights
            insights = self._parse_general_insights(insights_text, health_data.patient_id)
            
            return {
                "insights": [insight.__dict__ for insight in insights],
                "raw_analysis": insights_text,
                "analysis_type": "general_insights",
                "patient_id": health_data.patient_id
            }
            
        except BedrockServiceError as e:
            logger.error(f"Bedrock service error during general insights: {e}")
            raise
    
    async def _analyze_symptoms(
        self, 
        health_data: HealthData, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze symptoms using Bedrock."""
        
        if not health_data.symptoms:
            return {
                "analysis": "No symptoms reported for analysis",
                "recommendations": [],
                "analysis_type": "symptom_analysis",
                "patient_id": health_data.patient_id
            }
        
        # Extract symptom descriptions
        symptom_descriptions = [
            f"{symptom.name} ({symptom.severity.value})" + 
            (f" for {symptom.duration_days} days" if symptom.duration_days else "")
            for symptom in health_data.symptoms
        ]
        
        try:
            # Analyze symptoms using Bedrock
            analysis_result = await self.bedrock_client.analyze_symptoms(symptom_descriptions)
            
            # Generate recommendations based on analysis
            recommendations = self._generate_symptom_recommendations(
                analysis_result, health_data.patient_id
            )
            
            return {
                "analysis": analysis_result,
                "recommendations": [rec.__dict__ for rec in recommendations],
                "analysis_type": "symptom_analysis",
                "patient_id": health_data.patient_id
            }
            
        except BedrockServiceError as e:
            logger.error(f"Bedrock service error during symptom analysis: {e}")
            raise
    
    async def _generate_risk_narrative(
        self, 
        health_data: HealthData, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate risk narrative using Bedrock."""
        
        # Get risk assessment from parameters if provided
        risk_assessment = parameters.get("risk_assessment")
        
        if not risk_assessment:
            return {
                "narrative": "No risk assessment data provided for narrative generation",
                "analysis_type": "risk_narrative",
                "patient_id": health_data.patient_id
            }
        
        # Build context for risk narrative
        context = self._build_health_context(health_data)
        context["risk_assessment"] = risk_assessment
        
        # Create prompt for risk narrative
        prompt = self._build_risk_narrative_prompt(risk_assessment, parameters)
        
        try:
            # Generate narrative using Bedrock
            narrative = await self.bedrock_client.generate_insights(prompt, context)
            
            return {
                "narrative": narrative,
                "risk_level": risk_assessment.get("overall_risk_level"),
                "analysis_type": "risk_narrative",
                "patient_id": health_data.patient_id
            }
            
        except BedrockServiceError as e:
            logger.error(f"Bedrock service error during risk narrative: {e}")
            raise
    
    def _build_health_context(self, health_data: HealthData) -> Dict[str, Any]:
        """Build context dictionary from health data."""
        context = {
            "patient_id": health_data.patient_id,
            "data_timestamp": health_data.timestamp.isoformat()
        }
        
        # Add vital signs
        if health_data.vitals:
            context["vitals"] = {
                "heart_rate": health_data.vitals.heart_rate,
                "blood_pressure": f"{health_data.vitals.blood_pressure_systolic}/{health_data.vitals.blood_pressure_diastolic}",
                "temperature": health_data.vitals.temperature,
                "respiratory_rate": health_data.vitals.respiratory_rate,
                "oxygen_saturation": health_data.vitals.oxygen_saturation
            }
        
        # Add lab results
        if health_data.lab_results:
            context["lab_results"] = [
                {
                    "test": result.test_type.value,
                    "value": result.value,
                    "unit": result.unit,
                    "normal_range": f"{result.reference_range_min}-{result.reference_range_max}" 
                    if result.reference_range_min and result.reference_range_max else None
                }
                for result in health_data.lab_results
            ]
        
        # Add symptoms
        if health_data.symptoms:
            context["symptoms"] = [
                {
                    "name": symptom.name,
                    "severity": symptom.severity.value,
                    "duration_days": symptom.duration_days,
                    "description": symptom.description
                }
                for symptom in health_data.symptoms
            ]
        
        # Add medical history
        if health_data.medical_history:
            context["medical_history"] = {
                "conditions": health_data.medical_history.conditions,
                "medications": health_data.medical_history.medications,
                "allergies": health_data.medical_history.allergies,
                "surgeries": health_data.medical_history.surgeries,
                "family_history": health_data.medical_history.family_history
            }
        
        return context
    
    def _build_general_insights_prompt(
        self, 
        health_data: HealthData, 
        parameters: Dict[str, Any]
    ) -> str:
        """Build prompt for general health insights."""
        focus_areas = parameters.get("focus_areas", [])
        detail_level = parameters.get("detail_level", "standard")
        
        prompt = f"""
        Analyze the provided health data and generate comprehensive health insights for patient {health_data.patient_id}.
        
        Please provide insights in the following areas:
        1. Overall health status assessment
        2. Key observations from vital signs and lab results
        3. Potential health risks or concerns
        4. Positive health indicators
        5. Recommendations for health improvement
        """
        
        if focus_areas:
            prompt += f"\n\nPlease pay special attention to: {', '.join(focus_areas)}"
        
        if detail_level == "detailed":
            prompt += "\n\nProvide detailed explanations and medical reasoning for each insight."
        elif detail_level == "summary":
            prompt += "\n\nProvide concise, high-level insights suitable for quick review."
        
        prompt += """
        
        Format your response as clear, actionable insights that can help both healthcare providers and patients understand the health status.
        """
        
        return prompt
    
    def _build_risk_narrative_prompt(
        self, 
        risk_assessment: Dict[str, Any], 
        parameters: Dict[str, Any]
    ) -> str:
        """Build prompt for risk narrative generation."""
        audience = parameters.get("audience", "patient")
        
        prompt = f"""
        Create a clear, understandable narrative explanation of the health risk assessment provided.
        
        Risk Assessment Summary:
        - Overall Risk Level: {risk_assessment.get('overall_risk_level', 'Unknown')}
        - Risk Factors: {', '.join(risk_assessment.get('risk_factors', []))}
        - Confidence Score: {risk_assessment.get('confidence_score', 'N/A')}
        
        Target Audience: {audience}
        """
        
        if audience == "patient":
            prompt += """
            
            Write in plain language that a patient can easily understand. Avoid medical jargon and explain any necessary medical terms. Focus on:
            - What the risk assessment means for their health
            - Why certain factors contribute to risk
            - What they can do to improve their health outcomes
            - When they should seek medical attention
            """
        else:  # healthcare provider
            prompt += """
            
            Write for healthcare professionals with appropriate medical terminology. Focus on:
            - Clinical significance of the risk factors
            - Recommended interventions and monitoring
            - Differential considerations
            - Evidence-based treatment approaches
            """
        
        return prompt
    
    def _parse_general_insights(self, insights_text: str, patient_id: str) -> list:
        """Parse general insights from Bedrock response."""
        # For now, create a single comprehensive insight
        # In a production system, you might parse structured output
        
        insight = HealthInsight(
            insight_type=InsightType.GENERAL_HEALTH,
            title="Comprehensive Health Analysis",
            description=insights_text,
            confidence_score=0.85,  # Default confidence for Bedrock insights
            supporting_data={"source": "bedrock_llm", "patient_id": patient_id}
        )
        
        return [insight]
    
    def _generate_symptom_recommendations(
        self, 
        analysis_result: Dict[str, Any], 
        patient_id: str
    ) -> list:
        """Generate recommendations based on symptom analysis."""
        recommendations = []
        
        urgency_level = analysis_result.get("urgency_level", "routine")
        severity = analysis_result.get("severity_assessment", "moderate")
        
        # Map urgency to priority
        priority_mapping = {
            "emergency": RecommendationPriority.URGENT,
            "urgent": RecommendationPriority.HIGH,
            "routine": RecommendationPriority.MEDIUM
        }
        
        priority = priority_mapping.get(urgency_level, RecommendationPriority.MEDIUM)
        
        # Generate appropriate recommendations
        if urgency_level == "emergency":
            recommendations.append(Recommendation(
                recommendation_type=RecommendationType.EMERGENCY_CARE,
                priority=RecommendationPriority.URGENT,
                title="Seek Immediate Medical Attention",
                description="Based on symptom analysis, immediate medical evaluation is recommended",
                rationale=f"Symptoms indicate {severity} severity with emergency urgency",
                timeframe="immediately"
            ))
        elif urgency_level == "urgent":
            recommendations.append(Recommendation(
                recommendation_type=RecommendationType.MEDICAL_CONSULTATION,
                priority=RecommendationPriority.HIGH,
                title="Schedule Urgent Medical Consultation",
                description="Symptoms require prompt medical evaluation",
                rationale=f"Symptom analysis indicates {severity} severity requiring urgent attention",
                timeframe="within 24 hours"
            ))
        else:
            recommendations.append(Recommendation(
                recommendation_type=RecommendationType.MEDICAL_CONSULTATION,
                priority=priority,
                title="Schedule Medical Consultation",
                description="Discuss symptoms with healthcare provider",
                rationale=f"Symptom analysis suggests {severity} severity",
                timeframe="within 1-2 weeks"
            ))
        
        # Add specific recommendations from analysis
        for action in analysis_result.get("recommended_actions", []):
            recommendations.append(Recommendation(
                recommendation_type=RecommendationType.MONITORING,
                priority=priority,
                title=f"Follow Recommendation: {action}",
                description=action,
                rationale="Based on AI symptom analysis",
                timeframe="as appropriate"
            ))
        
        return recommendations
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the Bedrock agent."""
        try:
            # Check Bedrock client health
            bedrock_health = await self.bedrock_client.health_check()
            
            agent_status = {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type.value,
                "status": "healthy" if bedrock_health["status"] == "healthy" else "unhealthy",
                "bedrock_service": bedrock_health,
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