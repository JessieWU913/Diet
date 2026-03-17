# 系统架构图说明模板（导师版）

## 1. 文档目的

用于答辩/评审时快速说明系统整体结构、核心模块职责与关键数据流。

## 2. 架构总览图（可直接替换）

```mermaid
flowchart LR
  subgraph Frontend[前端 Vue3]
    A1[登录与鉴权]
    A2[聊天页]
    A3[食谱页]
    A4[饮食记录]
    A5[健康管理]
    A6[健康日志]
    A7[管理页]
  end

  subgraph Backend[Django + DRF]
    B1[路由层 agent.urls]
    B2[接口层 agent.views]
    B3[上下文层 agent.context]
    B4[记忆层 agent.memory]
    B5[工具层 mcp_tools/graph]
    B6[图数据库访问 neo4j_service]
  end

  subgraph Data[数据层]
    C1[(Neo4j 图数据库)]
    C2[(SQLite 用户与后台数据)]
  end

  subgraph LLM[模型服务]
    D1[LLM API]
  end

  Frontend --> Backend
  Backend --> Data
  Backend --> LLM
```

## 3. 分层说明（填写版）

### 3.1 前端层

- 技术栈：
- 核心页面：
- 关键状态管理策略：

### 3.2 后端接口层

- 路由入口：
- 统一返回规范：
- 权限控制方式：

### 3.3 智能能力层

- 上下文构建策略（GSSC）：
- 记忆模块拆分（长期/情景/工作）：
- 工具调用与回退策略：

### 3.4 数据层

- Neo4j 节点/关系概览：
- 日志与关系数据写入策略：
- 一致性约束（例如唯一约束）：

## 4. 关键时序（建议展示 1~2 条）

- 场景 A：用户提问 -> 工具查询 -> 返回推荐
- 场景 B：导出菜谱 -> 记录饮食 -> 健康管理统计刷新

## 5. 架构亮点（填写版）

- 亮点 1：
- 亮点 2：
- 亮点 3：

## 6. 可扩展性说明（填写版）

- 新增页面如何接入：
- 新增接口如何接入：
- 新增图谱实体如何接入：
