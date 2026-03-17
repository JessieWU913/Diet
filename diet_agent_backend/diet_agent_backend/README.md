# Django Project Config Module

## 作用

Django 工程级配置模块，负责全局配置与路由入口。

## 文件说明

- `settings.py`: 全局配置（App、数据库、跨域、时区等）。
- `urls.py`: 项目级 URL 分发（挂载 `agent` 路由）。
- `wsgi.py` / `asgi.py`: 部署入口。

## 配置重点

- `INSTALLED_APPS` 包含 `agent`、`rest_framework`、`corsheaders`。
- 开发期允许跨域，部署前请收紧 CORS 与 Host 白名单。
