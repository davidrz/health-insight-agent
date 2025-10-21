"""
WebSocket manager for real-time dashboard updates.

This module handles WebSocket connections, manages client subscriptions,
and broadcasts real-time updates to connected dashboard clients.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, List, Any, Optional
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WebSocketMessage(BaseModel):
    """WebSocket message structure."""
    type: str
    data: Dict[str, Any]
    timestamp: datetime
    message_id: str


class ClientConnection:
    """Represents a WebSocket client connection."""
    
    def __init__(self, websocket: WebSocket, client_id: str, patient_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.patient_id = patient_id
        self.connected_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
        self.subscriptions: Set[str] = set()
    
    async def send_message(self, message: WebSocketMessage) -> bool:
        """Send message to client."""
        try:
            await self.websocket.send_text(message.json())
            return True
        except Exception as e:
            logger.warning(f"Failed to send message to client {self.client_id}: {e}")
            return False
    
    async def send_ping(self) -> bool:
        """Send ping to client."""
        ping_message = WebSocketMessage(
            type="ping",
            data={"timestamp": datetime.utcnow().isoformat()},
            timestamp=datetime.utcnow(),
            message_id=str(uuid4())
        )
        return await self.send_message(ping_message)
    
    def update_ping(self):
        """Update last ping timestamp."""
        self.last_ping = datetime.utcnow()
    
    def add_subscription(self, subscription: str):
        """Add subscription to client."""
        self.subscriptions.add(subscription)
    
    def remove_subscription(self, subscription: str):
        """Remove subscription from client."""
        self.subscriptions.discard(subscription)


class DashboardWebSocketManager:
    """Manages WebSocket connections for dashboard real-time updates."""
    
    def __init__(self):
        # Active connections by client_id
        self.connections: Dict[str, ClientConnection] = {}
        
        # Patient subscriptions - maps patient_id to set of client_ids
        self.patient_subscriptions: Dict[str, Set[str]] = {}
        
        # Topic subscriptions - maps topic to set of client_ids
        self.topic_subscriptions: Dict[str, Set[str]] = {}
        
        # Background tasks
        self._ping_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.ping_interval = 30  # seconds
        self.connection_timeout = 300  # 5 minutes
    
    async def connect(
        self, 
        websocket: WebSocket, 
        client_id: str, 
        patient_id: str
    ) -> ClientConnection:
        """Accept WebSocket connection and register client."""
        await websocket.accept()
        
        connection = ClientConnection(websocket, client_id, patient_id)
        self.connections[client_id] = connection
        
        # Subscribe to patient updates
        if patient_id not in self.patient_subscriptions:
            self.patient_subscriptions[patient_id] = set()
        self.patient_subscriptions[patient_id].add(client_id)
        
        # Start background tasks if this is the first connection
        if len(self.connections) == 1:
            await self._start_background_tasks()
        
        logger.info(f"WebSocket client {client_id} connected for patient {patient_id}")
        
        # Send welcome message
        welcome_message = WebSocketMessage(
            type="connection_established",
            data={
                "client_id": client_id,
                "patient_id": patient_id,
                "server_time": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow(),
            message_id=str(uuid4())
        )
        await connection.send_message(welcome_message)
        
        return connection
    
    async def disconnect(self, client_id: str):
        """Disconnect and cleanup client."""
        if client_id not in self.connections:
            return
        
        connection = self.connections[client_id]
        patient_id = connection.patient_id
        
        # Remove from connections
        del self.connections[client_id]
        
        # Remove from patient subscriptions
        if patient_id in self.patient_subscriptions:
            self.patient_subscriptions[patient_id].discard(client_id)
            if not self.patient_subscriptions[patient_id]:
                del self.patient_subscriptions[patient_id]
        
        # Remove from topic subscriptions
        for topic, subscribers in self.topic_subscriptions.items():
            subscribers.discard(client_id)
        
        # Clean up empty topic subscriptions
        empty_topics = [
            topic for topic, subscribers in self.topic_subscriptions.items()
            if not subscribers
        ]
        for topic in empty_topics:
            del self.topic_subscriptions[topic]
        
        # Stop background tasks if no connections remain
        if not self.connections:
            await self._stop_background_tasks()
        
        logger.info(f"WebSocket client {client_id} disconnected")
    
    async def handle_message(self, client_id: str, message_data: str):
        """Handle incoming message from client."""
        if client_id not in self.connections:
            return
        
        try:
            message = json.loads(message_data)
            message_type = message.get("type")
            
            if message_type == "pong":
                # Update ping timestamp
                self.connections[client_id].update_ping()
            
            elif message_type == "subscribe":
                # Subscribe to topic
                topic = message.get("topic")
                if topic:
                    await self._subscribe_client_to_topic(client_id, topic)
            
            elif message_type == "unsubscribe":
                # Unsubscribe from topic
                topic = message.get("topic")
                if topic:
                    await self._unsubscribe_client_from_topic(client_id, topic)
            
            elif message_type == "request_data":
                # Handle data request
                await self._handle_data_request(client_id, message.get("data", {}))
            
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message from client {client_id}")
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
    
    async def broadcast_patient_update(
        self, 
        patient_id: str, 
        update_type: str, 
        data: Dict[str, Any]
    ):
        """Broadcast update to all clients subscribed to a patient."""
        if patient_id not in self.patient_subscriptions:
            return
        
        message = WebSocketMessage(
            type=update_type,
            data={
                "patient_id": patient_id,
                **data
            },
            timestamp=datetime.utcnow(),
            message_id=str(uuid4())
        )
        
        # Send to all subscribed clients
        client_ids = list(self.patient_subscriptions[patient_id])
        await self._broadcast_to_clients(client_ids, message)
        
        logger.info(f"Broadcasted {update_type} update to {len(client_ids)} clients for patient {patient_id}")
    
    async def broadcast_topic_update(
        self, 
        topic: str, 
        update_type: str, 
        data: Dict[str, Any]
    ):
        """Broadcast update to all clients subscribed to a topic."""
        if topic not in self.topic_subscriptions:
            return
        
        message = WebSocketMessage(
            type=update_type,
            data={
                "topic": topic,
                **data
            },
            timestamp=datetime.utcnow(),
            message_id=str(uuid4())
        )
        
        # Send to all subscribed clients
        client_ids = list(self.topic_subscriptions[topic])
        await self._broadcast_to_clients(client_ids, message)
        
        logger.info(f"Broadcasted {update_type} update to {len(client_ids)} clients for topic {topic}")
    
    async def _broadcast_to_clients(
        self, 
        client_ids: List[str], 
        message: WebSocketMessage
    ):
        """Broadcast message to specific clients."""
        if not client_ids:
            return
        
        # Send messages concurrently
        tasks = []
        for client_id in client_ids:
            if client_id in self.connections:
                task = self.connections[client_id].send_message(message)
                tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle failed sends (disconnect clients)
            failed_clients = []
            for i, result in enumerate(results):
                if isinstance(result, Exception) or result is False:
                    failed_clients.append(client_ids[i])
            
            # Disconnect failed clients
            for client_id in failed_clients:
                await self.disconnect(client_id)
    
    async def _subscribe_client_to_topic(self, client_id: str, topic: str):
        """Subscribe client to a topic."""
        if client_id not in self.connections:
            return
        
        if topic not in self.topic_subscriptions:
            self.topic_subscriptions[topic] = set()
        
        self.topic_subscriptions[topic].add(client_id)
        self.connections[client_id].add_subscription(topic)
        
        logger.info(f"Client {client_id} subscribed to topic {topic}")
    
    async def _unsubscribe_client_from_topic(self, client_id: str, topic: str):
        """Unsubscribe client from a topic."""
        if client_id not in self.connections:
            return
        
        if topic in self.topic_subscriptions:
            self.topic_subscriptions[topic].discard(client_id)
            if not self.topic_subscriptions[topic]:
                del self.topic_subscriptions[topic]
        
        self.connections[client_id].remove_subscription(topic)
        
        logger.info(f"Client {client_id} unsubscribed from topic {topic}")
    
    async def _handle_data_request(self, client_id: str, request_data: Dict[str, Any]):
        """Handle data request from client."""
        if client_id not in self.connections:
            return
        
        connection = self.connections[client_id]
        request_type = request_data.get("request_type")
        
        # Handle different request types
        if request_type == "dashboard_refresh":
            # Send dashboard refresh signal
            message = WebSocketMessage(
                type="dashboard_refresh_requested",
                data={"patient_id": connection.patient_id},
                timestamp=datetime.utcnow(),
                message_id=str(uuid4())
            )
            await connection.send_message(message)
    
    async def _start_background_tasks(self):
        """Start background maintenance tasks."""
        if self._ping_task is None or self._ping_task.done():
            self._ping_task = asyncio.create_task(self._ping_clients_loop())
        
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_connections_loop())
    
    async def _stop_background_tasks(self):
        """Stop background maintenance tasks."""
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def _ping_clients_loop(self):
        """Background task to ping clients periodically."""
        while True:
            try:
                await asyncio.sleep(self.ping_interval)
                
                if not self.connections:
                    break
                
                # Send ping to all clients
                ping_tasks = []
                for connection in self.connections.values():
                    ping_tasks.append(connection.send_ping())
                
                if ping_tasks:
                    await asyncio.gather(*ping_tasks, return_exceptions=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
    
    async def _cleanup_connections_loop(self):
        """Background task to cleanup stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                if not self.connections:
                    break
                
                current_time = datetime.utcnow()
                stale_clients = []
                
                for client_id, connection in self.connections.items():
                    time_since_ping = (current_time - connection.last_ping).total_seconds()
                    if time_since_ping > self.connection_timeout:
                        stale_clients.append(client_id)
                
                # Disconnect stale clients
                for client_id in stale_clients:
                    logger.info(f"Disconnecting stale client {client_id}")
                    await self.disconnect(client_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return {
            "total_connections": len(self.connections),
            "patient_subscriptions": len(self.patient_subscriptions),
            "topic_subscriptions": len(self.topic_subscriptions),
            "active_patients": list(self.patient_subscriptions.keys()),
            "active_topics": list(self.topic_subscriptions.keys())
        }


# Global WebSocket manager instance
websocket_manager = DashboardWebSocketManager()