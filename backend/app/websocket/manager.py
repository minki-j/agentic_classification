from typing import Dict, List, Set
from fastapi import WebSocket
import json
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Active connections per user(user_id, websocket)
        self.active_connections: Dict[str, WebSocket] = {}
        # Keep-alive tasks per user
        self.keepalive_tasks: Dict[str, asyncio.Task] = {}

    async def _keepalive_loop(self, websocket: WebSocket, user_id: str):
        """Send periodic ping messages to keep the connection alive"""
        try:
            while user_id in self.active_connections:
                await asyncio.sleep(30)  # Send ping every 30 seconds
                if user_id in self.active_connections:
                    try:
                        await self.send_directly_with_websocket(
                            {
                                "type": "ping",
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            websocket,
                        )
                        logger.debug(f"Sent keepalive ping to user {user_id}")
                    except Exception as e:
                        logger.error(
                            f"Failed to send keepalive ping to user {user_id}: {e}"
                        )
                        break
        except asyncio.CancelledError:
            logger.debug(f"Keepalive task cancelled for user {user_id}")
        except Exception as e:
            logger.error(f"Error in keepalive loop for user {user_id}: {e}")

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and store WebSocket connection"""
        await websocket.accept()
        self.active_connections[user_id] = websocket

        # Start keepalive task
        self.keepalive_tasks[user_id] = asyncio.create_task(
            self._keepalive_loop(websocket, user_id)
        )

        logger.info(
            f"User {user_id} connected. Total active connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]

            # Cancel keepalive task
            if user_id in self.keepalive_tasks:
                self.keepalive_tasks[user_id].cancel()
                del self.keepalive_tasks[user_id]

            logger.info(
                f"User {user_id} disconnected. Remaining connections: {len(self.active_connections)}"
            )

    async def send_directly_with_websocket(self, message: dict, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message directly to websocket: {e}")
            raise  # Re-raise to let caller handle it

    async def send_to_user(self, message: dict, user_id: str):
        """Send message to all connections of a specific user"""
        if user_id in self.active_connections:
            try:
                websocket = self.active_connections[user_id]
                # Check if websocket is still open before sending
                if (
                    websocket.client_state.name == "CONNECTED"
                    and websocket.application_state.name == "CONNECTED"
                ):
                    await websocket.send_json(message)
                else:
                    logger.warning(
                        f"WebSocket for user {user_id} is not in CONNECTED state. Client: {websocket.client_state.name}, App: {websocket.application_state.name}"
                    )
                    del self.active_connections[user_id]
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                logger.error(f"Removing connection for user {user_id} due to error")
                del self.active_connections[user_id]
        else:
            logger.warning(
                f"User {user_id} not found in active connections. Active connections: {list(self.active_connections.keys())}"
            )

    async def send_initialization_update(self, user_id: str, data: dict):
        """Send initialize nodes update to subscribed users"""
        message = {
            "type": "initialization_update",
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.send_to_user(message, user_id)

    async def send_classification_update(self, user_id: str, data: dict):
        """Send classification progress update to subscribed users"""
        message = {
            "type": "classification_update",
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.send_to_user(message, user_id)

    async def send_examination_update(self, user_id: str, data: dict):
        """Send examination progress update to subscribed users"""
        message = {
            "type": "examination_update",
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.send_to_user(message, user_id)

    async def send_dspy_update(self, user_id: str, data: dict):
        """Send dspy update to subscribed users"""
        message = {
            "type": "dspy_update",
            "data": data,
        }
        await self.send_to_user(message, user_id)

    async def send_error_message(self, user_id: str, data: dict):
        """Send error message to subscribed users"""
        message = {
            "type": "error",
            "data": data,
        }
        await self.send_to_user(message, user_id)

    async def send_custom_type_message(self, user_id: str, type: str, data: dict):
        """Send agent info messages (from _handle_stream_chunk)"""
        message = {
            "type": type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.send_to_user(message, user_id)

    async def disconnect_all(self):
        """Disconnect all active connections"""
        # Cancel all keepalive tasks first
        for user_id, task in list(self.keepalive_tasks.items()):
            task.cancel()
        self.keepalive_tasks.clear()

        # Close all websocket connections
        for user_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.close()
            except Exception:
                pass
        self.active_connections.clear()

    def get_connection_info(self) -> dict:
        """Get information about current connections for debugging"""
        info = {
            "total_connections": len(self.active_connections),
            "users": list(self.active_connections.keys()),
            "connection_states": {},
        }
        for user_id, ws in self.active_connections.items():
            try:
                info["connection_states"][user_id] = {
                    "client_state": ws.client_state.name,
                    "application_state": ws.application_state.name,
                }
            except Exception as e:
                info["connection_states"][user_id] = f"Error getting state: {e}"
        return info


# Global connection manager instance
connection_manager = ConnectionManager()
