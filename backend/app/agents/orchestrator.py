"""
Agent Orchestrator for coordinating multiple AI agents in health analysis.

This module implements the orchestration logic that coordinates
Bedrock and SageMaker agents to provide comprehensive health insights.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID, uuid4
import time

from .base import AgentTask, AgentResponse, AgentType, AgentStatus
from .mcp_server import get_mcp_server, MCPServer, AgentNotFoundError, TaskExecutionError
from .bedrock_agent import BedrockAgent
from .sagemaker_agent import SageMakerRiskAgent, SageMakerAnomalyAgent
from ..domain.entities import HealthData
from ..domain.value_objects import (
    InsightReport, HealthInsight, RiskAssessment, Recommendation,
    RiskLevel, InsightType, RecommendationType, RecommendationPriority
)

logger = logging.getLogger(__name__)


from app.core.exceptions import BusinessLogicError

class OrchestrationError(BusinessLogicError):
    """Base exception for orchestration errors."""
    pass


class AgentOrchestrator:
    """Coordinates multiple AI agents for comprehensive health analysis."""
    
    def __init__(self):
        self.orchestrator_id = str(uuid4())
        self.mcp_server = get_mcp_server()
        self.is_initialized = False
        
        # Analysis workflow configuration
        self.default_workflow = [
            AgentType.SAGEMAKER_RISK,      # Risk prediction first
            AgentType.BEDROCK_INSIGHTS,    # Natural language insights
            AgentType.SAGEMAKER_ANOMALY    # Anomaly detection (optional)
        ]
        
        # Orchestration statistics
        self.total_analyses = 0
        self.successful_analyses = 0
        self.failed_analyses = 0
        
        logger.info(f"Agent Orchestrator initialized: {self.orchestrator_id}")
    
    async def initialize(self) -> bool:
        """
        Initialize the orchestrator and register agents.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Ensure MCP server is running
            if not self.mcp_server.is_running:
                await self.mcp_server.start()
            
            # Register agents
            await self._register_agents()
            
            self.is_initialized = True
            logger.info("Agent Orchestrator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Agent Orchestrator: {e}")
            return False
    
    async def analyze_health_data(
        self, 
        health_data: HealthData, 
        analysis_options: Optional[Dict[str, Any]] = None
    ) -> InsightReport:
        """
        Orchestrate comprehensive health analysis across multiple agents.
        
        Args:
            health_data: The health data to analyze
            analysis_options: Optional configuration for analysis
            
        Returns:
            InsightReport: Comprehensive analysis results
            
        Raises:
            OrchestrationError: If orchestration fails
        """
        if not self.is_initialized:
            raise OrchestrationError("Orchestrator not initialized")
        
        start_time = time.time()
        analysis_options = analysis_options or {}
        
        try:
            logger.info(f"Starting health analysis for patient {health_data.patient_id}")
            
            # Create insight report
            insight_report = InsightReport(
                patient_id=health_data.patient_id,
                metadata={
                    "orchestrator_id": self.orchestrator_id,
                    "analysis_start_time": datetime.utcnow().isoformat(),
                    "workflow": [agent_type.value for agent_type in self.default_workflow]
                }
            )
            
            # Execute analysis workflow
            workflow_results = await self._execute_analysis_workflow(
                health_data, analysis_options
            )
            
            # Combine results into comprehensive report
            await self._combine_analysis_results(insight_report, workflow_results)
            
            # Calculate overall confidence score
            insight_report.confidence_score = self._calculate_overall_confidence(
                workflow_results
            )
            
            execution_time = time.time() - start_time
            insight_report.metadata["execution_time_seconds"] = execution_time
            
            self.total_analyses += 1
            self.successful_analyses += 1
            
            logger.info(
                f"Health analysis completed for patient {health_data.patient_id} "
                f"in {execution_time:.2f}s"
            )
            
            return insight_report
            
        except Exception as e:
            self.total_analyses += 1
            self.failed_analyses += 1
            
            error_msg = f"Health analysis failed for patient {health_data.patient_id}: {e}"
            logger.error(error_msg)
            raise OrchestrationError(error_msg)
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """
        Get status of all registered agents.
        
        Returns:
            Dict containing agent status information
        """
        try:
            agent_status = await self.mcp_server.get_agent_status()
            
            return {
                "orchestrator_id": self.orchestrator_id,
                "is_initialized": self.is_initialized,
                "mcp_server_status": self.mcp_server.get_server_stats(),
                "agents": agent_status,
                "orchestration_stats": {
                    "total_analyses": self.total_analyses,
                    "successful_analyses": self.successful_analyses,
                    "failed_analyses": self.failed_analyses,
                    "success_rate": (
                        self.successful_analyses / self.total_analyses 
                        if self.total_analyses > 0 else 0.0
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get agent status: {e}")
            return {
                "orchestrator_id": self.orchestrator_id,
                "is_initialized": self.is_initialized,
                "error": str(e)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on orchestrator and all agents.
        
        Returns:
            Dict containing health check results
        """
        try:
            # Check MCP server health
            mcp_health = await self.mcp_server.health_check()
            
            orchestrator_health = {
                "orchestrator_id": self.orchestrator_id,
                "status": "healthy" if self.is_initialized else "not_initialized",
                "mcp_server": mcp_health,
                "orchestration_stats": {
                    "total_analyses": self.total_analyses,
                    "successful_analyses": self.successful_analyses,
                    "failed_analyses": self.failed_analyses,
                    "success_rate": (
                        self.successful_analyses / self.total_analyses 
                        if self.total_analyses > 0 else 0.0
                    )
                }
            }
            
            return orchestrator_health
            
        except Exception as e:
            return {
                "orchestrator_id": self.orchestrator_id,
                "status": "error",
                "error": str(e)
            }
    
    async def _register_agents(self) -> None:
        """Register all health analysis agents with MCP server."""
        
        # Create and register Bedrock agent
        bedrock_agent = BedrockAgent()
        await self.mcp_server.register_agent(bedrock_agent)
        
        # Create and register SageMaker risk agent
        risk_agent = SageMakerRiskAgent()
        await self.mcp_server.register_agent(risk_agent)
        
        # Create and register SageMaker anomaly agent
        anomaly_agent = SageMakerAnomalyAgent()
        await self.mcp_server.register_agent(anomaly_agent)
        
        logger.info("All agents registered successfully")
    
    async def _execute_analysis_workflow(
        self, 
        health_data: HealthData, 
        analysis_options: Dict[str, Any]
    ) -> Dict[AgentType, AgentResponse]:
        """Execute the analysis workflow across multiple agents."""
        
        workflow_results = {}
        
        # Step 1: Risk prediction using SageMaker
        if AgentType.SAGEMAKER_RISK in self.default_workflow:
            try:
                risk_task = AgentTask(
                    agent_type=AgentType.SAGEMAKER_RISK,
                    health_data=health_data,
                    parameters=self._prepare_risk_parameters(health_data, analysis_options),
                    timeout_seconds=45
                )
                
                risk_response = await self.mcp_server.execute_agent_task(risk_task)
                workflow_results[AgentType.SAGEMAKER_RISK] = risk_response
                
                logger.info(f"Risk prediction completed: {risk_response.success}")
                
            except (AgentNotFoundError, TaskExecutionError) as e:
                logger.warning(f"Risk prediction failed: {e}")
                # Continue with other agents even if one fails
        
        # Step 2: Natural language insights using Bedrock
        if AgentType.BEDROCK_INSIGHTS in self.default_workflow:
            try:
                # Include risk assessment results if available
                bedrock_params = self._prepare_bedrock_parameters(
                    health_data, analysis_options, workflow_results
                )
                
                bedrock_task = AgentTask(
                    agent_type=AgentType.BEDROCK_INSIGHTS,
                    health_data=health_data,
                    parameters=bedrock_params,
                    timeout_seconds=60
                )
                
                bedrock_response = await self.mcp_server.execute_agent_task(bedrock_task)
                workflow_results[AgentType.BEDROCK_INSIGHTS] = bedrock_response
                
                logger.info(f"Bedrock insights completed: {bedrock_response.success}")
                
            except (AgentNotFoundError, TaskExecutionError) as e:
                logger.warning(f"Bedrock insights failed: {e}")
        
        # Step 3: Anomaly detection (optional, if time series data available)
        if (AgentType.SAGEMAKER_ANOMALY in self.default_workflow and 
            analysis_options.get("include_anomaly_detection", False)):
            
            try:
                anomaly_params = self._prepare_anomaly_parameters(
                    health_data, analysis_options
                )
                
                if anomaly_params.get("time_series_data"):
                    anomaly_task = AgentTask(
                        agent_type=AgentType.SAGEMAKER_ANOMALY,
                        health_data=health_data,
                        parameters=anomaly_params,
                        timeout_seconds=45
                    )
                    
                    anomaly_response = await self.mcp_server.execute_agent_task(anomaly_task)
                    workflow_results[AgentType.SAGEMAKER_ANOMALY] = anomaly_response
                    
                    logger.info(f"Anomaly detection completed: {anomaly_response.success}")
                
            except (AgentNotFoundError, TaskExecutionError) as e:
                logger.warning(f"Anomaly detection failed: {e}")
        
        return workflow_results
    
    async def _combine_analysis_results(
        self, 
        insight_report: InsightReport, 
        workflow_results: Dict[AgentType, AgentResponse]
    ) -> None:
        """Combine results from multiple agents into comprehensive report."""
        
        all_insights = []
        all_recommendations = []
        risk_assessment = None
        
        # Process results from each agent
        for agent_type, response in workflow_results.items():
            if not response.success or not response.result:
                continue
            
            result = response.result
            
            # Extract insights
            if "insights" in result:
                for insight_data in result["insights"]:
                    insight = self._reconstruct_insight(insight_data)
                    all_insights.append(insight)
            
            # Extract recommendations
            if "recommendations" in result:
                for rec_data in result["recommendations"]:
                    recommendation = self._reconstruct_recommendation(rec_data)
                    all_recommendations.append(recommendation)
            
            # Extract risk assessment (from SageMaker risk agent)
            if agent_type == AgentType.SAGEMAKER_RISK and "risk_assessment" in result:
                risk_assessment = self._reconstruct_risk_assessment(
                    result["risk_assessment"], result.get("risk_factors", [])
                )
        
        # Add combined insights and recommendations to report
        for insight in all_insights:
            insight_report.add_insight(insight)
        
        for recommendation in all_recommendations:
            insight_report.add_recommendation(recommendation)
        
        # Set risk assessment
        insight_report.risk_assessment = risk_assessment
        
        # Add synthesis insight if multiple agents contributed
        if len(workflow_results) > 1:
            synthesis_insight = self._create_synthesis_insight(workflow_results)
            insight_report.add_insight(synthesis_insight)
    
    def _prepare_risk_parameters(
        self, 
        health_data: HealthData, 
        analysis_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare parameters for risk prediction agent."""
        return {
            "age": analysis_options.get("patient_age", 0),
            "gender": analysis_options.get("patient_gender", "unknown"),
            "height_m": analysis_options.get("height_m"),
            "weight_kg": analysis_options.get("weight_kg"),
            "bmi": analysis_options.get("bmi"),
            "smoking": analysis_options.get("smoking", False),
            "exercise_frequency": analysis_options.get("exercise_frequency", 0)
        }
    
    def _prepare_bedrock_parameters(
        self, 
        health_data: HealthData, 
        analysis_options: Dict[str, Any],
        workflow_results: Dict[AgentType, AgentResponse]
    ) -> Dict[str, Any]:
        """Prepare parameters for Bedrock insights agent."""
        params = {
            "analysis_type": "general_insights",
            "focus_areas": analysis_options.get("focus_areas", []),
            "detail_level": analysis_options.get("detail_level", "standard")
        }
        
        # Include risk assessment if available
        if AgentType.SAGEMAKER_RISK in workflow_results:
            risk_response = workflow_results[AgentType.SAGEMAKER_RISK]
            if risk_response.success and risk_response.result:
                params["risk_assessment"] = risk_response.result.get("risk_assessment")
        
        return params
    
    def _prepare_anomaly_parameters(
        self, 
        health_data: HealthData, 
        analysis_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare parameters for anomaly detection agent."""
        return {
            "time_series_data": analysis_options.get("time_series_data"),
            "anomaly_threshold": analysis_options.get("anomaly_threshold", 0.5)
        }
    
    def _calculate_overall_confidence(
        self, 
        workflow_results: Dict[AgentType, AgentResponse]
    ) -> float:
        """Calculate overall confidence score from agent results."""
        
        confidences = []
        
        for response in workflow_results.values():
            if response.success and response.result:
                # Extract confidence from different result types
                if "risk_assessment" in response.result:
                    confidences.append(response.result["risk_assessment"].get("confidence", 0.5))
                elif "insights" in response.result:
                    for insight in response.result["insights"]:
                        confidences.append(insight.get("confidence_score", 0.5))
        
        if not confidences:
            return 0.5  # Default confidence
        
        # Return weighted average (more weight to higher confidences)
        return sum(confidences) / len(confidences)
    
    def _reconstruct_insight(self, insight_data: Dict[str, Any]) -> HealthInsight:
        """Reconstruct HealthInsight from serialized data."""
        return HealthInsight(
            insight_type=InsightType(insight_data["insight_type"]),
            title=insight_data["title"],
            description=insight_data["description"],
            confidence_score=insight_data["confidence_score"],
            supporting_data=insight_data.get("supporting_data", {}),
            generated_at=datetime.fromisoformat(insight_data["generated_at"])
        )
    
    def _reconstruct_recommendation(self, rec_data: Dict[str, Any]) -> Recommendation:
        """Reconstruct Recommendation from serialized data."""
        return Recommendation(
            recommendation_type=RecommendationType(rec_data["recommendation_type"]),
            priority=RecommendationPriority(rec_data["priority"]),
            title=rec_data["title"],
            description=rec_data["description"],
            rationale=rec_data["rationale"],
            expected_outcome=rec_data.get("expected_outcome"),
            timeframe=rec_data.get("timeframe"),
            created_at=datetime.fromisoformat(rec_data["created_at"])
        )
    
    def _reconstruct_risk_assessment(
        self, 
        risk_data: Dict[str, Any], 
        risk_factors_data: List[Dict[str, Any]]
    ) -> RiskAssessment:
        """Reconstruct RiskAssessment from serialized data."""
        from ..domain.value_objects import RiskFactor
        
        risk_factors = []
        for factor_data in risk_factors_data:
            risk_factor = RiskFactor(
                name=factor_data["name"],
                risk_level=RiskLevel(factor_data["risk_level"]),
                probability=factor_data["probability"],
                contributing_factors=factor_data.get("contributing_factors", []),
                mitigation_strategies=factor_data.get("mitigation_strategies", [])
            )
            risk_factors.append(risk_factor)
        
        return RiskAssessment(
            overall_risk_level=RiskLevel(risk_data["overall_risk_level"]),
            risk_factors=risk_factors,
            assessment_summary=f"ML-based risk assessment with score {risk_data.get('risk_score', 0)}",
            confidence_score=risk_data.get("confidence", 0.5),
            assessed_at=datetime.fromisoformat(risk_data["assessment_time"])
        )
    
    def _create_synthesis_insight(
        self, 
        workflow_results: Dict[AgentType, AgentResponse]
    ) -> HealthInsight:
        """Create a synthesis insight combining results from multiple agents."""
        
        successful_agents = [
            agent_type.value for agent_type, response in workflow_results.items()
            if response.success
        ]
        
        description = (
            f"Comprehensive analysis completed using {len(successful_agents)} AI agents: "
            f"{', '.join(successful_agents)}. This multi-agent approach provides "
            f"both quantitative risk assessment and qualitative health insights."
        )
        
        return HealthInsight(
            insight_type=InsightType.GENERAL_HEALTH,
            title="Multi-Agent Health Analysis Summary",
            description=description,
            confidence_score=0.9,
            supporting_data={
                "agents_used": successful_agents,
                "orchestrator_id": self.orchestrator_id,
                "analysis_method": "multi_agent_orchestration"
            }
        )


# Global orchestrator instance
_agent_orchestrator: Optional[AgentOrchestrator] = None


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get or create the global agent orchestrator instance."""
    global _agent_orchestrator
    if _agent_orchestrator is None:
        _agent_orchestrator = AgentOrchestrator()
    return _agent_orchestrator


async def init_agent_orchestrator() -> bool:
    """Initialize the agent orchestrator."""
    try:
        orchestrator = get_agent_orchestrator()
        success = await orchestrator.initialize()
        
        if success:
            logger.info("Agent Orchestrator initialized successfully")
        else:
            logger.error("Failed to initialize Agent Orchestrator")
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to initialize Agent Orchestrator: {e}")
        return False


async def close_agent_orchestrator() -> None:
    """Close the agent orchestrator."""
    global _agent_orchestrator
    if _agent_orchestrator:
        # The orchestrator will be cleaned up when MCP server stops
        logger.info("Agent Orchestrator closed")
        _agent_orchestrator = None