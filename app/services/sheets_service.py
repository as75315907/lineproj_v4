from __future__ import annotations

import json
from typing import Any, List, Optional

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:  # pragma: no cover
    gspread = None
    Credentials = None

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GoogleSheetsService:
    def __init__(self) -> None:
        self._client = None
        self._spreadsheet = None

    def is_available(self) -> bool:
        return bool(self._get_spreadsheet())

    def _get_client(self):
        if self._client is not None:
            return self._client
        if gspread is None or Credentials is None:
            logger.warning("gspread/google-auth not available yet")
            return None
        if not settings.google_spreadsheet_id:
            logger.warning("Google Sheets settings missing")
            return None

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = None
        if settings.google_service_account_json:
            try:
                service_account_info = json.loads(settings.google_service_account_json)
                creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            except Exception as exc:
                logger.warning("Failed to load Google service account JSON from env: %s", exc)
                return None
        elif settings.google_service_account_file:
            try:
                creds = Credentials.from_service_account_file(
                    settings.google_service_account_file,
                    scopes=scopes,
                )
            except Exception as exc:
                logger.warning("Failed to load Google service account file: %s", exc)
                return None
        else:
            logger.warning("Google Sheets credential source missing")
            return None

        self._client = gspread.authorize(creds)
        return self._client

    def _get_spreadsheet(self):
        if self._spreadsheet is not None:
            return self._spreadsheet
        client = self._get_client()
        if client is None:
            return None
        self._spreadsheet = client.open_by_key(settings.google_spreadsheet_id)
        return self._spreadsheet

    def get_worksheet(self, title: str):
        spreadsheet = self._get_spreadsheet()
        if spreadsheet is None:
            return None
        try:
            return spreadsheet.worksheet(title)
        except Exception:
            return spreadsheet.add_worksheet(title=title, rows=1000, cols=30)

    def append_row(self, sheet_name: str, values: List[Any]) -> None:
        ws = self.get_worksheet(sheet_name)
        if ws is None:
            logger.info("[MOCK append_row] %s -> %s", sheet_name, values)
            return
        ws.append_row(values, value_input_option="USER_ENTERED")

    def update_row(self, sheet_name: str, row: int, values: List[Any]) -> None:
        ws = self.get_worksheet(sheet_name)
        if ws is None:
            logger.info("[MOCK update_row] %s R%s=%s", sheet_name, row, values)
            return
        start_col = 1
        end_col = len(values)
        ws.update(f"{self._col_letter(start_col)}{row}:{self._col_letter(end_col)}{row}", [values], value_input_option="USER_ENTERED")

    def replace_sheet_data(self, sheet_name: str, rows: List[List[Any]]) -> None:
        ws = self.get_worksheet(sheet_name)
        if ws is None:
            logger.info("[MOCK replace_sheet_data] %s rows=%s", sheet_name, len(rows))
            return
        ws.clear()
        if rows:
            ws.update(f"A1:{self._col_letter(max(len(r) for r in rows))}{len(rows)}", rows, value_input_option="USER_ENTERED")

    def get_all_values(self, sheet_name: str) -> List[List[Any]]:
        ws = self.get_worksheet(sheet_name)
        if ws is None:
            logger.info("[MOCK get_all_values] %s", sheet_name)
            return []
        return ws.get_all_values()

    def update_cell(self, sheet_name: str, row: int, col: int, value: Any) -> None:
        ws = self.get_worksheet(sheet_name)
        if ws is None:
            logger.info("[MOCK update_cell] %s R%sC%s=%s", sheet_name, row, col, value)
            return
        ws.update_cell(row, col, value)

    def ensure_header(self, sheet_name: str, header: List[str]) -> None:
        rows = self.get_all_values(sheet_name)
        if not rows:
            self.append_row(sheet_name, header)
            return
        if rows[0] != header:
            logger.info("Header already exists but differs: %s", sheet_name)

    def find_row_by_two_keys(
        self,
        sheet_name: str,
        key1_col_idx: int,
        key1: str,
        key2_col_idx: int,
        key2: str,
        start_row: int = 2,
    ) -> Optional[int]:
        rows = self.get_all_values(sheet_name)
        for idx, row in enumerate(rows[start_row - 1 :], start=start_row):
            v1 = row[key1_col_idx - 1].strip() if len(row) >= key1_col_idx else ""
            v2 = row[key2_col_idx - 1].strip() if len(row) >= key2_col_idx else ""
            if v1 == str(key1).strip() and v2 == str(key2).strip():
                return idx
        return None

    def upsert_row_by_two_keys(
        self,
        sheet_name: str,
        key1_col_idx: int,
        key1: str,
        key2_col_idx: int,
        key2: str,
        values: List[Any],
        start_row: int = 2,
    ) -> str:
        row_idx = self.find_row_by_two_keys(sheet_name, key1_col_idx, key1, key2_col_idx, key2, start_row)
        if row_idx:
            self.update_row(sheet_name, row_idx, values)
            return "update"
        self.append_row(sheet_name, values)
        return "insert"

    def _col_letter(self, col: int) -> str:
        result = ""
        while col > 0:
            col, rem = divmod(col - 1, 26)
            result = chr(65 + rem) + result
        return result
