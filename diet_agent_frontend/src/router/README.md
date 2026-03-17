# Router Module

## 作用

维护前端路由表与访问控制（登录态、管理员态）。

## 文件

- `index.js`: 路由定义、重定向与 `beforeEach` 守卫。

## 规则

- 普通页面需 `meta.requiresAuth`。
- 管理端页面需 `meta.requiresAdmin`。
- 未登录访问受限页面时跳转到登录页。
