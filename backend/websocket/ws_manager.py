"""WebSocket connection manager for real-time job updates."""
import logging
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_new_job(self, job_data: Dict[str, Any]):
        """Broadcast a new job notification."""
        await self.broadcast({
            "type": "new_job",
            "data": job_data
        })

    async def send_crawl_status(self, status: str, count: int = 0):
        """Broadcast crawler status update."""
        await self.broadcast({
            "type": "crawl_status",
            "status": status,
            "count": count
        })


manager = ConnectionManager()
