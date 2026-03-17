# Frontend (Vue 3)

## 作用

前端负责用户交互与可视化，包括聊天、食谱推荐、饮食记录、健康管理、健康日志、收藏等页面。

## 目录结构

```text
diet_agent_frontend/
├── src/
│   ├── App.vue
│   ├── main.js
│   ├── api.js
│   ├── views/
│   ├── router/
│   └── utils/
├── index.html
├── vite.config.js
└── package.json
```

## 运行

```bash
npm install
npm run dev
```

生产构建：

```bash
npm run build
```

## 开发规范

- 所有接口调用统一走 `src/api.js`。
- 路由守卫统一在 `src/router/index.js`。
- 复用逻辑优先放到 `src/utils/`。
- 页面级状态优先本地维护，避免无效全局状态。

## 模块文档

- src 总览：[src/README.md](src/README.md)
- 页面模块：[src/views/README.md](src/views/README.md)
- 路由模块：[src/router/README.md](src/router/README.md)
- 工具模块：[src/utils/README.md](src/utils/README.md)
