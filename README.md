# LINE Attendance Bot (FastAPI + PostgreSQL / SQLite)

這一版已經不是單純骨架，而是可以真的測試下面這條流程：

**LINE webhook → FastAPI → PostgreSQL/SQLite → `/admin` 後台顯示真資料**

目前已完成：
- FastAPI webhook 入口
- LINE message / postback 事件路由
- 報班資料寫入資料庫
- 打卡資料寫入資料庫
- `/admin` 後台讀真資料
- `/admin/api/dashboard` 即時回傳真資料
- 每 5 秒前端自動 refresh
- Google Sheets 同步保留骨架，但不再作為主資料來源
- 支援 `DATABASE_URL`，可切換到 PostgreSQL
- 已加入 LINE webhook signature 驗證
- 已加入 `/admin` Basic Auth 保護

## 啟動方式

### 1. 安裝套件

```bash
pip install -r requirements.txt
```

### 2. 建立環境變數

把 `.env.example` 複製成 `.env`，至少可先填：

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `DATABASE_URL=postgresql+psycopg://lineproj:lineproj@127.0.0.1:5432/lineproj`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `TEST_MODE=true`

如果你沒有設定 `DATABASE_URL`，系統會退回使用 `SQLITE_DB_PATH=data/attendance.db`。
如果你暫時不填 LINE token，系統也能啟動，但只適合本機 API 測試；不能真的回 LINE。

### 本機 PostgreSQL 建議啟動方式

```bash
docker compose up -d
```

然後把 `.env` 設成：

```env
DATABASE_URL=postgresql+psycopg://lineproj:lineproj@127.0.0.1:5432/lineproj
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

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
- 請款表與獎金表目前為後台即時計算預覽，不是正式回寫 Sheet
- 報班 work_date 目前採「當晚報隔天班」
- SQLite 僅建議本機開發或緊急備援，不建議當正式線上主庫

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

1. 線上改接 Render Postgres 或 Neon Postgres
2. 把 Google Sheet 改成排程同步，不要卡在 webhook 主流程
3. 補 migration 工具與部署腳本
4. 加入備份排程，例如每日 `pg_dump`
5. 補壓力測試與 webhook 重試監控

## Render 測試部署

如果你現在想先做「少數人可用的測試站」，但還不急著上 Cloudflare Access，這一版可以先這樣部署：

- Render Web Service
- Render Postgres
- `/admin` 繼續用 Basic Auth 保護
- Google Sheets 憑證改用環境變數 `GOOGLE_SERVICE_ACCOUNT_JSON`

專案已提供 [render.yaml](/Users/lushuyan/Documents/Playground/lineproj_v4/render.yaml)，可以直接用 Render Blueprint 匯入。

### 建議做法

1. 把專案推到 GitHub
2. 在 Render 建立 `Blueprint`
3. 匯入這個 repo
4. Render 會依 `render.yaml` 建立：
   - 一個 Python Web Service
   - 一個 Postgres Database
5. 在 Render 補齊下列環境變數

### Render 必填環境變數

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `GROUP_ID`
- `HR_GROUP_ID`
- `GOOGLE_SPREADSHEET_ID`

### Google Sheets 憑證

Render 不適合直接放本機檔案 `service_account.json`。  
這一版已支援：

- `GOOGLE_SERVICE_ACCOUNT_JSON`

做法是把整份 Google Service Account JSON 內容，原樣貼到 Render 的這個環境變數裡。

如果你暫時不需要線上同步 Google Sheets，也可以先不填：

- `GOOGLE_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`

系統仍可先用資料庫與後台測試。

### 部署後要做的事

1. 打開 Render 服務網址
2. 先測：
   - `GET /health`
   - `GET /admin`
3. 確認 `/admin` 有跳 Basic Auth
4. 到 LINE Developers 把 webhook 改成：

```text
https://你的-render-網址/webhook/line
```

5. 用 LINE 實測報班 / 打卡

### 目前這種 Render 測試站的安全建議

- 這 still 是公開網址，不是內網
- 但有 `Basic Auth`，適合少數特定人員測試
- 先不要分享給太多人
- 建議之後正式用時再加 `Cloudflare Access`
- 如果 Render 已綁自訂網域，之後可考慮停用預設公開子網域

### 目前不建議的做法

- 不要在線上用 SQLite 當主資料庫
- 不要把 `.env`、`service_account.json`、本機資料庫檔提交到 repo
- 不要直接把 LINE token / secret 貼到公開地方


## Google Sheet 雙向同步

設定 `.env` 內的 `GOOGLE_SPREADSHEET_ID` 與 `GOOGLE_SERVICE_ACCOUNT_FILE` 後：

- LINE 報班時會即時 upsert 到 `工作表1`
- LINE 打卡時會即時 upsert 到 `出勤彙總` 與 `觀音長派`
- 後台可手動執行：
  - `POST /admin/api/export/google-sheet`：資料庫資料匯出到 `工作表1 / 出勤彙總 / 觀音長派`
  - `POST /admin/api/sync/import`：從 `工作表1 / 出勤彙總` 匯入資料庫

注意：Google Service Account 需要先共享到你的試算表。

## 備份

若你使用 PostgreSQL，可用內建腳本手動備份：

```bash
DATABASE_URL=postgresql+psycopg://lineproj:lineproj@127.0.0.1:5432/lineproj ./scripts/backup_postgres.sh
```
