from app.services.admin_dashboard_service import AdminDashboardService
from app.services.attendance_service import AttendanceService
from app.services.bonus_service import BonusService
from app.services.db_service import DatabaseService
from app.services.event_stream_service import event_stream
from app.services.export_service import ExportService
from app.services.invoice_service import InvoiceService
from app.services.line_service import LineBotService, LineWebhookHandler
from app.services.signup_service import SignupService
from app.services.sheets_service import GoogleSheetsService
from app.services.sync_service import SyncService


def get_db_service() -> DatabaseService:
    return DatabaseService()


def get_sheets_service() -> GoogleSheetsService:
    return GoogleSheetsService()


def get_bonus_service() -> BonusService:
    return BonusService(get_sheets_service(), get_db_service())


def get_line_bot_service() -> LineBotService:
    return LineBotService()


def get_signup_service() -> SignupService:
    return SignupService(get_sheets_service(), get_db_service())


def get_invoice_service() -> InvoiceService:
    return InvoiceService(get_sheets_service(), get_bonus_service())


def get_attendance_service() -> AttendanceService:
    return AttendanceService(get_sheets_service(), get_invoice_service(), get_db_service())


def get_admin_dashboard_service() -> AdminDashboardService:
    return AdminDashboardService(get_db_service(), get_bonus_service())


def get_webhook_handler() -> LineWebhookHandler:
    return LineWebhookHandler(
        line_service=get_line_bot_service(),
        signup_service=get_signup_service(),
        attendance_service=get_attendance_service(),
        db_service=get_db_service(),
        event_stream=event_stream,
    )


def get_sync_service() -> SyncService:
    sheets = get_sheets_service()
    db = get_db_service()
    bonus = BonusService(sheets, db)
    signup = SignupService(sheets, db)
    invoice = InvoiceService(sheets, bonus)
    attendance = AttendanceService(sheets, invoice, db)
    return SyncService(db=db, sheets=sheets, signup_service=signup, attendance_service=attendance, bonus_service=bonus)


def get_export_service() -> ExportService:
    sheets = get_sheets_service()
    db = get_db_service()
    bonus = BonusService(sheets, db)
    signup = SignupService(sheets, db)
    invoice = InvoiceService(sheets, bonus)
    attendance = AttendanceService(sheets, invoice, db)
    dashboard = AdminDashboardService(db, bonus)
    return ExportService(db=db, sheets=sheets, signup_service=signup, attendance_service=attendance, invoice_service=invoice, bonus_service=bonus, dashboard_service=dashboard)
