from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class LineSource(BaseModel):
    userId: Optional[str] = None
    groupId: Optional[str] = None
    type: Optional[str] = None


class LineMessage(BaseModel):
    type: Optional[str] = None
    text: Optional[str] = None


class LinePostback(BaseModel):
    data: Optional[str] = None


class LineEvent(BaseModel):
    type: str
    replyToken: Optional[str] = None
    timestamp: Optional[int] = None
    webhookEventId: Optional[str] = None
    source: Optional[LineSource] = None
    message: Optional[LineMessage] = None
    postback: Optional[LinePostback] = None


class LineWebhookBody(BaseModel):
    destination: Optional[str] = None
    events: List[LineEvent] = []


class GenericLinePayload(BaseModel):
    to: str
    messages: List[Dict[str, Any]]
