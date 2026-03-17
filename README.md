# Diet Agent

一个基于 Django + Neo4j + Vue 3 的智能膳食管理系统，支持：

- AI 对话推荐
- 食谱推荐与筛选
- 饮食记录/健康日志
- 健康管理（预算、营养分析、运动消耗）
- 收藏与食材关系查询
- 管理员数据导入与审计

## 1. 项目结构

```text
diet_agent/
├── diet_agent_backend/              # Django 后端
│   ├── agent/                       # 核心业务模块
│   │   ├── context/                 # 上下文构建
│   │   ├── memory/                  # 记忆模块
│   │   ├── views.py                 # API 实现
│   │   ├── urls.py                  # API 路由
│   │   └── neo4j_service.py         # Neo4j 封装
│   ├── diet_agent_backend/          # Django 工程配置
│   └── manage.py
├── diet_agent_frontend/             # Vue 前端
│   └── src/
│       ├── views/                   # 页面模块
│       ├── router/                  # 路由与鉴权守卫
│       ├── utils/                   # 工具函数
│       ├── App.vue                  # 应用壳
│       └── api.js                   # Axios 实例
└── README.md
```

## 2. 技术栈

- 前端：Vue 3, Vue Router, Vite, Axios, ECharts, lucide-vue-next
- 后端：Django, Django REST Framework, django-cors-headers
- 图数据库：Neo4j
- LLM 相关：langchain-openai, langchain-core, langgraph

## 3. 环境与依赖

### 3.1 后端（Python 3.10+）

在 `diet_agent_backend/` 目录创建并激活虚拟环境后安装依赖：

```bash
pip install django djangorestframework django-cors-headers neo4j python-dotenv langchain-openai langchain-core
```

创建 `diet_agent_backend/.env`（示例）：

```env
NEO4J_URI=your_neo4j_url
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
NEO4J_AUTO_INIT=true
# 可选：不填则自动使用仓库根目录 neo4j_data
# NEO4J_DATA_DIR=/absolute/path/to/neo4j_data
# 可选：强制重新全量导入一次（默认 false）
NEO4J_FORCE_REIMPORT=false
# 可选：手动指定导入版本号，不填则按数据文件指纹自动计算
# NEO4J_BOOTSTRAP_VERSION=v1

OPENAI_API_BASE=your_base_url
OPENAI_API_KEY=your_api_key
LLM_MODEL_NAME=your_model_name

ADMIN_DEFAULT_ID=admin
ADMIN_DEFAULT_PASSWORD=123
```

Neo4j 自动初始化说明：

- 项目启动时会自动检查 `neo4j_data/` 中的数据文件，并在首次运行或数据版本变化时执行全量 `upsert` 导入。
- 导入包含食材与食谱的完整属性（含 `nutrients_raw`、`ingredients_raw`、`steps_raw`、`raw_json`），并通过唯一约束与 `MERGE` 去重。
- 若已导入且版本未变化，后续启动会自动跳过，不重复导入。

### 3.2 前端（Node 20+）

```bash
cd diet_agent_frontend
npm install
```

## 4. 启动方式

### 4.1 启动后端

```bash
cd diet_agent_backend
python manage.py runserver
```

默认监听：`http://127.0.0.1:8000`

### 4.2 启动前端

```bash
cd diet_agent_frontend
npm run dev
```

默认监听：`http://127.0.0.1:5173`

## 5. 架构说明（简版）

### 5.1 前后端分层

- `views.py` 作为 API 层，负责参数校验、调用图谱服务与记忆模块。
- `neo4j_service.py` 统一管理 Neo4j 连接与查询。
- `context/* + memory/*` 为智能推荐和对话提供上下文与用户长期偏好。

### 5.2 数据流

1. 前端页面通过 `src/api.js` 请求 `/api/*`。
2. 后端 `agent.urls` 分发到对应 View。
3. View 查询 Neo4j / 写入日志，返回 JSON。
4. 前端页面按日期/餐次/模块渲染。

### 5.3 关键设计点

- 饮食记录、健康管理、健康日志使用统一日期格式 `YYYY-MM-DD`。
- 聊天历史按消息索引正序，避免时间戳并发写入导致乱序。
- 食谱推荐种类来自 Neo4j `category` 字段。

## 6. 模块文档索引

- 后端总览：[diet_agent_backend/README.md](diet_agent_backend/README.md)
- Agent 核心：[diet_agent_backend/agent/README.md](diet_agent_backend/agent/README.md)
- 上下文模块：[diet_agent_backend/agent/context/README.md](diet_agent_backend/agent/context/README.md)
- 记忆模块：[diet_agent_backend/agent/memory/README.md](diet_agent_backend/agent/memory/README.md)
- Django 配置：[diet_agent_backend/diet_agent_backend/README.md](diet_agent_backend/diet_agent_backend/README.md)
- 前端 src：[diet_agent_frontend/src/README.md](diet_agent_frontend/src/README.md)
- 页面模块：[diet_agent_frontend/src/views/README.md](diet_agent_frontend/src/views/README.md)
- 路由模块：[diet_agent_frontend/src/router/README.md](diet_agent_frontend/src/router/README.md)
- 工具模块：[diet_agent_frontend/src/utils/README.md](diet_agent_frontend/src/utils/README.md)

## 7. 说明

- 系统架构图说明模板：[docs/mentor/01_system_architecture_template.md](docs/mentor/01_system_architecture_template.md)
- API 清单模板：[docs/mentor/02_api_inventory_template.md](docs/mentor/02_api_inventory_template.md)
- 演示流程页：[docs/mentor/03_demo_flow_page.md](docs/mentor/03_demo_flow_page.md)
