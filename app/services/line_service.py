from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import AttendanceAction
from app.schemas.attendance import AttendanceContext
from app.schemas.line_events import LineEvent
from app.services.attendance_service import AttendanceService
from app.services.db_service import DatabaseService
from app.services.signup_service import SignupService
from app.utils.cache import webhook_event_cache

logger = get_logger(__name__)


class LineBotService:
    def __init__(self) -> None:
        self.base_headers = {
            "Authorization": f"Bearer {settings.line_channel_access_token}",
            "Content-Type": "application/json",
        }

    async def reply_text(self, reply_token: str, text: str) -> None:
        if not reply_token:
            return
        payload = {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
        await self._post("https://api.line.me/v2/bot/message/reply", payload)

    async def push_shift_form(self, to_id: str) -> None:
        payload = {
            "to": to_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": "明日班別報名（請點選按鈕）",
                    "contents": {
                        "type": "bubble",
                        "header": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": "明日班別報名", "weight": "bold", "size": "xl", "color": "#ffffff"}
                            ],
                            "backgroundColor": "#00b900",
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {"type": "text", "text": "報名時間：21:00 - 00:00", "size": "xs", "color": "#aaaaaa"},
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "早班 07:00",
                                        "data": "shift=早7",
                                        "displayText": "報名：早班 07:00",
                                    },
                                    "style": "primary",
                                    "margin": "md",
                                    "color": "#1db446",
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "postback",
                                        "label": "晚班 22:00",
                                        "data": "shift=晚10",
                                        "displayText": "報名：晚班 22:00",
                                    },
                                    "style": "primary",
                                    "margin": "md",
                                    "color": "#1db446",
                                },
                            ],
                        },
                    },
                }
            ],
        }
        await self._post("https://api.line.me/v2/bot/message/push", payload)

    async def push_attendance_card(self, to_id: str) -> None:
        payload = {
            "to": to_id,
            "messages": [
                {
                    "type": "flex",
                    "altText": "今日出勤打卡（請點按鈕）",
                    "contents": {
                        "type": "bubble",
                        "header": {
                            "type": "box",
                            "layout": "vertical",
                            "backgroundColor": "#111111",
                            "contents": [
                                {"type": "text", "text": "今日出勤打卡", "size": "xl", "weight": "bold", "color": "#ffffff"}
                            ],
                        },
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "md",
                            "contents": [
                                {"type": "text", "text": "請依序點選按鈕（系統自動記錄時間）", "size": "sm", "color": "#666666"},
                                {"type": "button", "style": "primary", "color": "#1db446", "action": {"type": "postback", "label": "✅ 上班打卡", "data": "att=IN", "displayText": "上班打卡"}},
                                {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "🍱 休息開始", "data": "att=BREAK_START", "displayText": "休息開始"}},
                                {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "⏱️ 休息結束", "data": "att=BREAK_END", "displayText": "休息結束"}},
                                {"type": "button", "style": "primary", "color": "#ff4d4f", "action": {"type": "postback", "label": "🏁 下班打卡", "data": "att=OUT", "displayText": "下班打卡"}},
                            ],
                        },
                    },
                }
            ],
        }
        await self._post("https://api.line.me/v2/bot/message/push", payload)

    async def get_group_member_name(self, group_id: str, user_id: str) -> Optional[str]:
        if not group_id or not user_id or not settings.line_channel_access_token:
            return None
        url = f"https://api.line.me/v2/bot/group/{group_id}/member/{user_id}"
        return await self._fetch_display_name(url)

    async def get_user_name(self, user_id: str) -> Optional[str]:
        if not user_id or not settings.line_channel_access_token:
            return None
        url = f"https://api.line.me/v2/bot/profile/{user_id}"
        return await self._fetch_display_name(url)

    async def _fetch_display_name(self, url: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url, headers={"Authorization": self.base_headers["Authorization"]})
            if res.status_code != 200:
                logger.warning("LINE get profile failed: %s %s", res.status_code, res.text)
                return None
            return res.json().get("displayName")

    async def _post(self, url: str, payload: Dict[str, Any]) -> None:
        if not settings.line_channel_access_token:
            logger.info("LINE token missing, skip POST %s", url)
            return
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(url, headers=self.base_headers, json=payload)
            logger.info("LINE POST %s -> %s", url, res.status_code)
            if res.status_code >= 400:
                logger.warning("LINE response body: %s", res.text)


