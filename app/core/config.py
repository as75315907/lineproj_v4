from functools import lru_cache
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = Field(default='LINE Attendance Bot', alias='APP_NAME')
    app_env: str = Field(default='dev', alias='APP_ENV')
    app_debug: bool = Field(default=True, alias='APP_DEBUG')
    timezone: str = Field(default='Asia/Taipei', alias='TIMEZONE')

    line_channel_access_token: str = Field(default='', alias='LINE_CHANNEL_ACCESS_TOKEN')
    line_channel_secret: str = Field(default='', alias='LINE_CHANNEL_SECRET')

    google_spreadsheet_id: str = Field(default='', alias='GOOGLE_SPREADSHEET_ID')
    google_service_account_file: str = Field(default='service_account.json', alias='GOOGLE_SERVICE_ACCOUNT_FILE')

    group_id: str = Field(default='', alias='GROUP_ID')
    hr_group_id: str = Field(default='', alias='HR_GROUP_ID')

    signup_sheet_name: str = Field(default='工作表1', alias='SIGNUP_SHEET_NAME')
    att_sheet_name: str = Field(default='出勤彙總', alias='ATT_SHEET_NAME')
    debug_sheet_name: str = Field(default='DEBUG_LOG', alias='DEBUG_SHEET_NAME')
    invoice_sheet_name: str = Field(default='觀音長派', alias='INVOICE_SHEET_NAME')
    bonus_sheet_name: str = Field(default='長期派遣-排休獎金', alias='BONUS_SHEET_NAME')

    sqlite_db_path: str = Field(default='data/attendance.db', alias='SQLITE_DB_PATH')
    export_dir: str = Field(default='data/exports', alias='EXPORT_DIR')

    test_mode: bool = Field(default=True, alias='TEST_MODE')
    signup_start_hour: int = Field(default=21, alias='SIGNUP_START_HOUR')
    invoice_hide_uid_col: bool = Field(default=True, alias='INVOICE_HIDE_UID_COL')
    invoice_auto_fill_bonus: bool = Field(default=True, alias='INVOICE_AUTO_FILL_BONUS')
    realtime_sheet_sync: bool = Field(default=False, alias='REALTIME_SHEET_SYNC')

    shift_alias_map: Dict[str, str] = {
        '早班 07:00': '早班',
        '晚班 22:00': '大夜班',
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
