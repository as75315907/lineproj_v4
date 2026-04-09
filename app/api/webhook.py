from fastapi import APIRouter, Depends, Request

from app.core.deps import get_webhook_handler
from app.schemas.line_events import LineWebhookBody
from app.services.line_service import LineWebhookHandler

router = APIRouter(tags=["webhook"])


@router.get("/")
async def root() -> dict:
    return {"message": "LINE Attendance Bot API"}


@router.post("/webhook/line")
async def line_webhook(
    body: LineWebhookBody,
    request: Request,
    handler: LineWebhookHandler = Depends(get_webhook_handler),
) -> dict:
    # TODO: 驗證 x-line-signature
    _ = request.headers.get("x-line-signature", "")
    for event in body.events:
        await handler.handle_event(event)
    return {"status": "ok", "events": len(body.events)}
