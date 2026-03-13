import uuid
import json
import os
import re
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from .memory.manager import MemoryManager
from .memory.semantic import SemanticMemory
from .memory.episodic import EpisodicMemory

from .graph import app
from .neo4j_service import graph_db

from django.contrib.auth.hashers import make_password, check_password


_recipe_enrich_llm = None


def _get_recipe_enrich_llm():
    """懒加载 AI 补全模型，避免影响进程启动。"""
    global _recipe_enrich_llm
    if _recipe_enrich_llm is None:
        _recipe_enrich_llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("LLM_MODEL_NAME"),
            default_headers={"X-Failover-Enabled": "true"},
            extra_body={"top_k": 20},
            max_tokens=600,
            temperature=0.2,
        )
    return _recipe_enrich_llm


def _extract_json_object(raw_text: str):
    """从模型输出中提取 JSON 对象。"""
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _ai_complete_recipe(name: str):
    """当图谱中不存在该菜名时，用 AI 生成可展示的兜底信息。"""
    try:
        llm = _get_recipe_enrich_llm()
        prompt = f"""
你是营养顾问。请为菜名“{name}”生成估算信息，严格只返回 JSON，不要输出任何额外文字。

JSON 结构必须是：
{{
  "calories": 数字,
  "protein": 数字,
  "fat": 数字,
  "carbs": 数字,
  "ingredients": ["字符串", "字符串"],
  "steps": ["字符串", "字符串", "字符串"]
}}

要求：
1. 数值合理，不要极端。
2. ingredients 与 steps 要可读、简洁。
3. 如果菜名看不懂，按清淡家常菜给估算。
"""
        response = llm.invoke(prompt)
        payload = _extract_json_object(response.content if hasattr(response, "content") else str(response))
        if not payload:
            return None

        ingredients = payload.get("ingredients", [])
        steps = payload.get("steps", [])

        if not isinstance(ingredients, list):
            ingredients = [str(ingredients)] if ingredients else []
        if not isinstance(steps, list):
            steps = [str(steps)] if steps else []

        return {
            "name": name,
            "calories": float(payload.get("calories", 0) or 0),
            "protein": float(payload.get("protein", 0) or 0),
            "fat": float(payload.get("fat", 0) or 0),
            "carbs": float(payload.get("carbs", 0) or 0),
            "ingredients": json.dumps(ingredients, ensure_ascii=False),
            "steps": json.dumps(steps, ensure_ascii=False),
            "source": "ai_fallback"
        }
    except Exception as e:
        print(f"AI补全失败: {e}")
        return None


def _is_blank_recipe_text(value):
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text == "[]"


