employee_backend_patch_full 使用說明
===================================

請覆蓋 / 新增以下檔案：

1. 覆蓋 app/services/signup_service.py
2. 覆蓋 app/services/attendance_service.py
3. 覆蓋 app/services/invoice_service.py
4. 覆蓋 app/core/deps.py
5. 覆蓋 app/services/db_service.py
6. 新增 app/services/employee_service.py
7. 新增 app/api/admin_employees.py

另外手動修改：
- app/main.py
  新增：
    from app.api.admin_employees import router as admin_employees_router
    app.include_router(admin_employees_router)

資料庫初始化：
- 若你的專案有 schema 初始化檔，請加入 schema_add_employees.sql 內容
- 若沒有現成 migration，最簡單是手動在 SQLite 執行 schema_add_employees.sql

新增 API：
- GET  /admin/api/employees
- POST /admin/api/employees/{uid}/role
- POST /admin/api/employees/{uid}/status
- POST /admin/api/employees/{uid}/note

角色值：
- staff
- supervisor
- leader
- admin

狀態值：
- active
- inactive
