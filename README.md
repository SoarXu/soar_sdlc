# SOAR SDLC

前后端分离的项目管理系统开发框架。

## 技术栈

- 后端：Python 3.11+、FastAPI、SQLAlchemy、Alembic、Pydantic、JWT，采用 MVC 分层
- 前端：Vue 3、Vite、Vue Router、Pinia、Axios、Element Plus
- 数据库：默认 SQLite，可切换 MySQL/PostgreSQL

## 目录

```text
backend/   FastAPI API 服务，MVC 后端结构
frontend/  Vue3 前端应用
docs/      设计文档
```

后端核心目录：

```text
backend/app/controllers/  Controller，负责 HTTP 路由和请求响应
backend/app/models/       Model，负责数据库实体
backend/app/views/        View，负责请求/响应数据结构
backend/app/services/     Service，负责业务逻辑
backend/app/db/           数据库连接和会话
backend/app/core/         配置、安全等基础能力
```

## 后端启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

演示账号：

```text
admin / admin123
```

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端地址：

```text
http://127.0.0.1:5173
```

开发环境中，`frontend/vite.config.js` 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 已预置内容

- 后端健康检查：`GET /api/v1/health`
- 登录接口：`POST /api/v1/auth/login`
- 项目列表接口：`GET /api/v1/projects`
- 新增项目接口：`POST /api/v1/projects`
- Vue3 后台布局、登录页、项目集总览页、项目管理页