def _to_json_safe(value):
    """将 Neo4j 特殊类型（如 DateTime）转换为 JSON 可序列化值。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    return str(value)

# 用户注册与登录接口
class UserAuthView(APIView):
    def post(self, request):
        user_id = str(request.data.get("user_id", "")).strip()
        password = str(request.data.get("password", "")).strip()
        action = request.data.get("action")
        name = str(request.data.get("name", "新用户")).strip()

        print(f"\n=== 收到验证请求: action={action}, user_id={user_id} ===")

        if not user_id or not password:
            return Response({"error": "账号和密码不能为空"}, status=400)

        if action == 'register':
            check_cypher = "MATCH (u:User {id: $user_id}) RETURN u"
            existing_user = graph_db.query(check_cypher, {"user_id": user_id})

            if existing_user:
                print("注册失败：账号已存在")
                return Response({"error": "该账号已被注册，请直接登录"}, status=400)

            hashed_password = make_password(password)
            print(f"注册准备写入 -> 明文密码: {password} | 加密结果: {hashed_password[:15]}...")

            create_cypher = """
            CREATE (u:User {id: $user_id, name: $name, password: $password})
            RETURN u
            """
            try:
                graph_db.query(create_cypher, {
                    "user_id": user_id,
                    "name": name,
                    "password": hashed_password
                })
                print("注册成功，数据已写入 Neo4j")
                return Response({"status": "success", "message": "注册成功"})
            except Exception as e:
                print(f"数据库写入失败: {e}")
                return Response({"error": f"数据库写入失败: {e}"}, status=500)

        elif action == 'login':
            login_cypher = "MATCH (u:User {id: $user_id}) RETURN u.password AS db_password"
            result = graph_db.query(login_cypher, {"user_id": user_id})

            if not result:
                print("登录失败：账号在图谱中不存在")
                return Response({"error": "账号不存在，请先注册"}, status=404)

            db_password = result[0].get("db_password")
            print(f"数据库中取出的密文类型: {type(db_password)}")
            print(f"数据库中取出的密文内容: {db_password[:15] if db_password else '空'}...")

            if not db_password:
                return Response({"error": "该账号是早期无密码账号，请重新注册"}, status=400)

            # 确保拿出来的是纯字符串格式
            db_password_str = str(db_password)

            if check_password(password, db_password_str):
                print("密码校验通过，允许登录！")
                return Response({"status": "success", "message": "登录成功"})
            else:
                print(f"密码校验失败！前端传来的明文是: '{password}'")
                return Response({"error": "密码错误，请重试"}, status=401)

        else:
            return Response({"error": "无效的操作"}, status=400)

# 用户资料填写接口
class UserProfileView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        birth_date = request.data.get("birthDate", "")
        gender = request.data.get("gender", "female")

        try:
            height = float(request.data.get("height") or 0)
            weight = float(request.data.get("weight") or 0)
        except ValueError:
            height, weight = 0.0, 0.0

        allergies = request.data.get("allergies", [])
        dislikes = request.data.get("dislikes", [])

        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MERGE (u:User {id: $user_id})
        SET u.gender = $gender, 
            u.height = $height, 
            u.weight = $weight, 
            u.birth_date = $birth_date,
            u.allergies = $allergies, 
            u.dislikes = $dislikes
        RETURN u
        """
        try:
            graph_db.query(cypher, {
                "user_id": user_id,
                "gender": gender,
                "height": height,
                "weight": weight,
                "birth_date": birth_date,
                "allergies": allergies,
                "dislikes": dislikes
            })
            return Response({"status": "success", "message": "画像更新成功"})
        except Exception as e:
            print(f"写入个人中心失败: {e}")
            return Response({"error": str(e)}, status=500)

    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})
        RETURN coalesce(u.gender, 'female') AS gender, 
               coalesce(u.height, 0) AS height, 
               coalesce(u.weight, 0) AS weight, 
               coalesce(u.allergies, []) AS allergies, 
               coalesce(u.dislikes, []) AS dislikes, 
               coalesce(u.positive_feedback, []) AS positive_feedback,
               coalesce(u.birth_date, "") AS birthDate
        """
        try:
            result = graph_db.query(cypher, {"user_id": user_id})
            if result:
                data = result[0]
                pos = data.get("positive_feedback", []) or []
                data["recent_positive_feedback"] = pos[-5:][::-1]
                return Response(data)
            return Response({})
        except Exception as e:
            print(f"读取个人中心失败: {e}")
            return Response({"error": str(e)}, status=500)

# 聊天接口
class AgentChatView(APIView):
    def post(self, request):
        user_query = request.data.get("query", "")
        user_mode = request.data.get("mode", "standard")
        user_id = request.data.get("user_id")
        session_id = request.data.get("session_id", f"session_{user_id}")

        user_profile = SemanticMemory.get_user_profile(user_id) if user_id else {}

        inputs = {
            "messages": [HumanMessage(content=user_query)],
            "user_mode": user_mode,
            "reflection_count": 0,
            "user_profile": user_profile,
            "user_id": user_id
        }

        config = {"configurable": {"thread_id": session_id}}

        try:
            result = app.invoke(inputs, config=config)
            return Response({"response": result['messages'][-1].content})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

# 用户负面反馈收集接口
class FeedbackView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        reason = request.data.get("reason")
        content = request.data.get("content", "")
        feedback_type = request.data.get("feedback_type", "down")

        if not user_id or not reason:
            return Response({"error": "参数不完整"}, status=400)

        if feedback_type == "up":
            success = MemoryManager.save_user_positive_feedback(user_id, reason, content)
            success_msg = "正向反馈记忆已写入图谱"
        else:
            success = MemoryManager.save_user_feedback(user_id, reason, content)
            success_msg = "反思记忆已写入图谱"

        if success:
            return Response({"status": "success", "message": success_msg})
        else:
            return Response({"error": "记忆写入失败，请检查数据库连接"}, status=500)

class RecipeDetailView(APIView):
    """
    [前端专用接口] 传入菜名列表，返回图谱中真实的完整菜谱数据
    """
    def post(self, request):
        names = request.data.get("names", [])
        if not names:
            return Response({"error": "未提供菜名"}, status=400)

        # 1) 精确匹配
        exact_cypher = """
        MATCH (n:Recipe)
        WHERE n.name IN $names
        RETURN n.name AS name,
               n.calories AS calories,
               n.protein AS protein,
               n.fat AS fat,
               n.carbs AS carbs,
               n.ingredients_raw AS ingredients,
               n.steps AS steps,
               'exact' AS source
        """

        # 2) 模糊匹配（用于“名称不完全一致”场景）
        fuzzy_cypher = """
        MATCH (n:Recipe)
        WHERE toLower(n.name) CONTAINS toLower($name)
           OR toLower($name) CONTAINS toLower(n.name)
        RETURN n.name AS matched_name,
               n.calories AS calories,
               n.protein AS protein,
               n.fat AS fat,
               n.carbs AS carbs,
               n.ingredients_raw AS ingredients,
               n.steps AS steps
        ORDER BY size(n.name) ASC
        LIMIT 1
        """

        try:
            exact_results = graph_db.query(exact_cypher, {"names": names})
            exact_map = {item["name"]: item for item in exact_results}

            final_results = []
            for name in names:
                # exact 命中
                if name in exact_map:
                    item = exact_map[name]
                    if _is_blank_recipe_text(item.get("steps")) or _is_blank_recipe_text(item.get("ingredients")):
                        ai_item = _ai_complete_recipe(name)
                        if ai_item:
                            if _is_blank_recipe_text(item.get("ingredients")):
                                item["ingredients"] = ai_item.get("ingredients", item.get("ingredients"))
                            if _is_blank_recipe_text(item.get("steps")):
                                item["steps"] = ai_item.get("steps", item.get("steps"))
                            if not item.get("calories"):
                                item["calories"] = ai_item.get("calories", item.get("calories"))
                            if not item.get("protein"):
                                item["protein"] = ai_item.get("protein", item.get("protein"))
                            if not item.get("fat"):
                                item["fat"] = ai_item.get("fat", item.get("fat"))
                            if not item.get("carbs"):
                                item["carbs"] = ai_item.get("carbs", item.get("carbs"))
                            item["source"] = "exact+ai_fill"
                    final_results.append(item)
                    continue

                # fuzzy 命中
                fuzzy = graph_db.query(fuzzy_cypher, {"name": name})
                if fuzzy:
                    f = fuzzy[0]
                    resolved_name = f.get("matched_name") or name
                    fuzzy_item = {
                        "name": resolved_name,
                        "requested_name": name,
                        "calories": f.get("calories"),
                        "protein": f.get("protein"),
                        "fat": f.get("fat"),
                        "carbs": f.get("carbs"),
                        "ingredients": f.get("ingredients"),
                        "steps": f.get("steps"),
                        "source": "fuzzy",
                        "matched_name": f.get("matched_name")
                    }

                    if _is_blank_recipe_text(fuzzy_item.get("steps")) or _is_blank_recipe_text(fuzzy_item.get("ingredients")):
                        ai_item = _ai_complete_recipe(resolved_name)
                        if ai_item:
                            if _is_blank_recipe_text(fuzzy_item.get("ingredients")):
                                fuzzy_item["ingredients"] = ai_item.get("ingredients", fuzzy_item.get("ingredients"))
                            if _is_blank_recipe_text(fuzzy_item.get("steps")):
                                fuzzy_item["steps"] = ai_item.get("steps", fuzzy_item.get("steps"))
                            if not fuzzy_item.get("calories"):
                                fuzzy_item["calories"] = ai_item.get("calories", fuzzy_item.get("calories"))
                            if not fuzzy_item.get("protein"):
                                fuzzy_item["protein"] = ai_item.get("protein", fuzzy_item.get("protein"))
                            if not fuzzy_item.get("fat"):
                                fuzzy_item["fat"] = ai_item.get("fat", fuzzy_item.get("fat"))
                            if not fuzzy_item.get("carbs"):
                                fuzzy_item["carbs"] = ai_item.get("carbs", fuzzy_item.get("carbs"))
                            fuzzy_item["source"] = "fuzzy+ai_fill"

                    final_results.append(fuzzy_item)
                    continue

                # AI 补全
                ai_item = _ai_complete_recipe(name)
                if ai_item:
                    final_results.append(ai_item)
                else:
                    final_results.append({
                        "name": name,
                        "calories": 0,
                        "protein": 0,
                        "fat": 0,
                        "carbs": 0,
                        "ingredients": "",
                        "steps": "",
                        "source": "empty"
                    })

            return Response({"status": "success", "data": final_results})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class MealEventView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        date_str = request.data.get("date") # 比如 2026-03-06
        recipe_names = request.data.get("recipe_names", []) # 传个数组 ['西红柿炒蛋', '米饭']

        success = EpisodicMemory.record_meal_event(user_id, recipe_names, date_str)
        if success:
            return Response({"status": "success", "message": "已记入饮食历史档案！"})
        return Response({"error": "记录失败"}, status=500)

    def get(self, request):
        user_id = request.query_params.get("user_id")
        # 提取过去 14 天的记录发给前端
        history = EpisodicMemory.get_recent_meals(user_id, days_limit=14)
        return Response({"history": history})

class FoodSearchView(APIView):
    """搜索食物/菜谱的营养信息"""
    def get(self, request):
        keyword = request.query_params.get("q", "").strip()
        if not keyword:
            return Response({"error": "请输入搜索关键词"}, status=400)

        cypher = """
        MATCH (n)
        WHERE (n:Recipe OR n:Ingredient)
          AND n.name CONTAINS $keyword
        RETURN labels(n)[0] AS type,
               n.name AS name,
               n.calories AS calories,
               n.protein AS protein,
               n.fat AS fat,
               n.carbs AS carbs
        LIMIT 20
        """
        try:
            results = graph_db.query(cypher, {"keyword": keyword})
            return Response({"data": results})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class IngredientDetailView(APIView):
    """食材详情查询：完整营养属性 + 关系图信息（互补/互斥/重叠）"""
    def get(self, request):
        name = request.query_params.get("name", "").strip()
        if not name:
            return Response({"error": "请输入食材名"}, status=400)

        ingredient_cypher = """
        MATCH (i:Ingredient)
        WHERE toLower(i.name) = toLower($name)
           OR toLower(i.name) CONTAINS toLower($name)
           OR toLower($name) CONTAINS toLower(i.name)
        RETURN i.name AS name, properties(i) AS props
        ORDER BY CASE WHEN toLower(i.name) = toLower($name) THEN 0 ELSE 1 END, size(i.name) ASC
        LIMIT 1
        """

        relation_cypher = """
        MATCH (i:Ingredient {name: $name})
        OPTIONAL MATCH (i)-[r]-(other:Ingredient)
        RETURN type(r) AS relation_type,
               other.name AS related_name,
               coalesce(r.reason, r.desc, '') AS reason,
               CASE WHEN startNode(r) = i THEN 'out' ELSE 'in' END AS direction
        LIMIT 300
        """

        try:
            ingredient_result = graph_db.query(ingredient_cypher, {"name": name})
            if not ingredient_result:
                return Response({"error": "未找到该食材"}, status=404)

            item = ingredient_result[0]
            ingredient_name = item.get("name")
            props = item.get("props") or {}

            nutrients_raw = props.get("nutrients_raw")
            nutrients_detail = {}
            if nutrients_raw:
                try:
                    parsed = json.loads(nutrients_raw)
                    if isinstance(parsed, dict):
                        nutrients_detail = parsed
                except Exception:
                    nutrients_detail = {"raw_text": str(nutrients_raw)}

            relation_rows = graph_db.query(relation_cypher, {"name": ingredient_name})

            complement_types = {"SYNERGY_WITH", "MATCH_WITH", "PAIR_WITH", "COMPLEMENT_WITH", "GOOD_WITH", "SUITABLE_WITH"}
            conflict_types = {"CLASH_WITH", "CONFLICTS_WITH", "INCOMPATIBLE_WITH", "AVOID_WITH", "RESTRAIN_WITH"}
            overlap_types = {"OVERLAP_WITH", "SIMILAR_TO", "SUBSTITUTE_WITH", "SAME_CATEGORY_WITH"}

            complements, conflicts, overlaps, all_relations = [], [], [], []

            for r in relation_rows:
                r_type = (r.get("relation_type") or "").upper()
                target = r.get("related_name")
                reason = r.get("reason") or ""
                direction = r.get("direction") or "out"
                if not r_type or not target:
                    continue

                row = {
                    "name": target,
                    "reason": reason,
                    "relation_type": r_type,
                    "direction": direction,
                }
                all_relations.append(row)

                reason_text = str(reason)
                if r_type in complement_types or ("互补" in reason_text or "相宜" in reason_text or "搭配" in reason_text):
                    complements.append(row)
                elif r_type in conflict_types or ("禁忌" in reason_text or "相克" in reason_text or "冲突" in reason_text):
                    conflicts.append(row)
                elif r_type in overlap_types or ("重叠" in reason_text or "类似" in reason_text):
                    overlaps.append(row)

            cleaned_props = {}
            for k, v in props.items():
                if v is None:
                    continue
                if isinstance(v, str) and len(v.strip()) == 0:
                    continue
                if k in {"embedding", "vector", "feature_vector"}:
                    continue
                cleaned_props[k] = _to_json_safe(v)

            return Response({
                "status": "success",
                "data": {
                    "name": ingredient_name,
                    "all_properties": cleaned_props,
                    "nutrients_detail": _to_json_safe(nutrients_detail),
                    "relations": {
                        "complements": _to_json_safe(complements),
                        "conflicts": _to_json_safe(conflicts),
                        "overlaps": _to_json_safe(overlaps),
                        "all": _to_json_safe(all_relations),
                    }
                }
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class DietLogView(APIView):
    """饮食记录：记录/查询用户每日摄入"""
    def post(self, request):
        user_id = request.data.get("user_id")
        date_str = request.data.get("date", datetime.now().strftime("%Y-%m-%d"))
        meal_type = request.data.get("meal_type", "lunch")  # breakfast/lunch/dinner/snack
        food_name = request.data.get("food_name", "")
        calories = request.data.get("calories", 0)
        protein = request.data.get("protein", 0)
        fat = request.data.get("fat", 0)
        carbs = request.data.get("carbs", 0)
        amount = request.data.get("amount", 1)

        if not user_id or not food_name:
            return Response({"error": "缺少必要参数"}, status=400)

        log_id = str(uuid.uuid4())[:8]
        cypher = """
        MATCH (u:User {id: $user_id})
        CREATE (log:DietLog {
            id: $log_id, user_id: $user_id, date: $date,
            meal_type: $meal_type, food_name: $food_name,
            calories: $calories, protein: $protein,
            fat: $fat, carbs: $carbs, amount: $amount
        })
        MERGE (u)-[:HAS_LOG]->(log)
        RETURN log.id AS id
        """
        try:
            graph_db.query(cypher, {
                "user_id": user_id, "log_id": log_id, "date": date_str,
                "meal_type": meal_type, "food_name": food_name,
                "calories": float(calories), "protein": float(protein),
                "fat": float(fat), "carbs": float(carbs), "amount": float(amount)
            })
            return Response({"status": "success", "id": log_id})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def get(self, request):
        user_id = request.query_params.get("user_id")
        date_str = request.query_params.get("date")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        if start_date and end_date:
            cypher = """
            MATCH (u:User {id: $user_id})-[:HAS_LOG]->(log:DietLog)
            WHERE log.date >= $start_date AND log.date <= $end_date
            RETURN log.id AS id, log.date AS date, log.meal_type AS meal_type,
                   log.food_name AS food_name, log.calories AS calories,
                   log.protein AS protein, log.fat AS fat,
                   log.carbs AS carbs, log.amount AS amount
            ORDER BY log.date DESC, CASE log.meal_type
                WHEN 'breakfast' THEN 1 WHEN 'lunch' THEN 2
                WHEN 'dinner' THEN 3 ELSE 4
            END
            """
            params = {"user_id": user_id, "start_date": start_date, "end_date": end_date}
        else:
            if not date_str:
                date_str = datetime.now().strftime("%Y-%m-%d")
            cypher = """
            MATCH (u:User {id: $user_id})-[:HAS_LOG]->(log:DietLog {date: $date})
            RETURN log.id AS id, log.meal_type AS meal_type,
                   log.food_name AS food_name, log.calories AS calories,
                   log.protein AS protein, log.fat AS fat,
                   log.carbs AS carbs, log.amount AS amount
            ORDER BY CASE log.meal_type
                WHEN 'breakfast' THEN 1 WHEN 'lunch' THEN 2
                WHEN 'dinner' THEN 3 ELSE 4
            END
            """
            params = {"user_id": user_id, "date": date_str}

        try:
            results = graph_db.query(cypher, params)
            return Response({"logs": results})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def delete(self, request):
        user_id = request.query_params.get("user_id")
        log_id = request.query_params.get("log_id")
        if not user_id or not log_id:
            return Response({"error": "缺少参数"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})-[:HAS_LOG]->(log:DietLog {id: $log_id})
        DETACH DELETE log
        """
        try:
            graph_db.query(cypher, {"user_id": user_id, "log_id": log_id})
            return Response({"status": "success"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class NutritionSummaryView(APIView):
    """营养摘要：获取某日期范围的营养汇总"""
    def get(self, request):
        user_id = request.query_params.get("user_id")
        days = int(request.query_params.get("days", 7))
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        date_list = []
        for i in range(days - 1, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            date_list.append(d)

        cypher = """
        MATCH (u:User {id: $user_id})-[:HAS_LOG]->(log:DietLog)
        WHERE log.date IN $dates
        RETURN log.date AS date,
               sum(log.calories) AS total_calories,
               sum(log.protein) AS total_protein,
               sum(log.fat) AS total_fat,
               sum(log.carbs) AS total_carbs
        ORDER BY log.date
        """
        try:
            results = graph_db.query(cypher, {"user_id": user_id, "dates": date_list})
            result_map = {r["date"]: r for r in results}
            full_data = []
            for d in date_list:
                if d in result_map:
                    r = result_map[d]
                    full_data.append({
                        "date": d,
                        "calories": r.get("total_calories", 0),
                        "protein": r.get("total_protein", 0),
                        "fat": r.get("total_fat", 0),
                        "carbs": r.get("total_carbs", 0)
                    })
                else:
                    full_data.append({"date": d, "calories": 0, "protein": 0, "fat": 0, "carbs": 0})
            return Response({"summary": full_data})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class RecommendMealsView(APIView):
    """自动推荐一日三餐"""
    def get(self, request):
        user_id = request.query_params.get("user_id")

        profile = SemanticMemory.get_user_profile(user_id) if user_id else {}
        dislikes = profile.get("dislikes", [])
        allergies = profile.get("allergies", [])
        avoid_list = dislikes + allergies

        avoid_filter = ""
        if avoid_list:
            conditions = " AND ".join([f"NOT n.name CONTAINS '{item}' AND NOT n.ingredients_raw CONTAINS '{item}'" for item in avoid_list])
            avoid_filter = f"AND {conditions}"

        breakfast_cypher = f"""
        MATCH (n:Recipe)
        WHERE n.calories < 400 AND n.calories > 100
        {avoid_filter}
        WITH n, rand() AS r
        ORDER BY r
        RETURN n.name AS name, n.calories AS calories,
               n.protein AS protein, n.fat AS fat, n.carbs AS carbs
        LIMIT 3
        """

        lunch_cypher = f"""
        MATCH (n:Recipe)
        WHERE n.calories >= 300 AND n.calories <= 700
        {avoid_filter}
        WITH n, rand() AS r
        ORDER BY r
        RETURN n.name AS name, n.calories AS calories,
               n.protein AS protein, n.fat AS fat, n.carbs AS carbs
        LIMIT 4
        """

        dinner_cypher = f"""
        MATCH (n:Recipe)
        WHERE n.calories >= 200 AND n.calories <= 500
        {avoid_filter}
        WITH n, rand() AS r
        ORDER BY r
        RETURN n.name AS name, n.calories AS calories,
               n.protein AS protein, n.fat AS fat, n.carbs AS carbs
        LIMIT 3
        """
        try:
            breakfast = graph_db.query(breakfast_cypher)
            lunch = graph_db.query(lunch_cypher)
            dinner = graph_db.query(dinner_cypher)
            return Response({
                "breakfast": breakfast,
                "lunch": lunch,
                "dinner": dinner
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class FavoriteIngredientsView(APIView):
    """管理用户常用食材偏好"""
    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})
        RETURN coalesce(u.favorite_ingredients, []) AS favorites
        """
        try:
            result = graph_db.query(cypher, {"user_id": user_id})
            return Response({"favorites": result[0]["favorites"] if result else []})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def post(self, request):
        user_id = request.data.get("user_id")
        favorites = request.data.get("favorites", [])
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})
        SET u.favorite_ingredients = $favorites
        RETURN u.favorite_ingredients
        """
        try:
            graph_db.query(cypher, {"user_id": user_id, "favorites": favorites})
            return Response({"status": "success"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class SimilarIngredientView(APIView):
    """搜索相似/同功能食材（用于收藏夹替换）"""
    def get(self, request):
        name = request.query_params.get("name", "").strip()
        if not name:
            return Response({"error": "缺少食材名"}, status=400)

        cypher = """
        MATCH (n:Ingredient {name: $name})
        OPTIONAL MATCH (n)-[:CATEGORY]->(cat)<-[:CATEGORY]-(sim:Ingredient)
        WHERE sim.name <> $name
        RETURN DISTINCT sim.name AS name,
               sim.calories AS calories,
               sim.protein AS protein,
               sim.fat AS fat,
               sim.carbs AS carbs
        LIMIT 10
        """
        try:
            results = graph_db.query(cypher, {"name": name})
            if not results:
                fallback = """
                MATCH (n:Ingredient)
                WHERE n.name <> $name AND n.name CONTAINS $keyword
                RETURN n.name AS name,
                       n.calories AS calories,
                       n.protein AS protein,
                       n.fat AS fat,
                       n.carbs AS carbs
                LIMIT 10
                """
                keyword = name[:2] if len(name) >= 2 else name
                results = graph_db.query(fallback, {"name": name, "keyword": keyword})
            return Response({"similar": [r["name"] for r in results if r.get("name")]})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class FoodConflictView(APIView):
    """查询食物相克/不能同食信息"""
    def get(self, request):
        name = request.query_params.get("name", "").strip()
        if not name:
            return Response({"error": "缺少食材名"}, status=400)

        cypher = """
        MATCH (a:Ingredient {name: $name})-[r:CONFLICTS_WITH]->(b:Ingredient)
        RETURN b.name AS name, r.reason AS reason
        UNION
        MATCH (b:Ingredient)-[r:CONFLICTS_WITH]->(a:Ingredient {name: $name})
        RETURN b.name AS name, r.reason AS reason
        """
        try:
            results = graph_db.query(cypher, {"name": name})
            return Response({"conflicts": [r["name"] for r in results if r.get("name")]})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class UserCollectionView(APIView):
    """用户收藏夹(菜谱收藏)"""
    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})-[:COLLECTED]->(c:Collection)
        RETURN c.id AS id, c.name AS recipe_name, c.calories AS calories,
               c.protein AS protein, c.fat AS fat, c.carbs AS carbs,
               c.ingredients_raw AS ingredients,
               c.steps AS steps,
               c.added_at AS added_at
        ORDER BY c.added_at DESC
        """
        try:
            results = graph_db.query(cypher, {"user_id": user_id})
            return Response({"collections": results})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def post(self, request):
        user_id = request.data.get("user_id")
        recipe_name = request.data.get("recipe_name", request.data.get("name", ""))
        calories = request.data.get("calories", 0)
        protein = request.data.get("protein", 0)
        fat = request.data.get("fat", 0)
        carbs = request.data.get("carbs", 0)
        ingredients_raw = request.data.get("ingredients", request.data.get("ingredients_raw", ""))
        steps = request.data.get("steps", "")

        if not user_id or not recipe_name:
            return Response({"error": "缺少参数"}, status=400)

        cid = str(uuid.uuid4())[:8]
        cypher = """
        MATCH (u:User {id: $user_id})
        MERGE (c:Collection {user_id: $user_id, name: $name})
        ON CREATE SET c.id = $cid, c.calories = $calories,
                      c.protein = $protein, c.fat = $fat, c.carbs = $carbs,
                      c.ingredients_raw = $ingredients_raw, c.steps = $steps,
                      c.added_at = $added_at
                ON MATCH SET c.calories = CASE
                                                WHEN coalesce(c.calories, 0) = 0 AND $calories > 0 THEN $calories
                                                ELSE c.calories END,
                                            c.protein = CASE
                                                WHEN coalesce(c.protein, 0) = 0 AND $protein > 0 THEN $protein
                                                ELSE c.protein END,
                                            c.fat = CASE
                                                WHEN coalesce(c.fat, 0) = 0 AND $fat > 0 THEN $fat
                                                ELSE c.fat END,
                                            c.carbs = CASE
                                                WHEN coalesce(c.carbs, 0) = 0 AND $carbs > 0 THEN $carbs
                                                ELSE c.carbs END,
                                            c.ingredients_raw = CASE
                                                WHEN c.ingredients_raw IS NULL OR trim(toString(c.ingredients_raw)) = '' OR trim(toString(c.ingredients_raw)) = '[]'
                                                THEN $ingredients_raw
                                                ELSE c.ingredients_raw END,
                                            c.steps = CASE
                                                WHEN c.steps IS NULL OR trim(toString(c.steps)) = '' OR trim(toString(c.steps)) = '[]'
                                                THEN $steps
                                                ELSE c.steps END
        MERGE (u)-[:COLLECTED]->(c)
        RETURN c.id AS id
        """
        try:
            graph_db.query(cypher, {
                "user_id": user_id, "name": recipe_name, "cid": cid,
                "calories": float(calories), "protein": float(protein),
                "fat": float(fat), "carbs": float(carbs),
                "ingredients_raw": ingredients_raw, "steps": steps,
                "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return Response({"status": "success", "id": cid})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def delete(self, request):
        user_id = request.query_params.get("user_id")
        recipe_name = request.query_params.get("recipe_name")
        cid = request.query_params.get("id")
        if not user_id or (not cid and not recipe_name):
            return Response({"error": "缺少参数"}, status=400)

        if recipe_name:
            cypher = """
            MATCH (u:User {id: $user_id})-[:COLLECTED]->(c:Collection {name: $recipe_name})
            DETACH DELETE c
            """
            params = {"user_id": user_id, "recipe_name": recipe_name}
        else:
            cypher = """
            MATCH (u:User {id: $user_id})-[:COLLECTED]->(c:Collection {id: $cid})
            DETACH DELETE c
            """
            params = {"user_id": user_id, "cid": cid}
        try:
            graph_db.query(cypher, params)
            return Response({"status": "success"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ChatHistoryView(APIView):
    """保存和获取聊天历史"""
    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})-[:HAS_CHAT]->(s:ChatSession)
        OPTIONAL MATCH (s)-[:HAS_MSG]->(m:ChatMessage)
        WITH s, m ORDER BY m.timestamp ASC
        WITH s, collect({role: m.role, content: m.content, timestamp: m.timestamp}) AS msgs
        RETURN s.id AS session_id, s.title AS title,
               s.created_at AS created_at, msgs
        ORDER BY s.created_at DESC
        """
        try:
            results = graph_db.query(cypher, {"user_id": user_id})
            return Response({"sessions": results})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def post(self, request):
        user_id = request.data.get("user_id")
        session_id = request.data.get("session_id", "")
        title = request.data.get("title", "新对话")
        messages_data = request.data.get("messages", [])

        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cypher = """
        MATCH (u:User {id: $user_id})
        MERGE (s:ChatSession {id: $session_id, user_id: $user_id})
        ON CREATE SET s.title = $title, s.created_at = $now
        ON MATCH SET s.title = $title
        MERGE (u)-[:HAS_CHAT]->(s)
        """
        try:
            graph_db.query(cypher, {
                "user_id": user_id, "session_id": session_id,
                "title": title, "now": now
            })

            del_cypher = """
            MATCH (s:ChatSession {id: $session_id})-[:HAS_MSG]->(m:ChatMessage)
            DETACH DELETE m
            """
            graph_db.query(del_cypher, {"session_id": session_id})

            for i, msg in enumerate(messages_data):
                msg_cypher = """
                MATCH (s:ChatSession {id: $session_id})
                CREATE (m:ChatMessage {
                    role: $role, content: $content,
                    timestamp: $ts, idx: $idx
                })
                CREATE (s)-[:HAS_MSG]->(m)
                """
                graph_db.query(msg_cypher, {
                    "session_id": session_id,
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "ts": now, "idx": i
                })

            return Response({"status": "success", "session_id": session_id})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def delete(self, request):
        user_id = request.query_params.get("user_id")
        session_id = request.query_params.get("session_id")
        if not user_id or not session_id:
            return Response({"error": "缺少参数"}, status=400)

        cypher = """
        MATCH (s:ChatSession {id: $session_id, user_id: $user_id})
        OPTIONAL MATCH (s)-[:HAS_MSG]->(m:ChatMessage)
        DETACH DELETE s, m
        """
        try:
            graph_db.query(cypher, {"user_id": user_id, "session_id": session_id})
            return Response({"status": "success"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)