# Views Module

## 作用

页面级模块集合，每个 `.vue` 文件对应一个业务页面。

## 主要页面

- `LoginView.vue`: 登录/注册。
- `HomeView.vue`: 主页与快捷看板。
- `DietLogView.vue`: 饮食记录录入与查询。
- `RecipeView.vue`: 食谱推荐、筛选、导出菜谱管理。
- `StatsView.vue`: 健康管理与 AI 分析展板。
- `ChatView.vue`: AI 对话、反馈、菜谱导出。
- `IngredientSearchView.vue`: 食材/菜谱查询。
- `FavoritesView.vue`: 收藏管理与关系查询。
- `HealthLogView.vue`: 历史日志时间线。
- `AdminView.vue`: 管理台。

## 维护建议

- 新页面增加后，同步更新 `router/index.js` 与本 README。
