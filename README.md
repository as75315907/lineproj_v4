# LINE Attendance Bot (FastAPI + SQLite 可測試版)

這一版已經不是單純骨架，而是可以真的測試下面這條流程：

**LINE webhook → FastAPI → SQLite → `/admin` 後台顯示真資料**

目前已完成：
- FastAPI webhook 入口
- LINE message / postback 事件路由
- 報班資料寫入 SQLite
- 打卡資料寫入 SQLite
- `/admin` 後台讀 SQLite 真資料
- `/admin/api/dashboard` 即時回傳真資料
- 每 5 秒前端自動 refresh
- Google Sheets 同步保留骨架，但不再作為主資料來源

## 啟動方式

### 1. 安裝套件

```bash
pip install -r requirements.txt
```

### 2. 建立環境變數

把 `.env.example` 複製成 `.env`，至少可先填：

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `SQLITE_DB_PATH=data/attendance.db`
- `TEST_MODE=true`

如果你暫時不填 LINE token，系統也能啟動，但只適合本機 API 測試；不能真的回 LINE。

### 3. 啟動

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. 打開後台

```text
http://127.0.0.1:8000/admin
```

### 5. 健康檢查

```text
GET /health
```

## 要怎麼用 LINE 真實測試

### 本機測試
你需要把 webhook URL 暴露到外網，例如用 ngrok：

```bash
ngrok http 8000
```

然後把 LINE Developers 的 webhook URL 設成：

```text
https://你的-ngrok-網址/webhook/line
```

### 測試流程
1. 在 LINE 群組輸入 `報班`
2. Bot 會推播報班按鈕
3. 點 `早班 07:00` 或 `晚班 22:00`
4. 到 `/admin` 看 `工作表1`
5. 在 LINE 群組輸入 `打卡`
6. 點 `上班打卡 / 休息開始 / 休息結束 / 下班打卡`
7. 到 `/admin` 看 `出勤彙總`

## 目前限制

- Google Sheet 同步仍是骨架，還不是完整正式同步
- LINE signature 驗證尚未加上
- 請款表與獎金表目前為後台即時計算預覽，不是正式回寫 Sheet
- 報班 work_date 目前採「當晚報隔天班」

## 主要路由

- `POST /webhook/line`
- `GET /health`
- `GET /admin`
- `GET /admin/api/dashboard`

## 目前系統狀態頁會顯示

- 工作表1（報班）
- 出勤彙總（打卡）
- 觀音長派（請款預覽）
- 長期派遣-排休獎金（班別別名對照）
- DEBUG_LOG（最近事件）

## 下一步最適合做的事

1. 把 Google Sheet 正式同步補上
2. 加入 LINE webhook signature 驗證
3. 把請款表欄位與公式完整對齊你目前實際 Sheet
4. 補登入保護（私人後台帳密）
5. SQLite 升級 PostgreSQL


## Google Sheet 雙向同步

設定 `.env` 內的 `GOOGLE_SPREADSHEET_ID` 與 `GOOGLE_SERVICE_ACCOUNT_FILE` 後：

- LINE 報班時會即時 upsert 到 `工作表1`
- LINE 打卡時會即時 upsert 到 `出勤彙總` 與 `觀音長派`
- 後台可手動執行：
  - `POST /admin/api/sync/export`：SQLite 全量匯出到 `工作表1 / 出勤彙總 / 觀音長派`
  - `POST /admin/api/sync/import`：從 `工作表1 / 出勤彙總` 匯入 SQLite

注意：Google Service Account 需要先共享到你的試算表。
