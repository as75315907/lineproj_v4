from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.core.deps import get_admin_dashboard_service, get_export_service, get_sync_service
from app.services.admin_dashboard_service import AdminDashboardService
from app.services.event_stream_service import event_stream
from app.services.export_service import ExportService
from app.services.sync_service import SyncService

router = APIRouter(prefix='/admin', tags=['admin'])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / 'templates'))


@router.get('', response_class=HTMLResponse)
async def admin_index(request: Request):
    return templates.TemplateResponse(request, 'admin.html', {'payload': {}, 'page_title': 'LINE 報班 / 打卡管理後台'})


@router.get('/api/dashboard')
async def admin_dashboard_api(date: str | None = Query(default=None), service: AdminDashboardService = Depends(get_admin_dashboard_service)):
    return service.get_dashboard_payload(date)


@router.get('/api/events/stream')
async def admin_event_stream():
    async def gen():
        last_version = 0
        yield 'retry: 3000\n\n'
        while True:
            try:
                async for last_version, payload in event_stream.listen(last_version):
                    yield f'event: dashboard\ndata: {payload}\nid: {last_version}\n\n'
            except asyncio.CancelledError:
                break
    return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})


@router.post('/api/sync/import')
async def admin_import_sync(sync_service: SyncService = Depends(get_sync_service)):
    result = sync_service.import_all()
    await event_stream.publish('dashboard_updated')
    return result


@router.post('/api/export/google-sheet')
async def admin_export_google_sheet(date: str | None = Query(default=None), export_service: ExportService = Depends(get_export_service), dashboard_service: AdminDashboardService = Depends(get_admin_dashboard_service)):
    target_date = date or dashboard_service.get_dashboard_payload().get('date')
    result = export_service.export_google_sheet(target_date)
    await event_stream.publish('dashboard_updated')
    return result


@router.get('/api/export/excel')
async def admin_export_excel(date: str | None = Query(default=None), export_service: ExportService = Depends(get_export_service), dashboard_service: AdminDashboardService = Depends(get_admin_dashboard_service)):
    target_date = date or dashboard_service.get_dashboard_payload().get('date')
    path = export_service.export_excel(target_date)
    return FileResponse(path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=path.name)
