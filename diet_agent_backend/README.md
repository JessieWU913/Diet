# Backend Module

## 作用

Django 后端入口目录，负责项目启动、环境变量加载、数据导入脚本与运行数据库文件管理。

## 目录说明

- `manage.py`: Django 管理命令入口。
- `diet_agent_backend/`: Django 工程配置（settings、urls、wsgi、asgi）。
- `agent/`: 业务应用，包含 API、图谱访问、记忆模块。
- `import_full_graph.py`: 图谱全量导入脚本。
- `db.sqlite3`: Django 本地数据库（主要用于认证/管理数据）。

## 运行方式

在本目录执行：

```bash
python manage.py runserver
```

## 维护建议

- 生产环境不要提交真实 `db.sqlite3`。
- `.env` 存放 Neo4j 与模型服务配置，不要入库。
- 当 `NEO4J_AUTO_INIT=true` 时，后端会在连接 Neo4j 后自动从 `neo4j_data/` 做去重导入。
