# Agent Module

## 作用

核心业务模块，提供膳食推荐、饮食记录、健康分析、聊天、收藏、管理端数据维护等 API。

## 核心文件

- `views.py`: 主要 API 实现。
- `urls.py`: API 路由注册。
- `graph.py`: 对话与工具链流程编排。
- `neo4j_service.py`: Neo4j 连接与查询封装。
- `mcp_tools.py`: 图谱检索/工具函数。
- `memory/`: 语义记忆、情景记忆、工作记忆。
- `context/`: 对话上下文构建。

## 对外接口

由 `urls.py` 暴露到 `/api/*`，包含：

- 聊天、反馈、聊天历史
- 饮食记录、运动记录、营养汇总
- 食谱推荐/详情、食材详情/关系
- 管理员鉴权与导入审计

## 开发约定

- API 返回统一 JSON。
- 图谱查询优先通过 `neo4j_service.graph_db.query()`。
- 新增接口需同步更新 `urls.py` 与项目总 README。
