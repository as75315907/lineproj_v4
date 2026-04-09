from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class EventStreamService:
    _condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    _version: int = 0
    _payload: str = 'dashboard_updated'

    async def publish(self, payload: str = 'dashboard_updated') -> None:
        async with self._condition:
            self._version += 1
            self._payload = payload
            self._condition.notify_all()

    async def listen(self, last_version: int = 0):
        while True:
            async with self._condition:
                await self._condition.wait_for(lambda: self._version > last_version)
                last_version = self._version
                payload = self._payload
            yield last_version, payload


event_stream = EventStreamService()
