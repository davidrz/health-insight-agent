"""
Model Context Protocol (MCP) server for AI agent communication.

This module implements the MCP server that handles communication
between different AI agents in the Health Insight Agent system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from uuid import UUID, uuid4
import json

from .base import (
    HealthAgent, AgentTask, AgentResponse, AgentRegistry, 
    AgentStatus, AgentType
)

logger = logging.getLogger(__name__)


from app.core.exceptions import ExternalServiceError, NotFoundError, BusinessLogicError

class MCPServerError(ExternalServiceError):
    """Base exception for MCP server errors."""
    pass


class AgentNotFoundError(NotFoundError):
    """Raised when requested agent is not found."""
    pass


class TaskExecutionError(BusinessLogicError):
    """Raised when task execution fails."""
    pass


class MCPServer:
    """Model Context Protocol server for AI agent communication."""
    
    def __init__(self):
        self.server_id = str(uuid4())
        self.agent_registry = AgentRegistry()
        self.active_tasks: Dict[UUID, AgentTask] = {}
        self.task_results: Dict[UUID, AgentResponse] = {}
        self.task_callbacks: Dict[UUID, Callable] = {}
        self.started_at = datetime.utcnow()
        self.is_running = False
        
        # Task execution statistics
        self.total_tasks_executed = 0
        self.successful_tasks = 0
        self.failed_tasks = 0
        
        logger.info(f"MCP Server initialized with ID: {self.server_id}")
    
    async def start(self) -> None:
        """Start the MCP server."""
        if self.is_running:
            logger.warning("MCP Server is already running")
            return
        
        self.is_running = True
        logger.info("MCP Server started successfully")
        
        # Start background task cleanup
        asyncio.create_task(self._cleanup_completed_tasks())
    
    async def stop(self) -> None:
        """Stop the MCP server."""
        if not self.is_running:
            logger.warning("MCP Server is not running")
            return
        
        self.is_running = False
        
        # Cancel all active tasks
        for task_id in list(self.active_tasks.keys()):
            await self._cancel_task(task_id)
        
        logger.info("MCP Server stopped")
    
    async def register_agent(self, agent: HealthAgent) -> None:
        """
        Register a new health analysis agent.
        
        Args:
            agent: The agent to register
            
        Raises:
            MCPServerError: If registration fails
        """
        try:
            self.agent_registry.register_agent(agent)
            
            # Perform initial health check
            health_status = await agent.health_check()
            
            logger.info(
                f"Agent registered: {agent.agent_id} "
                f"(type: {agent.agent_type.value}, "
                f"status: {health_status.get('status', 'unknown')})"
            )
            
        except Exception as e:
            logger.error(f"Failed to register agent {agent.agent_id}: {e}")
            raise MCPServerError(f"Agent registration failed: {e}")
    
    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.
        
        Args:
            agent_id: ID of the agent to unregister
            
        Returns:
            bool: True if agent was found and removed
        """
        # Cancel any active tasks for this agent
        tasks_to_cancel = [
            task_id for task_id, task in self.active_tasks.items()
            if self._get_task_agent_id(task) == agent_id
        ]
        
        for task_id in tasks_to_cancel:
            await self._cancel_task(task_id)
        
        success = self.agent_registry.unregister_agent(agent_id)
        
        if success:
            logger.info(f"Agent unregistered: {agent_id}")
        else:
            logger.warning(f"Agent not found for unregistration: {agent_id}")
        
        return success
    
    async def execute_agent_task(self, task: AgentTask) -> AgentResponse:
        """
        Execute a specific analysis task through an agent.
        
        Args:
            task: The task to execute
            
        Returns:
            AgentResponse: Result of the task execution
            
        Raises:
            AgentNotFoundError: If no suitable agent is available
            TaskExecutionError: If task execution fails
        """
        if not self.is_running:
            raise MCPServerError("MCP Server is not running")
        
        # Find available agent for the task
        agent = self.agent_registry.get_available_agent(task.agent_type)
        if not agent:
            raise AgentNotFoundError(
                f"No available agent found for type: {task.agent_type.value}"
            )
        
        # Add task to active tasks
        self.active_tasks[task.task_id] = task
        
        try:
            logger.info(
                f"Executing task {task.task_id} with agent {agent.agent_id} "
                f"(type: {task.agent_type.value})"
            )
            
            # Set agent status to running
            agent._set_status(AgentStatus.RUNNING)
            
            # Execute the task with timeout
            response = await asyncio.wait_for(
                agent.execute_task(task),
                timeout=task.timeout_seconds
            )
            
            # Update statistics
            self.total_tasks_executed += 1
            if response.success:
                self.successful_tasks += 1
            else:
                self.failed_tasks += 1
            
            # Store result
            self.task_results[task.task_id] = response
            
            # Set agent back to idle
            agent._set_status(AgentStatus.IDLE)
            
            logger.info(
                f"Task {task.task_id} completed successfully "
                f"(execution time: {response.execution_time_ms}ms)"
            )
            
            return response
            
        except asyncio.TimeoutError:
            error_msg = f"Task {task.task_id} timed out after {task.timeout_seconds}s"
            logger.error(error_msg)
            
            agent._set_status(AgentStatus.ERROR)
            self.failed_tasks += 1
            
            response = AgentResponse(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                success=False,
                error_message=error_msg
            )
            
            self.task_results[task.task_id] = response
            raise TaskExecutionError(error_msg)
            
        except Exception as e:
            error_msg = f"Task {task.task_id} execution failed: {e}"
            logger.error(error_msg)
            
            agent._set_status(AgentStatus.ERROR)
            self.failed_tasks += 1
            
            response = AgentResponse(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                success=False,
                error_message=str(e)
            )
            
            self.task_results[task.task_id] = response
            raise TaskExecutionError(error_msg)
            
        finally:
            # Remove from active tasks
            self.active_tasks.pop(task.task_id, None)
    
    async def execute_agent_task_async(
        self, 
        task: AgentTask, 
        callback: Optional[Callable[[AgentResponse], None]] = None
    ) -> UUID:
        """
        Execute a task asynchronously and return task ID immediately.
        
        Args:
            task: The task to execute
            callback: Optional callback function for when task completes
            
        Returns:
            UUID: Task ID for tracking
        """
        if callback:
            self.task_callbacks[task.task_id] = callback
        
        # Start task execution in background
        asyncio.create_task(self._execute_task_with_callback(task))
        
        return task.task_id
    
    async def get_task_result(self, task_id: UUID) -> Optional[AgentResponse]:
        """
        Get the result of a completed task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            AgentResponse: Task result or None if not found/completed
        """
        return self.task_results.get(task_id)
    
    async def get_task_status(self, task_id: UUID) -> Dict[str, Any]:
        """
        Get the status of a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Dict containing task status information
        """
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "task_id": str(task_id),
                "status": "running",
                "agent_type": task.agent_type.value,
                "created_at": task.created_at.isoformat(),
                "timeout_seconds": task.timeout_seconds
            }
        elif task_id in self.task_results:
            result = self.task_results[task_id]
            return {
                "task_id": str(task_id),
                "status": "completed",
                "success": result.success,
                "completed_at": result.completed_at.isoformat(),
                "execution_time_ms": result.execution_time_ms
            }
        else:
            return {
                "task_id": str(task_id),
                "status": "not_found"
            }
    
    async def get_agent_status(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get status of agents.
        
        Args:
            agent_id: Specific agent ID, or None for all agents
            
        Returns:
            Dict containing agent status information
        """
        if agent_id:
            agent = self.agent_registry.get_agent(agent_id)
            if not agent:
                raise AgentNotFoundError(f"Agent not found: {agent_id}")
            
            return agent.get_status()
        else:
            return self.agent_registry.get_agent_status_summary()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on MCP server and all agents.
        
        Returns:
            Dict containing health check results
        """
        server_health = {
            "server_id": self.server_id,
            "status": "healthy" if self.is_running else "stopped",
            "uptime_seconds": (datetime.utcnow() - self.started_at).total_seconds(),
            "total_tasks_executed": self.total_tasks_executed,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": (
                self.successful_tasks / self.total_tasks_executed 
                if self.total_tasks_executed > 0 else 0.0
            ),
            "active_tasks": len(self.active_tasks),
            "agents": {}
        }
        
        # Check health of all agents
        for agent in self.agent_registry.get_all_agents():
            try:
                agent_health = await agent.health_check()
                server_health["agents"][agent.agent_id] = {
                    "status": agent_health.get("status", "unknown"),
                    "agent_type": agent.agent_type.value,
                    "last_activity": agent.last_activity.isoformat(),
                    "health_details": agent_health
                }
            except Exception as e:
                server_health["agents"][agent.agent_id] = {
                    "status": "error",
                    "agent_type": agent.agent_type.value,
                    "error": str(e)
                }
        
        return server_health
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "server_id": self.server_id,
            "is_running": self.is_running,
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": (datetime.utcnow() - self.started_at).total_seconds(),
            "total_tasks_executed": self.total_tasks_executed,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "active_tasks": len(self.active_tasks),
            "cached_results": len(self.task_results),
            "registered_agents": len(self.agent_registry.get_all_agents())
        }
    
    async def _execute_task_with_callback(self, task: AgentTask) -> None:
        """Execute task and call callback if provided."""
        try:
            response = await self.execute_agent_task(task)
            
            # Call callback if provided
            callback = self.task_callbacks.get(task.task_id)
            if callback:
                try:
                    callback(response)
                except Exception as e:
                    logger.error(f"Callback execution failed for task {task.task_id}: {e}")
                finally:
                    self.task_callbacks.pop(task.task_id, None)
                    
        except Exception as e:
            logger.error(f"Async task execution failed for {task.task_id}: {e}")
            
            # Still call callback with error response
            callback = self.task_callbacks.get(task.task_id)
            if callback:
                try:
                    error_response = AgentResponse(
                        task_id=task.task_id,
                        agent_id="unknown",
                        success=False,
                        error_message=str(e)
                    )
                    callback(error_response)
                except Exception as callback_error:
                    logger.error(f"Callback execution failed: {callback_error}")
                finally:
                    self.task_callbacks.pop(task.task_id, None)
    
    async def _cancel_task(self, task_id: UUID) -> None:
        """Cancel an active task."""
        if task_id in self.active_tasks:
            logger.info(f"Cancelling task: {task_id}")
            self.active_tasks.pop(task_id, None)
            self.task_callbacks.pop(task_id, None)
    
    def _get_task_agent_id(self, task: AgentTask) -> str:
        """Get the agent ID that would handle this task."""
        agent = self.agent_registry.get_available_agent(task.agent_type)
        return agent.agent_id if agent else "unknown"
    
    async def _cleanup_completed_tasks(self) -> None:
        """Background task to clean up old completed tasks."""
        while self.is_running:
            try:
                # Clean up task results older than 1 hour
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                
                tasks_to_remove = [
                    task_id for task_id, result in self.task_results.items()
                    if result.completed_at < cutoff_time
                ]
                
                for task_id in tasks_to_remove:
                    self.task_results.pop(task_id, None)
                    self.task_callbacks.pop(task_id, None)
                
                if tasks_to_remove:
                    logger.debug(f"Cleaned up {len(tasks_to_remove)} old task results")
                
                # Sleep for 10 minutes before next cleanup
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"Task cleanup error: {e}")
                await asyncio.sleep(60)  # Shorter sleep on error


# Global MCP server instance
_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Get or create the global MCP server instance."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server


async def init_mcp_server() -> bool:
    """Initialize and start the MCP server."""
    try:
        server = get_mcp_server()
        await server.start()
        
        logger.info("MCP Server initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP Server: {e}")
        return False


async def close_mcp_server() -> None:
    """Stop and close the MCP server."""
    global _mcp_server
    if _mcp_server:
        await _mcp_server.stop()
        logger.info("MCP Server closed")
        _mcp_server = None