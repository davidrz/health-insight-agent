"""
Base classes and interfaces for AI agents in the Health Insight Agent system.

This module defines the core abstractions for health analysis agents
that can be orchestrated through the MCP server.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from uuid import UUID, uuid4

from ..domain.entities import HealthData
from ..domain.value_objects import InsightReport


class AgentStatus(Enum):
    """Status of an AI agent."""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


class AgentType(Enum):
    """Types of health analysis agents."""
    BEDROCK_INSIGHTS = "bedrock_insights"
    SAGEMAKER_RISK = "sagemaker_risk"
    SAGEMAKER_ANOMALY = "sagemaker_anomaly"
    COMPOSITE_ANALYSIS = "composite_analysis"


@dataclass
class AgentTask:
    """Represents a task to be executed by an agent."""
    
    task_id: UUID = field(default_factory=uuid4)
    agent_type: AgentType = AgentType.BEDROCK_INSIGHTS
    health_data: Optional[HealthData] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # 1 = highest, 5 = lowest
    created_at: datetime = field(default_factory=datetime.utcnow)
    timeout_seconds: int = 30
    
    def __post_init__(self):
        """Validate agent task data."""
        if self.priority < 1 or self.priority > 5:
            raise ValueError("Priority must be between 1 and 5")
        
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")


@dataclass
class AgentResponse:
    """Response from an agent task execution."""
    
    task_id: UUID
    agent_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: int = 0
    completed_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class HealthAgent(ABC):
    """Abstract base class for health analysis agents."""
    
    def __init__(self, agent_id: str, agent_type: AgentType):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.status = AgentStatus.IDLE
        self.last_activity = datetime.utcnow()
        self.error_count = 0
        self.total_tasks = 0
        self.successful_tasks = 0
    
    @abstractmethod
    async def execute_task(self, task: AgentTask) -> AgentResponse:
        """
        Execute a health analysis task.
        
        Args:
            task: The task to execute
            
        Returns:
            AgentResponse: Result of the task execution
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the agent.
        
        Returns:
            Dict containing health status information
        """
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status and statistics."""
        success_rate = (
            self.successful_tasks / self.total_tasks 
            if self.total_tasks > 0 else 0.0
        )
        
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "status": self.status.value,
            "last_activity": self.last_activity.isoformat(),
            "error_count": self.error_count,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "success_rate": success_rate
        }
    
    def _update_task_stats(self, success: bool):
        """Update task execution statistics."""
        self.total_tasks += 1
        if success:
            self.successful_tasks += 1
        else:
            self.error_count += 1
        
        self.last_activity = datetime.utcnow()
    
    def _set_status(self, status: AgentStatus):
        """Update agent status."""
        self.status = status
        self.last_activity = datetime.utcnow()


class AgentRegistry:
    """Registry for managing health analysis agents."""
    
    def __init__(self):
        self._agents: Dict[str, HealthAgent] = {}
        self._agents_by_type: Dict[AgentType, List[HealthAgent]] = {}
    
    def register_agent(self, agent: HealthAgent) -> None:
        """
        Register a new health analysis agent.
        
        Args:
            agent: The agent to register
            
        Raises:
            ValueError: If agent ID already exists
        """
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent with ID {agent.agent_id} already registered")
        
        self._agents[agent.agent_id] = agent
        
        if agent.agent_type not in self._agents_by_type:
            self._agents_by_type[agent.agent_type] = []
        
        self._agents_by_type[agent.agent_type].append(agent)
    
    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.
        
        Args:
            agent_id: ID of the agent to unregister
            
        Returns:
            bool: True if agent was found and removed
        """
        if agent_id not in self._agents:
            return False
        
        agent = self._agents[agent_id]
        del self._agents[agent_id]
        
        if agent.agent_type in self._agents_by_type:
            self._agents_by_type[agent.agent_type] = [
                a for a in self._agents_by_type[agent.agent_type] 
                if a.agent_id != agent_id
            ]
        
        return True
    
    def get_agent(self, agent_id: str) -> Optional[HealthAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_agents_by_type(self, agent_type: AgentType) -> List[HealthAgent]:
        """Get all agents of a specific type."""
        return self._agents_by_type.get(agent_type, [])
    
    def get_available_agent(self, agent_type: AgentType) -> Optional[HealthAgent]:
        """
        Get an available agent of the specified type.
        
        Args:
            agent_type: Type of agent needed
            
        Returns:
            HealthAgent: Available agent or None if none available
        """
        agents = self.get_agents_by_type(agent_type)
        
        # Find idle agents first
        for agent in agents:
            if agent.status == AgentStatus.IDLE:
                return agent
        
        # If no idle agents, return any non-error agent
        for agent in agents:
            if agent.status != AgentStatus.ERROR:
                return agent
        
        return None
    
    def get_all_agents(self) -> List[HealthAgent]:
        """Get all registered agents."""
        return list(self._agents.values())
    
    def get_agent_status_summary(self) -> Dict[str, Any]:
        """Get summary of all agent statuses."""
        total_agents = len(self._agents)
        status_counts = {}
        
        for agent in self._agents.values():
            status = agent.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_agents": total_agents,
            "status_counts": status_counts,
            "agents_by_type": {
                agent_type.value: len(agents) 
                for agent_type, agents in self._agents_by_type.items()
            }
        }