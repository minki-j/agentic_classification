from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from jose import JWTError

from app.core.security import verify_token
from app.websocket.manager import connection_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_current_user_ws(
    websocket: WebSocket, token: Optional[str] = Query(None)
) -> Optional[str]:
    """Authenticate WebSocket connection using query parameter token"""
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return None

    try:
        user_id = verify_token(token, token_type="access")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return None
        return user_id
    except JWTError:
        await websocket.close(code=1008, reason="Invalid token")
        return None


@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    WebSocket endpoint for real-time classification updates

    The 'websocket' parameter is automatically injected by the FastAPI framework when a WebSocket connection is established from the frontend like this:

    ```javascript
    const ws = new WebSocket(wsUrl);
    ```

    The websocket object represent the bidirectional connection between client and server, sending and receiving messages like this:

    ``` python
    # Receive message from client
    data = await websocket.receive_json()

    # Send message to client
    websocket.send_json({"type": "subscribe", "session_id": "123"})
    ```

    Since there can be multiple connections, we separate the logic into a manager class that handles the connections and messages. This endpoint serves as the entry point for the websocket connection, and also keep receiving messages from the client in a infinite loop.
    """
    # Authenticate
    user_id = await get_current_user_ws(websocket, token)
    if not user_id:
        return

    logger.info(f"WebSocket authenticated for user {user_id}")

    # Connect
    await connection_manager.connect(websocket, user_id)

    try:
        while True:
            # Wait for messages from client
            logger.debug(f"Waiting for message from user {user_id}")
            data = await websocket.receive_json()
            logger.debug(f"Received message from user {user_id}: {data}")

            # Handle different message types
            message_type = data.get("type")

            if message_type == "ping":
                # Respond to ping with pong
                await connection_manager.send_directly_with_websocket(
                    {"type": "pong", "timestamp": data.get("timestamp")}, websocket
                )

            elif message_type == "pong":
                # Acknowledge pong response from client
                logger.debug(f"Received pong from user {user_id}")

            else:
                # Unknown message type
                await connection_manager.send_directly_with_websocket(
                    {
                        "type": "error",
                        "error": f"Unknown message type: {message_type}",
                        "timestamp": data.get("timestamp"),
                    },
                    websocket,
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket disconnected for user {user_id} (WebSocketDisconnect)")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}", exc_info=True)
        connection_manager.disconnect(websocket, user_id)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            logger.error(f"Failed to close websocket for user {user_id}")
