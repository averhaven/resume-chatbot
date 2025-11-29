from pydantic import BaseModel


class WebSocketMessage(BaseModel):
    """WebSocket message format for communication

    Attributes:
        type: Message type (e.g., 'echo', 'chat', 'system', 'error')
        data: Message content/payload
    """
    type: str
    data: str