class LineWebhookHandler:
    def __init__(
        self,
        line_service: LineBotService,
        signup_service: SignupService,
        attendance_service: AttendanceService,
        db_service: DatabaseService,
        event_stream,
        employee_service=None,
    ) -> None:
        self.line_service = line_service
        self.signup_service = signup_service
        self.attendance_service = attendance_service
        self.db = db_service
        self.event_stream = event_stream
        self.employee_service = employee_service

    async def handle_event(self, event: LineEvent) -> None:
        if event.webhookEventId:
            if event.webhookEventId in webhook_event_cache or self.db.is_duplicate_webhook(event.webhookEventId):
                logger.info("duplicate webhook ignored: %s", event.webhookEventId)
                return
            webhook_event_cache[event.webhookEventId] = True
            self.db.save_webhook_event(event.webhookEventId, event.type, event.model_dump_json())

        source = event.source
        group_id = source.groupId if source else ""
        user_id = source.userId if source else ""
        reply_token = event.replyToken or ""

        self.db.add_log("INFO", "event.type", f"type={event.type} user={user_id} group={group_id}")

        if event.type == "message" and event.message and event.message.type == "text":
            text = (event.message.text or "").strip()
            self.db.add_log("INFO", "message.text", text)
            await self._handle_text_message(text, group_id, user_id, reply_token, event)
            return

        if event.type == "postback" and event.postback and event.postback.data:
            self.db.add_log("INFO", "postback.data", event.postback.data)
            await self._handle_postback(event.postback.data.strip(), group_id, user_id, reply_token, event)
            return

        logger.info("Unhandled event: %s", event.model_dump())

    async def _handle_text_message(self, text: str, group_id: str, user_id: str, reply_token: str, event: LineEvent) -> None:
        if text == "報班":
            name = await self._resolve_user_name(group_id, user_id)
            self._ensure_employee(user_id, name, group_id)
            await self.line_service.push_shift_form(group_id or user_id)
            await self.line_service.reply_text(reply_token, "✅ 已重新推播報班表單")
            return

        if text == "打卡":
            name = await self._resolve_user_name(group_id, user_id)
            self._ensure_employee(user_id, name, group_id)
            await self.line_service.push_attendance_card(group_id or user_id)
            await self.line_service.reply_text(reply_token, "✅ 已推播今日出勤打卡按鈕")
            return

        action_map = {
            "上班打卡": AttendanceAction.IN,
            "休息開始": AttendanceAction.BREAK_START,
            "休息結束": AttendanceAction.BREAK_END,
            "下班打卡": AttendanceAction.OUT,
        }
        if text in action_map:
            name = await self._resolve_user_name(group_id, user_id)
            self._ensure_employee(user_id, name, group_id)
            event_time = self._resolve_event_time(event.timestamp)
            result = self.attendance_service.handle_attendance(
                AttendanceContext(uid=user_id, name=name, group_id=group_id, action=action_map[text], event_time=event_time)
            )
            self._update_employee_shift(user_id, event_time.strftime("%Y-%m-%d"))
            await self.line_service.reply_text(reply_token, result.message)
            await self.event_stream.publish("dashboard_updated")

    async def _handle_postback(self, data: str, group_id: str, user_id: str, reply_token: str, event: LineEvent) -> None:
        if data.startswith("att="):
            action_str = data.replace("att=", "")
            name = await self._resolve_user_name(group_id, user_id)
            self._ensure_employee(user_id, name, group_id)
            event_time = self._resolve_event_time(event.timestamp)
            result = self.attendance_service.handle_attendance(
                AttendanceContext(uid=user_id, name=name, group_id=group_id, action=AttendanceAction(action_str), event_time=event_time)
            )
            self._update_employee_shift(user_id, event_time.strftime("%Y-%m-%d"))
            await self.line_service.reply_text(reply_token, result.message)
            await self.event_stream.publish("dashboard_updated")
            return

        if data.startswith("shift="):
            name = await self._resolve_user_name(group_id, user_id)
            self._ensure_employee(user_id, name, group_id)
            result = self.signup_service.upsert_signup(uid=user_id, name=name, group_id=group_id, raw_shift=data)
            if result.get("shift_text"):
                self._update_employee_latest_shift(user_id, result["shift_text"])
            await self.line_service.reply_text(reply_token, result["message"])
            await self.event_stream.publish("dashboard_updated")

    async def _resolve_user_name(self, group_id: str, user_id: str) -> str:
        return (
            await self.line_service.get_group_member_name(group_id, user_id)
            or await self.line_service.get_user_name(user_id)
            or (f"使用者-{user_id[:6]}" if user_id else "匿名員工")
        )

    def _ensure_employee(self, uid: str, name: str, group_id: str) -> None:
        if self.employee_service and uid:
            self.employee_service.ensure_employee(uid, name, group_id)

    def _update_employee_latest_shift(self, uid: str, latest_shift: str) -> None:
        if self.employee_service and uid and latest_shift:
            self.employee_service.db.update_employee_latest_shift(uid, latest_shift)

    def _update_employee_shift(self, uid: str, work_date: str) -> None:
        if not self.employee_service or not uid or not work_date:
            return
        shift = self.db.get_shift_for_date(uid, work_date)
        if shift:
            self.employee_service.db.update_employee_latest_shift(uid, shift)

    @staticmethod
    def _resolve_event_time(timestamp_ms: Optional[int]) -> datetime:
        if not timestamp_ms:
            return datetime.now(ZoneInfo(settings.timezone))
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=ZoneInfo(settings.timezone))