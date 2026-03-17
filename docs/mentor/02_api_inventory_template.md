# API 清单模板（导师版）

## 1. 说明

本模板用于提交时展示接口完整性、输入输出规范与测试状态。

## 2. 基础信息

- Base URL：
- 鉴权方式：
- 返回格式：JSON
- 错误码约定：

## 3. 接口总表（填写）

| 编号 | 接口名称 | Method | Path | 作用 | 是否鉴权 |
| --- | --- | --- | --- | --- | --- |
| 1 | 用户登录/注册 | POST | /api/auth/ | 登录与注册 | 否 |
| 2 | 用户资料读写 | GET/POST | /api/user-profile/ | 画像与目标管理 | 是 |
| 3 | 聊天对话 | POST | /api/chat/ | AI 推荐与问答 | 是 |
| 4 | 反馈写入 | POST | /api/feedback/ | 正负反馈学习 | 是 |
| 5 | 饮食记录 | GET/POST/DELETE | /api/diet-log/ | 饮食日志管理 | 是 |
| 6 | 运动记录 | GET/POST/DELETE | /api/exercise-log/ | 运动消耗管理 | 是 |
| 7 | 食谱推荐 | GET/POST | /api/recommend-meals/ | 推荐三餐 | 是 |
| 8 | 菜谱详情 | GET/POST | /api/recipe-detail/ /api/recipe/ | 菜谱详情与补全 | 是 |
| 9 | 食材详情 | GET | /api/ingredient-detail/ | 食材与关系查询 | 是 |
| 10 | 管理员总览 | GET | /api/admin/overview/ | 运营统计 | 管理员 |

## 4. 单接口模板（复制多份填写）

### 4.1 接口名称

- Method + Path：
- 功能：
- 请求参数：
- 响应字段：
- 异常场景：
- 示例请求：

```json
{
  "example": "request"
}
```

- 示例响应：

```json
{
  "status": "success"
}
```

## 5. 覆盖性检查清单

- [ ] 核心用户链路接口已列全
- [ ] 管理端接口已列全
- [ ] 每个接口有至少 1 个成功响应示例
- [ ] 每个接口有失败场景说明
- [ ] 鉴权需求与前端路由一致
