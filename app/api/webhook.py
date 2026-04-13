from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.deps import get_webhook_handler
from app.core.security import verify_line_signature
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
    signature = request.headers.get("x-line-signature", "")
    raw_body = await request.body()
    if not verify_line_signature(raw_body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid line signature")
    for event in body.events:
        await handler.handle_event(event)
    return {"status": "ok", "events": len(body.events)}
