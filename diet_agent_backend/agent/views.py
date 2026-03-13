import uuid
import json
import os
import re
import secrets
import difflib
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
_admin_sessions = {}
_user_id_constraint_ready = False

ADMIN_DEFAULT_ID = os.getenv("ADMIN_DEFAULT_ID", "admin")
ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "123")

SYNONYM_DICT = {
    "小麦粉(标准粉)": "小麦粉(标准粉)",
    "小麦粉": "小麦粉(标准粉)",
    "西红柿": "番茄",
    "地瓜": "红薯",
    "马铃薯": "土豆",
    "洋芋": "土豆",
    "大蒜": "蒜",
    "姜": "生姜",
    "鲜牛奶": "牛奶",
    "纯牛奶": "牛奶",
    "瘦肉": "猪肉(瘦)",
    "精肉": "猪肉(瘦)",
}


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


def _issue_admin_token():
    token = secrets.token_urlsafe(24)
    _admin_sessions[token] = datetime.now() + timedelta(hours=12)
    return token


def _validate_admin_token(request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return False
    expire_at = _admin_sessions.get(token)
    if not expire_at:
        return False
    if datetime.now() > expire_at:
        _admin_sessions.pop(token, None)
        return False
    return True


def _safe_float(value):
    if value is None:
        return None
    try:
        if str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def _clean_name_for_match(name: str):
    if not name:
        return ""
    raw = str(name).strip()
    if raw in SYNONYM_DICT:
        return SYNONYM_DICT[raw]
    name_clean = re.sub(r"\(.*?\)", "", raw).strip()
    name_clean = re.sub(r"（.*?）", "", name_clean).strip()
    return SYNONYM_DICT.get(name_clean, name_clean)


def _find_or_create_relation_name(raw_name: str, valid_names: set):
    if not raw_name:
        return "", False

    name = str(raw_name).strip()
    if name in valid_names:
        return name, False

    cleaned = _clean_name_for_match(name)
    if cleaned in valid_names:
        return cleaned, False

    matches = difflib.get_close_matches(cleaned, list(valid_names), n=1, cutoff=0.85)
    if matches:
        return matches[0], False

    return cleaned, True


def _read_admin_import_payload(request):
    import_type = str(request.data.get("import_type", "")).strip().lower()
    upload = request.FILES.get("file")
    file_path = str(request.data.get("file_path", "")).strip()

    if import_type not in {"ingredient", "recipe", "relation"}:
        raise ValueError("import_type 必须是 ingredient / recipe / relation")
    if not upload and not file_path:
        raise ValueError("请上传 JSON 文件，或填写服务器可读的 JSON 绝对路径")

    if file_path:
        if not os.path.isabs(file_path):
            raise ValueError("file_path 必须是绝对路径")
        if not file_path.lower().endswith(".json"):
            raise ValueError("file_path 必须指向 .json 文件")
        if not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")
        with open(file_path, "r", encoding="utf-8-sig") as f:
            raw_text = f.read()
        source = "path"
        file_name = os.path.basename(file_path)
    else:
        raw_text = upload.read().decode("utf-8-sig")
        source = "upload"
        file_name = str(getattr(upload, "name", "uploaded.json"))

    payload = json.loads(raw_text)
    return {
        "import_type": import_type,
        "payload": payload,
        "source": source,
        "file_path": file_path,
        "file_name": file_name,
    }


def _ensure_user_id_constraint():
    global _user_id_constraint_ready
    if _user_id_constraint_ready:
        return
    try:
        graph_db.query(
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE"
        )
        _user_id_constraint_ready = True
    except Exception as e:
        # Do not block auth flow if constraint creation fails in restricted environments.
        print(f"WARNING: ensure user id constraint failed: {e}")

# 用户注册与登录接口
class UserAuthView(APIView):
    def post(self, request):
        _ensure_user_id_constraint()

        user_id = str(request.data.get("user_id", "")).strip()
        password = str(request.data.get("password", "")).strip()
        action = request.data.get("action")
        name = str(request.data.get("name", "新用户")).strip()

        print(f"\n=== 收到验证请求: action={action}, user_id={user_id} ===")

        if not user_id or not password:
            return Response({"error": "账号和密码不能为空"}, status=400)

        # 注册账号仅允许字母、数字、短横杠、下划线
        if action == 'register' and not re.fullmatch(r"[A-Za-z0-9_-]+", user_id):
            return Response({"error": "User ID 仅允许字母、数字、短横杠(-)和下划线(_)"}, status=400)

        if action == 'register':
            check_cypher = "MATCH (u:User {id: $user_id}) RETURN u"
            existing_user = graph_db.query(check_cypher, {"user_id": user_id})

            if existing_user:
                print("注册失败：账号已存在")
                return Response({"error": "该账号已被注册，请直接登录"}, status=400)

            hashed_password = make_password(password)
            print(f"注册准备写入 -> 明文密码: {password} | 加密结果: {hashed_password[:15]}...")

            create_cypher = """
            CREATE (u:User {id: $user_id, name: $name, password: $password, created_at: $created_at})
            RETURN u
            """
            try:
                graph_db.query(create_cypher, {
                    "user_id": user_id,
                    "name": name,
                    "password": hashed_password,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                print("注册成功，数据已写入 Neo4j")
                return Response({"status": "success", "message": "注册成功"})
            except Exception as e:
                print(f"数据库写入失败: {e}")
                return Response({"error": f"数据库写入失败: {e}"}, status=500)

        elif action == 'login':
            login_cypher = "MATCH (u:User {id: $user_id}) RETURN u.password AS db_password, coalesce(u.name, '') AS user_name"
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
                return Response({
                    "status": "success",
                    "message": "登录成功",
                    "user_name": result[0].get("user_name", "")
                })
            else:
                print(f"密码校验失败！前端传来的明文是: '{password}'")
                return Response({"error": "密码错误，请重试"}, status=401)

        else:
            return Response({"error": "无效的操作"}, status=400)


class AdminAuthView(APIView):
    """管理员登录（默认账号：admin / 123）"""
    def post(self, request):
        admin_id = str(request.data.get("admin_id", "")).strip()
        password = str(request.data.get("password", "")).strip()

        if not admin_id or not password:
            return Response({"error": "管理员账号和密码不能为空"}, status=400)

        if admin_id != ADMIN_DEFAULT_ID or password != ADMIN_DEFAULT_PASSWORD:
            return Response({"error": "管理员账号或密码错误"}, status=401)

        token = _issue_admin_token()
        return Response({
            "status": "success",
            "message": "管理员登录成功",
            "token": token,
            "admin_id": admin_id,
        })


class AdminOverviewView(APIView):
    """管理员总览：用户注册信息、偏好信息、历史记录"""
    def get(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        try:
            users_cypher = """
            MATCH (u:User)
            RETURN u.id AS user_id,
                   coalesce(u.name, '') AS name,
                   coalesce(u.created_at, '') AS created_at,
                   coalesce(u.birth_date, '') AS birth_date,
                   coalesce(u.gender, '') AS gender,
                   coalesce(u.height, 0) AS height,
                   coalesce(u.weight, 0) AS weight,
                   coalesce(u.allergies, []) AS allergies,
                   coalesce(u.dislikes, []) AS dislikes,
                   coalesce(u.favorite_ingredients, []) AS favorite_ingredients,
                   coalesce(u.positive_feedback, []) AS positive_feedback
            ORDER BY u.id
            """
            users = graph_db.query(users_cypher)

            logs_cypher = """
            MATCH (u:User)-[:HAS_LOG]->(log:DietLog)
            RETURN u.id AS user_id,
                   log.id AS log_id,
                   log.date AS date,
                   log.meal_type AS meal_type,
                   log.food_name AS food_name,
                   log.calories AS calories,
                   log.protein AS protein,
                   log.fat AS fat,
                   log.carbs AS carbs,
                   log.amount AS amount
            ORDER BY log.date DESC
            """
            log_rows = graph_db.query(logs_cypher)

            chat_cypher = """
            MATCH (u:User)-[:HAS_CHAT]->(s:ChatSession)
            OPTIONAL MATCH (s)-[:HAS_MSG]->(m:ChatMessage)
            WITH u.id AS user_id, s, count(m) AS msg_count
            RETURN user_id,
                   s.id AS session_id,
                   coalesce(s.title, '') AS title,
                   coalesce(s.created_at, '') AS created_at,
                   msg_count
            ORDER BY s.created_at DESC
            """
            chat_rows = graph_db.query(chat_cypher)

            logs_map = {}
            for row in log_rows:
                uid = row.get("user_id")
                if not uid:
                    continue
                logs_map.setdefault(uid, [])
                if len(logs_map[uid]) < 20:
                    logs_map[uid].append(_to_json_safe(row))

            chats_map = {}
            for row in chat_rows:
                uid = row.get("user_id")
                if not uid:
                    continue
                chats_map.setdefault(uid, [])
                if len(chats_map[uid]) < 10:
                    chats_map[uid].append(_to_json_safe(row))

            merged_users = []
            for u in users:
                uid = u.get("user_id")
                merged_users.append({
                    "user_id": uid,
                    "registration": {
                        "name": u.get("name", ""),
                        "created_at": u.get("created_at", ""),
                        "birth_date": u.get("birth_date", ""),
                        "gender": u.get("gender", ""),
                        "height": u.get("height", 0),
                        "weight": u.get("weight", 0),
                    },
                    "preferences": {
                        "allergies": _to_json_safe(u.get("allergies", [])),
                        "dislikes": _to_json_safe(u.get("dislikes", [])),
                        "favorite_ingredients": _to_json_safe(u.get("favorite_ingredients", [])),
                        "positive_feedback": _to_json_safe((u.get("positive_feedback", []) or [])[-5:]),
                    },
                    "history": {
                        "diet_logs": logs_map.get(uid, []),
                        "chat_sessions": chats_map.get(uid, []),
                    },
                })

            total_logs = sum(len(v) for v in logs_map.values())
            total_chats = sum(len(v) for v in chats_map.values())

            return Response({
                "status": "success",
                "stats": {
                    "user_count": len(merged_users),
                    "diet_log_count": total_logs,
                    "chat_session_count": total_chats,
                },
                "users": merged_users,
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class AdminDataImportView(APIView):
    """管理员数据更新：上传 JSON 并导入（食材 / 菜谱 / 食材关系）"""

    def post(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        task_id = str(uuid.uuid4())[:12]
        started_at = datetime.now()
        started_at_text = started_at.strftime("%Y-%m-%d %H:%M:%S")
        try:
            parsed = _read_admin_import_payload(request)
        except Exception as e:
            return Response({"error": f"JSON 解析失败: {e}"}, status=400)

        import_type = parsed["import_type"]
        payload = parsed["payload"]
        source = parsed["source"]
        file_path = parsed["file_path"]
        file_name = parsed["file_name"]

        self._create_import_task(
            task_id=task_id,
            import_type=import_type,
            source=source,
            file_path=file_path,
            file_name=file_name,
            started_at=started_at_text,
        )

        try:
            if import_type == "ingredient":
                stats = self._import_ingredients(payload, task_id=task_id)
            elif import_type == "recipe":
                stats = self._import_recipes(payload, task_id=task_id)
            else:
                stats = self._import_relations(payload, task_id=task_id)

            ended_at = datetime.now()
            ended_at_text = ended_at.strftime("%Y-%m-%d %H:%M:%S")
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)
            self._finish_import_task(task_id, "success", ended_at_text, duration_ms, stats=stats)

            return Response({
                "status": "success",
                "import_type": import_type,
                "task_id": task_id,
                "source": source,
                "file_path": file_path,
                "file_name": file_name,
                "started_at": started_at_text,
                "ended_at": ended_at_text,
                "duration_ms": duration_ms,
                "stats": stats,
            })
        except Exception as e:
            ended_at = datetime.now()
            ended_at_text = ended_at.strftime("%Y-%m-%d %H:%M:%S")
            duration_ms = int((ended_at - started_at).total_seconds() * 1000)
            self._finish_import_task(task_id, "failed", ended_at_text, duration_ms, error=str(e))
            return Response({"error": f"导入失败: {e}"}, status=500)

    def _create_import_task(self, task_id, import_type, source, file_path, file_name, started_at):
        cypher = """
        CREATE (t:ImportTask {
            id: $task_id,
            import_type: $import_type,
            source: $source,
            file_path: $file_path,
            file_name: $file_name,
            started_at: $started_at,
            status: 'running',
            created_at: $started_at
        })
        """
        graph_db.query(cypher, {
            "task_id": task_id,
            "import_type": import_type,
            "source": source,
            "file_path": file_path,
            "file_name": file_name,
            "started_at": started_at,
        })

    def _finish_import_task(self, task_id, status, ended_at, duration_ms, stats=None, error=None):
        cypher = """
        MATCH (t:ImportTask {id: $task_id})
        SET t.status = $status,
            t.ended_at = $ended_at,
            t.duration_ms = $duration_ms,
            t.stats_json = $stats_json,
            t.error = $error
        """
        graph_db.query(cypher, {
            "task_id": task_id,
            "status": status,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "stats_json": json.dumps(stats or {}, ensure_ascii=False),
            "error": str(error or ""),
        })

    def _import_ingredients(self, data, task_id=None):
        if not isinstance(data, list):
            raise ValueError("食材 JSON 必须是数组")

        dedup = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            nutrients = item.get("nutrients", {}) if isinstance(item.get("nutrients"), dict) else {}
            existing = dedup.get(name, {
                "name": name,
                "original_name": "",
                "category": "",
                "cal_per_100g": None,
                "unit_info": [],
                "nutrients": {},
                "raw_items": [],
            })

            existing["original_name"] = str(item.get("original_name") or existing["original_name"] or name).strip()
            existing["category"] = str(item.get("category") or existing["category"] or "Other").strip() or "Other"
            cp = _safe_float(item.get("cal_per_100g"))
            if cp is not None:
                existing["cal_per_100g"] = cp

            unit_info = item.get("unit_info", [])
            if isinstance(unit_info, list):
                existing["unit_info"].extend(unit_info)

            existing["nutrients"].update(nutrients)
            existing["raw_items"].append(item)
            dedup[name] = existing

        upsert_query = """
        MERGE (i:Ingredient {name: $name})
        ON CREATE SET i.created_at = $now
        SET i.updated_at = $now,
            i.original_name = CASE WHEN $original_name <> '' THEN $original_name ELSE coalesce(i.original_name, $name) END,
            i.category = CASE WHEN $category <> '' THEN $category ELSE coalesce(i.category, 'Other') END,
            i.calories = CASE WHEN $calories IS NULL THEN i.calories ELSE $calories END,
            i.protein = CASE WHEN $protein IS NULL THEN i.protein ELSE $protein END,
            i.fat = CASE WHEN $fat IS NULL THEN i.fat ELSE $fat END,
            i.carbs = CASE WHEN $carbs IS NULL THEN i.carbs ELSE $carbs END,
            i.fiber = CASE WHEN $fiber IS NULL THEN i.fiber ELSE $fiber END,
            i.cal_per_100g = CASE WHEN $cal_per_100g IS NULL THEN i.cal_per_100g ELSE $cal_per_100g END,
            i.unit_info = CASE WHEN $unit_info = '' THEN i.unit_info ELSE $unit_info END,
            i.nutrients_raw = CASE WHEN $nutrients_raw = '' THEN i.nutrients_raw ELSE $nutrients_raw END,
            i.nutrient_count = CASE WHEN $nutrient_count IS NULL THEN i.nutrient_count ELSE $nutrient_count END,
            i.missing_info = false,
            i.source = 'admin_upload'
        """

        nutrient_rel_query = """
        MATCH (i:Ingredient {name: $ingredient_name})
        MERGE (n:Nutrient {name: $nutrient_name})
        SET n.updated_at = $now
        MERGE (i)-[r:HAS_NUTRIENT]->(n)
        SET r.value = $value, r.unit = $unit, r.updated_at = $now
        """

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nutrient_rel_count = 0
        with graph_db.driver.session() as session:
            for row in dedup.values():
                nutrients = row.get("nutrients", {}) if isinstance(row.get("nutrients"), dict) else {}
                calories = _safe_float((nutrients.get("热量") or {}).get("value") if isinstance(nutrients.get("热量"), dict) else None)
                protein = _safe_float((nutrients.get("蛋白质") or {}).get("value") if isinstance(nutrients.get("蛋白质"), dict) else None)
                fat = _safe_float((nutrients.get("脂肪") or {}).get("value") if isinstance(nutrients.get("脂肪"), dict) else None)
                carbs = _safe_float((nutrients.get("碳水化合物") or {}).get("value") if isinstance(nutrients.get("碳水化合物"), dict) else None)
                fiber = _safe_float((nutrients.get("纤维素") or {}).get("value") if isinstance(nutrients.get("纤维素"), dict) else None)

                unit_unique = []
                seen_u = set()
                for u in row.get("unit_info", []):
                    key = json.dumps(u, ensure_ascii=False, sort_keys=True)
                    if key in seen_u:
                        continue
                    seen_u.add(key)
                    unit_unique.append(u)

                session.run(upsert_query, {
                    "name": row["name"],
                    "original_name": row.get("original_name") or row["name"],
                    "category": row.get("category") or "Other",
                    "calories": calories,
                    "protein": protein,
                    "fat": fat,
                    "carbs": carbs,
                    "fiber": fiber,
                    "cal_per_100g": row.get("cal_per_100g"),
                    "unit_info": json.dumps(unit_unique, ensure_ascii=False),
                    "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
                    "nutrient_count": len(nutrients.keys()),
                    "now": now,
                })

                for nk, nv in nutrients.items():
                    if isinstance(nv, dict):
                        session.run(nutrient_rel_query, {
                            "ingredient_name": row["name"],
                            "nutrient_name": str(nk),
                            "value": _safe_float(nv.get("value")),
                            "unit": str(nv.get("unit") or "").strip(),
                            "now": now,
                        })
                        nutrient_rel_count += 1

        return {
            "input_records": len(data),
            "deduped_ingredients": len(dedup),
            "upserted_ingredients": len(dedup),
            "upserted_nutrient_relations": nutrient_rel_count,
        }

    def _import_recipes(self, data, task_id=None):
        if not isinstance(data, list):
            raise ValueError("菜谱 JSON 必须是数组")

        dedup = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            dedup[name] = item

        upsert_query = """
        MERGE (r:Recipe {name: $name})
        ON CREATE SET r.created_at = $now
        SET r.updated_at = $now,
            r.category = CASE WHEN $category <> '' THEN $category ELSE r.category END,
            r.image = CASE WHEN $image <> '' THEN $image ELSE r.image END,
            r.calories = CASE WHEN $calories IS NULL THEN r.calories ELSE $calories END,
            r.protein = CASE WHEN $protein IS NULL THEN r.protein ELSE $protein END,
            r.fat = CASE WHEN $fat IS NULL THEN r.fat ELSE $fat END,
            r.carbs = CASE WHEN $carbs IS NULL THEN r.carbs ELSE $carbs END,
            r.fiber = CASE WHEN $fiber IS NULL THEN r.fiber ELSE $fiber END,
            r.steps = CASE WHEN $steps = '' THEN r.steps ELSE $steps END,
            r.ingredients_raw = CASE WHEN $ingredients_raw = '' THEN r.ingredients_raw ELSE $ingredients_raw END,
            r.nutrients_raw = CASE WHEN $nutrients_raw = '' THEN r.nutrients_raw ELSE $nutrients_raw END,
            r.health_advice = CASE WHEN $health_advice = '' THEN r.health_advice ELSE $health_advice END,
            r.is_unhealthy_for_diet = CASE WHEN $is_unhealthy_for_diet IS NULL THEN r.is_unhealthy_for_diet ELSE $is_unhealthy_for_diet END,
            r.raw_json = CASE WHEN $raw_json = '' THEN r.raw_json ELSE $raw_json END,
            r.source = 'admin_upload'
        """

        contains_query = """
        MATCH (r:Recipe {name: $recipe_name})
        MERGE (i:Ingredient {name: $ingredient_name})
        ON CREATE SET i.source = 'recipe_relation', i.missing_info = true, i.created_at = $now
        MERGE (r)-[rel:CONTAINS]->(i)
        SET rel.weight_g = $weight_g,
            rel.raw_text = $raw_text,
            rel.is_linked = $is_linked,
            rel.updated_at = $now
        """

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        contains_count = 0
        with graph_db.driver.session() as session:
            for name, item in dedup.items():
                nutrients = item.get("nutrients", {}) if isinstance(item.get("nutrients"), dict) else {}
                calories = _safe_float((nutrients.get("热量") or {}).get("value") if isinstance(nutrients.get("热量"), dict) else None)
                protein = _safe_float((nutrients.get("蛋白质") or {}).get("value") if isinstance(nutrients.get("蛋白质"), dict) else None)
                fat = _safe_float((nutrients.get("脂肪") or {}).get("value") if isinstance(nutrients.get("脂肪"), dict) else None)
                carbs = _safe_float((nutrients.get("碳水化合物") or {}).get("value") if isinstance(nutrients.get("碳水化合物"), dict) else None)
                fiber = _safe_float((nutrients.get("纤维素") or {}).get("value") if isinstance(nutrients.get("纤维素"), dict) else None)

                basic_info = item.get("basic_info", {}) if isinstance(item.get("basic_info"), dict) else {}
                health_advice = str(item.get("health_advice") or basic_info.get("cooking_type_detail") or "").strip()
                unhealthy = item.get("is_unhealthy_for_diet")
                if unhealthy is None and health_advice:
                    unhealthy = ("不宜食用" in health_advice) or ("少吃" in health_advice)

                steps = item.get("steps", [])
                if isinstance(steps, list):
                    steps_text = json.dumps(steps, ensure_ascii=False)
                else:
                    steps_text = str(steps or "")

                ingredients = item.get("ingredients", []) if isinstance(item.get("ingredients"), list) else []
                session.run(upsert_query, {
                    "name": name,
                    "category": str(item.get("category") or "").strip(),
                    "image": str(item.get("image") or "").strip(),
                    "calories": calories,
                    "protein": protein,
                    "fat": fat,
                    "carbs": carbs,
                    "fiber": fiber,
                    "steps": steps_text,
                    "ingredients_raw": json.dumps(ingredients, ensure_ascii=False),
                    "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
                    "health_advice": health_advice,
                    "is_unhealthy_for_diet": unhealthy,
                    "raw_json": json.dumps(item, ensure_ascii=False),
                    "now": now,
                })

                for ing in ingredients:
                    if not isinstance(ing, dict):
                        continue
                    ing_name = str(ing.get("ingredient_name") or ing.get("name") or "").strip()
                    if not ing_name:
                        continue
                    session.run(contains_query, {
                        "recipe_name": name,
                        "ingredient_name": ing_name,
                        "weight_g": _safe_float(ing.get("weight_g")) or 0.0,
                        "raw_text": str(ing.get("raw_text") or "").strip(),
                        "is_linked": bool(ing.get("is_linked", False)),
                        "now": now,
                    })
                    contains_count += 1

        return {
            "input_records": len(data),
            "deduped_recipes": len(dedup),
            "upserted_recipes": len(dedup),
            "upserted_contains_relations": contains_count,
        }

    def _import_relations(self, data, task_id=None):
        if not isinstance(data, dict):
            raise ValueError("关系 JSON 必须是对象")

        existing_names = graph_db.query("MATCH (i:Ingredient) RETURN i.name AS name")
        valid_names = {str(x.get("name", "")).strip() for x in existing_names if x.get("name")}

        rel_queries = {
            "互斥": """
                MERGE (a:Ingredient {name: $src})
                ON CREATE SET a.source = 'relation_upload', a.missing_info = true, a.created_at = $now, a.created_by_import_task = $task_id
                MERGE (b:Ingredient {name: $tgt})
                ON CREATE SET b.source = 'relation_upload', b.missing_info = true, b.created_at = $now, b.created_by_import_task = $task_id
                MERGE (a)-[r:CLASH_WITH]->(b)
                SET r.desc = $desc,
                    r.source_category = $category,
                    r.source_sub_category = $sub_category,
                    r.updated_at = $now,
                    r.import_task_id = $task_id
            """,
            "互补": """
                MERGE (a:Ingredient {name: $src})
                ON CREATE SET a.source = 'relation_upload', a.missing_info = true, a.created_at = $now, a.created_by_import_task = $task_id
                MERGE (b:Ingredient {name: $tgt})
                ON CREATE SET b.source = 'relation_upload', b.missing_info = true, b.created_at = $now, b.created_by_import_task = $task_id
                MERGE (a)-[r:COMPLEMENT_WITH]->(b)
                SET r.desc = $desc,
                    r.source_category = $category,
                    r.source_sub_category = $sub_category,
                    r.updated_at = $now,
                    r.import_task_id = $task_id
            """,
            "重叠": """
                MERGE (a:Ingredient {name: $src})
                ON CREATE SET a.source = 'relation_upload', a.missing_info = true, a.created_at = $now, a.created_by_import_task = $task_id
                MERGE (b:Ingredient {name: $tgt})
                ON CREATE SET b.source = 'relation_upload', b.missing_info = true, b.created_at = $now, b.created_by_import_task = $task_id
                MERGE (a)-[r:SIMILAR_TO]->(b)
                SET r.desc = $desc,
                    r.source_category = $category,
                    r.source_sub_category = $sub_category,
                    r.updated_at = $now,
                    r.import_task_id = $task_id
            """,
        }

        relation_seen = set()
        created_name_count = 0
        relation_count = 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with graph_db.driver.session() as session:
            for category, sub_dict in data.items():
                if not isinstance(sub_dict, dict):
                    continue
                for sub_category, item_list in sub_dict.items():
                    if not isinstance(item_list, list):
                        continue
                    for item in item_list:
                        if not isinstance(item, dict):
                            continue
                        src_raw = item.get("食物名称")
                        src_final, src_is_new = _find_or_create_relation_name(src_raw, valid_names)
                        if not src_final:
                            continue
                        if src_is_new and src_final not in valid_names:
                            valid_names.add(src_final)
                            created_name_count += 1

                        rel_obj = item.get("食物关系", {}) if isinstance(item.get("食物关系"), dict) else {}
                        for rel_type, targets in rel_obj.items():
                            if rel_type not in rel_queries or not isinstance(targets, list):
                                continue
                            for target in targets:
                                if not isinstance(target, dict):
                                    continue
                                tgt_raw = target.get("食物名称")
                                desc = str(target.get("描述") or "").strip()
                                tgt_final, tgt_is_new = _find_or_create_relation_name(tgt_raw, valid_names)
                                if not tgt_final:
                                    continue
                                if tgt_is_new and tgt_final not in valid_names:
                                    valid_names.add(tgt_final)
                                    created_name_count += 1

                                dedup_key = (src_final, rel_type, tgt_final)
                                if dedup_key in relation_seen:
                                    continue
                                relation_seen.add(dedup_key)

                                session.run(rel_queries[rel_type], {
                                    "src": src_final,
                                    "tgt": tgt_final,
                                    "desc": desc,
                                    "category": str(category),
                                    "sub_category": str(sub_category),
                                    "now": now,
                                    "task_id": task_id or "",
                                })
                                relation_count += 1

        return {
            "input_groups": len(data.keys()),
            "upserted_relations": relation_count,
            "new_ingredient_nodes_created": created_name_count,
            "deduped_relations": len(relation_seen),
        }


class AdminImportPreviewView(APIView):
    """导入前预览与差异对比（dry-run）"""
    def post(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        try:
            parsed = _read_admin_import_payload(request)
        except Exception as e:
            return Response({"error": f"JSON 解析失败: {e}"}, status=400)

        import_type = parsed["import_type"]
        payload = parsed["payload"]

        if import_type == "ingredient":
            preview = self._preview_ingredients(payload)
        elif import_type == "recipe":
            preview = self._preview_recipes(payload)
        else:
            preview = self._preview_relations(payload)

        return Response({"status": "success", "import_type": import_type, "preview": preview})

    def _preview_ingredients(self, data):
        if not isinstance(data, list):
            raise ValueError("食材 JSON 必须是数组")
        dedup = {}
        for item in data:
            if isinstance(item, dict) and str(item.get("name", "")).strip():
                dedup[str(item.get("name")).strip()] = item

        names = list(dedup.keys())
        existing = {}
        if names:
            rows = graph_db.query(
                "MATCH (i:Ingredient) WHERE i.name IN $names RETURN i.name AS name, i.category AS category, i.cal_per_100g AS cal_per_100g, i.original_name AS original_name, i.nutrients_raw AS nutrients_raw",
                {"names": names},
            )
            existing = {r["name"]: r for r in rows}

        create_count, update_count, skip_count = 0, 0, 0
        diffs = []
        for name, item in dedup.items():
            nutrients = item.get("nutrients", {}) if isinstance(item.get("nutrients"), dict) else {}
            incoming = {
                "category": str(item.get("category") or "").strip(),
                "cal_per_100g": _safe_float(item.get("cal_per_100g")),
                "original_name": str(item.get("original_name") or "").strip(),
                "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
            }
            ex = existing.get(name)
            if not ex:
                create_count += 1
                if len(diffs) < 20:
                    diffs.append({"name": name, "action": "create", "changed_fields": list(incoming.keys())})
                continue

            changed_fields = []
            for k in ("category", "original_name", "nutrients_raw"):
                if str(ex.get(k) or "") != str(incoming.get(k) or ""):
                    changed_fields.append(k)
            ex_cal = _safe_float(ex.get("cal_per_100g"))
            in_cal = incoming.get("cal_per_100g")
            if (ex_cal is None) != (in_cal is None) or (ex_cal is not None and in_cal is not None and abs(ex_cal - in_cal) > 1e-9):
                changed_fields.append("cal_per_100g")

            if changed_fields:
                update_count += 1
                if len(diffs) < 20:
                    diffs.append({"name": name, "action": "update", "changed_fields": changed_fields})
            else:
                skip_count += 1

        return {
            "input_records": len(data),
            "deduped_records": len(dedup),
            "will_create": create_count,
            "will_update": update_count,
            "will_skip": skip_count,
            "diff_samples": diffs,
        }

    def _preview_recipes(self, data):
        if not isinstance(data, list):
            raise ValueError("菜谱 JSON 必须是数组")
        dedup = {}
        for item in data:
            if isinstance(item, dict) and str(item.get("name", "")).strip():
                dedup[str(item.get("name")).strip()] = item

        names = list(dedup.keys())
        existing = {}
        if names:
            rows = graph_db.query(
                "MATCH (r:Recipe) WHERE r.name IN $names RETURN r.name AS name, r.category AS category, r.calories AS calories, r.nutrients_raw AS nutrients_raw, r.ingredients_raw AS ingredients_raw, r.steps AS steps",
                {"names": names},
            )
            existing = {r["name"]: r for r in rows}

        create_count, update_count, skip_count = 0, 0, 0
        diffs = []
        for name, item in dedup.items():
            nutrients = item.get("nutrients", {}) if isinstance(item.get("nutrients"), dict) else {}
            calories = _safe_float((nutrients.get("热量") or {}).get("value") if isinstance(nutrients.get("热量"), dict) else None)
            steps = item.get("steps", [])
            incoming = {
                "category": str(item.get("category") or "").strip(),
                "calories": calories,
                "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
                "ingredients_raw": json.dumps(item.get("ingredients", []) if isinstance(item.get("ingredients"), list) else [], ensure_ascii=False),
                "steps": json.dumps(steps, ensure_ascii=False) if isinstance(steps, list) else str(steps or ""),
            }
            ex = existing.get(name)
            if not ex:
                create_count += 1
                if len(diffs) < 20:
                    diffs.append({"name": name, "action": "create", "changed_fields": list(incoming.keys())})
                continue

            changed_fields = []
            for k in ("category", "nutrients_raw", "ingredients_raw", "steps"):
                if str(ex.get(k) or "") != str(incoming.get(k) or ""):
                    changed_fields.append(k)
            ex_cal = _safe_float(ex.get("calories"))
            in_cal = incoming.get("calories")
            if (ex_cal is None) != (in_cal is None) or (ex_cal is not None and in_cal is not None and abs(ex_cal - in_cal) > 1e-9):
                changed_fields.append("calories")

            if changed_fields:
                update_count += 1
                if len(diffs) < 20:
                    diffs.append({"name": name, "action": "update", "changed_fields": changed_fields})
            else:
                skip_count += 1

        return {
            "input_records": len(data),
            "deduped_records": len(dedup),
            "will_create": create_count,
            "will_update": update_count,
            "will_skip": skip_count,
            "diff_samples": diffs,
        }

    def _preview_relations(self, data):
        if not isinstance(data, dict):
            raise ValueError("关系 JSON 必须是对象")

        existing_rows = graph_db.query(
            "MATCH (a:Ingredient)-[r:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO]->(b:Ingredient) RETURN a.name AS src, type(r) AS rel, b.name AS tgt, coalesce(r.desc, '') AS desc"
        )
        existing_map = {(r.get("src"), r.get("rel"), r.get("tgt")): str(r.get("desc") or "") for r in existing_rows}
        existing_names = graph_db.query("MATCH (i:Ingredient) RETURN i.name AS name")
        valid_names = {str(x.get("name", "")).strip() for x in existing_names if x.get("name")}
        type_map = {"互斥": "CLASH_WITH", "互补": "COMPLEMENT_WITH", "重叠": "SIMILAR_TO"}

        create_count, update_count, skip_count = 0, 0, 0
        diffs = []
        seen = set()

        for category, sub_dict in data.items():
            if not isinstance(sub_dict, dict):
                continue
            for _, item_list in sub_dict.items():
                if not isinstance(item_list, list):
                    continue
                for item in item_list:
                    if not isinstance(item, dict):
                        continue
                    src_final, _ = _find_or_create_relation_name(item.get("食物名称"), valid_names)
                    if not src_final:
                        continue
                    rel_obj = item.get("食物关系", {}) if isinstance(item.get("食物关系"), dict) else {}
                    for rel_type, targets in rel_obj.items():
                        if rel_type not in type_map or not isinstance(targets, list):
                            continue
                        rel_label = type_map[rel_type]
                        for target in targets:
                            if not isinstance(target, dict):
                                continue
                            tgt_final, _ = _find_or_create_relation_name(target.get("食物名称"), valid_names)
                            if not tgt_final:
                                continue
                            key = (src_final, rel_label, tgt_final)
                            if key in seen:
                                continue
                            seen.add(key)
                            desc = str(target.get("描述") or "").strip()
                            if key not in existing_map:
                                create_count += 1
                                if len(diffs) < 20:
                                    diffs.append({"name": f"{src_final}->{tgt_final}", "action": "create", "changed_fields": [rel_label]})
                            elif existing_map[key] != desc:
                                update_count += 1
                                if len(diffs) < 20:
                                    diffs.append({"name": f"{src_final}->{tgt_final}", "action": "update", "changed_fields": ["desc"]})
                            else:
                                skip_count += 1

        return {
            "input_groups": len(data.keys()),
            "deduped_relations": len(seen),
            "will_create": create_count,
            "will_update": update_count,
            "will_skip": skip_count,
            "diff_samples": diffs,
        }


class AdminImportTaskListView(APIView):
    """导入任务日志列表"""
    def get(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        limit = int(request.query_params.get("limit", 20) or 20)
        if limit < 1:
            limit = 20
        if limit > 100:
            limit = 100

        rows = graph_db.query(
            """
            MATCH (t:ImportTask)
            RETURN t.id AS id,
                   t.import_type AS import_type,
                   t.source AS source,
                   coalesce(t.file_path, '') AS file_path,
                   coalesce(t.file_name, '') AS file_name,
                   t.status AS status,
                   t.started_at AS started_at,
                   coalesce(t.ended_at, '') AS ended_at,
                   coalesce(t.duration_ms, 0) AS duration_ms,
                   coalesce(t.stats_json, '{}') AS stats_json,
                   coalesce(t.error, '') AS error
            ORDER BY t.started_at DESC
            LIMIT $limit
            """,
            {"limit": limit},
        )
        for r in rows:
            try:
                r["stats"] = json.loads(r.get("stats_json") or "{}")
            except Exception:
                r["stats"] = {}
            r.pop("stats_json", None)
        return Response({"tasks": rows})


class AdminImportRollbackView(APIView):
    """一键回滚最近一次关系导入（第一版）"""
    def post(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        task_id = str(request.data.get("task_id", "")).strip()
        if task_id:
            task_rows = graph_db.query(
                "MATCH (t:ImportTask {id: $task_id}) RETURN t.id AS id, t.import_type AS import_type, t.status AS status",
                {"task_id": task_id},
            )
        else:
            task_rows = graph_db.query(
                """
                MATCH (t:ImportTask {import_type: 'relation', status: 'success'})
                RETURN t.id AS id, t.import_type AS import_type, t.status AS status
                ORDER BY t.started_at DESC
                LIMIT 1
                """
            )

        if not task_rows:
            return Response({"error": "未找到可回滚的关系导入任务"}, status=404)

        row = task_rows[0]
        if row.get("import_type") != "relation" or row.get("status") != "success":
            return Response({"error": "仅支持回滚成功的关系导入任务"}, status=400)

        target_task_id = row.get("id")

        deleted_rel = graph_db.query(
            """
            MATCH ()-[r:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO {import_task_id: $task_id}]->()
            WITH count(r) AS c
            MATCH ()-[r2:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO {import_task_id: $task_id}]->()
            DELETE r2
            RETURN c AS deleted
            """,
            {"task_id": target_task_id},
        )
        deleted_rel_count = int((deleted_rel[0] if deleted_rel else {}).get("deleted", 0) or 0)

        deleted_nodes = graph_db.query(
            """
            MATCH (i:Ingredient {created_by_import_task: $task_id})
            WHERE NOT (i)-[:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO]-(:Ingredient)
              AND NOT (i)<-[:CONTAINS]-(:Recipe)
            WITH collect(i) AS nodes, count(i) AS c
            FOREACH (n IN nodes | DELETE n)
            RETURN c AS deleted
            """,
            {"task_id": target_task_id},
        )
        deleted_node_count = int((deleted_nodes[0] if deleted_nodes else {}).get("deleted", 0) or 0)

        graph_db.query(
            "MATCH (t:ImportTask {id: $task_id}) SET t.rollback_at = $ts, t.rollback_status = 'done'",
            {"task_id": target_task_id, "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        )

        return Response({
            "status": "success",
            "rollback_task_id": target_task_id,
            "deleted_relations": deleted_rel_count,
            "deleted_new_nodes": deleted_node_count,
        })


class AdminDataQualityView(APIView):
    """数据质量巡检"""
    def get(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        checks = {
            "ingredients_missing_original_name": "MATCH (i:Ingredient) WHERE i.original_name IS NULL OR trim(toString(i.original_name)) = '' RETURN count(i) AS v",
            "ingredients_missing_nutrients_raw": "MATCH (i:Ingredient) WHERE i.nutrients_raw IS NULL OR trim(toString(i.nutrients_raw)) = '' RETURN count(i) AS v",
            "recipes_missing_nutrients_raw": "MATCH (r:Recipe) WHERE r.nutrients_raw IS NULL OR trim(toString(r.nutrients_raw)) = '' RETURN count(r) AS v",
            "ingredients_missing_info_flag": "MATCH (i:Ingredient) WHERE coalesce(i.missing_info, false) = true RETURN count(i) AS v",
            "duplicate_ingredient_names": "MATCH (i:Ingredient) WITH i.name AS name, count(i) AS c WHERE c > 1 RETURN count(name) AS v",
            "duplicate_recipe_names": "MATCH (r:Recipe) WITH r.name AS name, count(r) AS c WHERE c > 1 RETURN count(name) AS v",
            "orphan_ingredients": "MATCH (i:Ingredient) WHERE NOT (i)<-[:CONTAINS]-(:Recipe) AND NOT (i)-[:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO]-(:Ingredient) RETURN count(i) AS v",
            "abnormal_self_relations": "MATCH (i:Ingredient)-[r:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO]->(i) RETURN count(r) AS v",
            "abnormal_empty_relation_desc": "MATCH (:Ingredient)-[r:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO]->(:Ingredient) WHERE r.desc IS NULL OR trim(toString(r.desc)) = '' RETURN count(r) AS v",
        }

        result = {}
        for k, q in checks.items():
            row = graph_db.query(q)
            result[k] = int((row[0] if row else {}).get("v", 0) or 0)

        suggestions = []
        if result["ingredients_missing_info_flag"] > 0:
            suggestions.append("可执行一键修复：补全 missing_info=true 的食材默认字段")
        if result["abnormal_empty_relation_desc"] > 0:
            suggestions.append("可执行一键修复：为空关系补默认描述")
        if not suggestions:
            suggestions.append("当前未发现高优先级质量问题")

        return Response({"status": "success", "checks": result, "suggestions": suggestions})


class AdminDataQualityFixView(APIView):
    """数据质量一键修复"""
    def post(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        action = str(request.data.get("action", "fix_missing_info")).strip()
        if action == "fix_missing_info":
            rows = graph_db.query(
                """
                MATCH (i:Ingredient)
                WHERE coalesce(i.missing_info, false) = true
                WITH collect(i) AS nodes, count(i) AS c
                FOREACH (n IN nodes |
                    SET n.original_name = coalesce(n.original_name, n.name),
                        n.category = coalesce(n.category, 'Other'),
                        n.nutrient_count = coalesce(n.nutrient_count, 0),
                        n.unit_info = coalesce(n.unit_info, '[]'),
                        n.nutrients_raw = coalesce(n.nutrients_raw, '{}'),
                        n.missing_info = false,
                        n.updated_at = $ts
                )
                RETURN c AS fixed
                """,
                {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            )
            fixed = int((rows[0] if rows else {}).get("fixed", 0) or 0)
            return Response({"status": "success", "action": action, "fixed_count": fixed})

        if action == "fill_empty_relation_desc":
            rows = graph_db.query(
                """
                MATCH (:Ingredient)-[r:CLASH_WITH|COMPLEMENT_WITH|SIMILAR_TO]->(:Ingredient)
                WHERE r.desc IS NULL OR trim(toString(r.desc)) = ''
                WITH collect(r) AS rels, count(r) AS c
                FOREACH (x IN rels | SET x.desc = '系统自动补全：未提供说明')
                RETURN c AS fixed
                """
            )
            fixed = int((rows[0] if rows else {}).get("fixed", 0) or 0)
            return Response({"status": "success", "action": action, "fixed_count": fixed})

        return Response({"error": "不支持的修复动作"}, status=400)


class AdminUserAuditView(APIView):
    """用户行为审计（支持按日期过滤）"""
    def get(self, request):
        if not _validate_admin_token(request):
            return Response({"error": "管理员认证失败，请重新登录"}, status=401)

        end_date = str(request.query_params.get("end_date") or datetime.now().strftime("%Y-%m-%d"))
        start_date = str(request.query_params.get("start_date") or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))

        active_log_rows = graph_db.query(
            "MATCH (u:User)-[:HAS_LOG]->(l:DietLog) WHERE l.date >= $start AND l.date <= $end RETURN count(DISTINCT u) AS v",
            {"start": start_date, "end": end_date},
        )
        active_chat_rows = graph_db.query(
            "MATCH (u:User)-[:HAS_CHAT]->(s:ChatSession) WHERE substring(coalesce(s.created_at, ''), 0, 10) >= $start AND substring(coalesce(s.created_at, ''), 0, 10) <= $end RETURN count(DISTINCT u) AS v",
            {"start": start_date, "end": end_date},
        )

        usage_rows = graph_db.query(
            """
            MATCH (u:User)
            OPTIONAL MATCH (u)-[:HAS_LOG]->(l:DietLog)
              WHERE l.date >= $start AND l.date <= $end
            OPTIONAL MATCH (u)-[:HAS_CHAT]->(s:ChatSession)
              WHERE substring(coalesce(s.created_at, ''), 0, 10) >= $start AND substring(coalesce(s.created_at, ''), 0, 10) <= $end
            OPTIONAL MATCH (u)-[:COLLECTED]->(c:Collection)
            RETURN u.id AS user_id,
                   count(DISTINCT l) AS log_count,
                   count(DISTINCT s) AS chat_count,
                   count(DISTINCT c) AS collect_count
            ORDER BY (count(DISTINCT l) + count(DISTINCT s)) DESC
            LIMIT 20
            """,
            {"start": start_date, "end": end_date},
        )

        failed_rows = graph_db.query(
            "MATCH (t:ImportTask) WHERE t.status = 'failed' AND substring(coalesce(t.started_at, ''), 0, 10) >= $start AND substring(coalesce(t.started_at, ''), 0, 10) <= $end RETURN count(t) AS v",
            {"start": start_date, "end": end_date},
        )

        feature_usage = {
            "diet_log_entries": sum(int(r.get("log_count", 0) or 0) for r in usage_rows),
            "chat_sessions": sum(int(r.get("chat_count", 0) or 0) for r in usage_rows),
            "collections": sum(int(r.get("collect_count", 0) or 0) for r in usage_rows),
        }

        return Response({
            "status": "success",
            "period": {"start_date": start_date, "end_date": end_date},
            "active_users": {
                "by_diet_log": int((active_log_rows[0] if active_log_rows else {}).get("v", 0) or 0),
                "by_chat": int((active_chat_rows[0] if active_chat_rows else {}).get("v", 0) or 0),
            },
            "feature_usage": feature_usage,
            "failed_requests_recorded": int((failed_rows[0] if failed_rows else {}).get("v", 0) or 0),
            "top_users": usage_rows,
        })

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

        try:
            target_weight = float(request.data.get("targetWeight") or 0)
        except ValueError:
            target_weight = 0.0

        try:
            fat_loss_weeks = int(request.data.get("fatLossWeeks") or 0)
        except ValueError:
            fat_loss_weeks = 0

        if fat_loss_weeks < 0:
            fat_loss_weeks = 0

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
                        u.dislikes = $dislikes,
                        u.target_weight = $target_weight,
                        u.fat_loss_weeks = $fat_loss_weeks,
                        u.initial_weight = CASE
                            WHEN u.initial_weight IS NULL OR toFloat(u.initial_weight) <= 0 THEN CASE WHEN $weight > 0 THEN $weight ELSE u.initial_weight END
                            ELSE u.initial_weight
                        END,
                        u.fat_loss_start_date = CASE
                            WHEN $fat_loss_weeks > 0 AND (u.fat_loss_start_date IS NULL OR trim(toString(u.fat_loss_start_date)) = '') THEN $today
                            ELSE u.fat_loss_start_date
                        END
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
                                "dislikes": dislikes,
                                "target_weight": target_weight,
                                "fat_loss_weeks": fat_loss_weeks,
                                "today": datetime.now().strftime("%Y-%m-%d")
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
             coalesce(u.initial_weight, 0) AS initialWeight,
             coalesce(u.target_weight, 0) AS targetWeight,
             coalesce(u.fat_loss_weeks, 0) AS fatLossWeeks,
             coalesce(u.fat_loss_start_date, "") AS fatLossStartDate,
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
            recipe_hidden_keys = {
                "image",
                "ingredients_raw",
                "raw_json",
                "steps",
                "steps_raw",
            }
            for k, v in props.items():
                if v is None:
                    continue
                if isinstance(v, str) and len(v.strip()) == 0:
                    continue
                if k in {"embedding", "vector", "feature_vector"}:
                    continue
                if k in recipe_hidden_keys:
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


class RecipeFullDetailView(APIView):
    """菜谱详情查询：完整属性 + 营养细节 + 配料明细 + 步骤"""
    def get(self, request):
        name = request.query_params.get("name", "").strip()
        if not name:
            return Response({"error": "请输入菜谱名"}, status=400)

        recipe_cypher = """
        MATCH (r:Recipe)
        WHERE toLower(r.name) = toLower($name)
           OR toLower(r.name) CONTAINS toLower($name)
           OR toLower($name) CONTAINS toLower(r.name)
        RETURN r.name AS name, properties(r) AS props
        ORDER BY CASE WHEN toLower(r.name) = toLower($name) THEN 0 ELSE 1 END, size(r.name) ASC
        LIMIT 1
        """

        contains_cypher = """
        MATCH (r:Recipe {name: $name})-[rel:CONTAINS]->(i:Ingredient)
        RETURN i.name AS ingredient_name,
               rel.weight_g AS weight_g,
               rel.raw_text AS raw_text,
               rel.is_linked AS is_linked
        ORDER BY coalesce(rel.weight_g, 0) DESC
        LIMIT 400
        """

        try:
            recipe_result = graph_db.query(recipe_cypher, {"name": name})
            if not recipe_result:
                return Response({"error": "未找到该菜谱"}, status=404)

            item = recipe_result[0]
            recipe_name = item.get("name")
            props = item.get("props") or {}

            nutrients_detail = {}
            nutrients_raw = props.get("nutrients_raw")
            if nutrients_raw:
                try:
                    parsed = json.loads(nutrients_raw)
                    if isinstance(parsed, dict):
                        nutrients_detail = parsed
                except Exception:
                    nutrients_detail = {"raw_text": str(nutrients_raw)}

            ingredients_detail = []
            ingredients_raw = props.get("ingredients_raw")
            if ingredients_raw:
                try:
                    parsed = json.loads(ingredients_raw)
                    if isinstance(parsed, list):
                        ingredients_detail = parsed
                except Exception:
                    ingredients_detail = [{"raw_text": str(ingredients_raw)}]

            # If raw field is absent or empty, fallback to graph relations.
            contains_rows = graph_db.query(contains_cypher, {"name": recipe_name})
            if (not ingredients_detail) and contains_rows:
                ingredients_detail = [
                    {
                        "ingredient_name": r.get("ingredient_name"),
                        "weight_g": r.get("weight_g"),
                        "raw_text": r.get("raw_text"),
                        "is_linked": r.get("is_linked"),
                    }
                    for r in contains_rows
                ]

            steps_detail = []
            steps_raw = props.get("steps")
            if steps_raw:
                if isinstance(steps_raw, list):
                    steps_detail = [str(s).strip() for s in steps_raw if str(s).strip()]
                else:
                    text = str(steps_raw).strip()
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            steps_detail = [str(s).strip() for s in parsed if str(s).strip()]
                        else:
                            steps_detail = [line.strip() for line in text.split("\n") if line.strip()]
                    except Exception:
                        steps_detail = [line.strip() for line in text.split("\n") if line.strip()]

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
                    "name": recipe_name,
                    "query_type": "recipe",
                    "all_properties": cleaned_props,
                    "nutrients_detail": _to_json_safe(nutrients_detail),
                    "ingredients_detail": _to_json_safe(ingredients_detail),
                    "steps_detail": _to_json_safe(steps_detail),
                    "contains_relations": _to_json_safe(contains_rows),
                    "relations": {
                        "complements": [],
                        "conflicts": [],
                        "overlaps": [],
                        "all": [],
                    },
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


class ExerciseLogView(APIView):
    """运动消耗记录：按日期记录与统计，支持 MET 自动估算"""
    def post(self, request):
        user_id = request.data.get("user_id")
        date_str = request.data.get("date", datetime.now().strftime("%Y-%m-%d"))
        exercise_type = str(request.data.get("exercise_type", "运动")).strip() or "运动"
        note = str(request.data.get("note", "")).strip()

        try:
            duration_minutes = float(request.data.get("duration_minutes") or 0)
        except ValueError:
            duration_minutes = 0.0

        try:
            met = float(request.data.get("met") or 0)
        except ValueError:
            met = 0.0

        try:
            calories = float(request.data.get("calories") or 0)
        except ValueError:
            calories = 0.0

        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        if calories <= 0 and met > 0 and duration_minutes > 0:
            weight_rows = graph_db.query(
                "MATCH (u:User {id: $user_id}) RETURN coalesce(u.weight, 60) AS weight LIMIT 1",
                {"user_id": user_id}
            )
            weight = float((weight_rows[0] if weight_rows else {}).get("weight", 60) or 60)
            calories = met * weight * (duration_minutes / 60.0)

        calories = max(0.0, calories)
        duration_minutes = max(0.0, duration_minutes)
        met = max(0.0, met)

        log_id = str(uuid.uuid4())[:10]
        cypher = """
        MATCH (u:User {id: $user_id})
        CREATE (log:ExerciseLog {
            id: $log_id,
            user_id: $user_id,
            date: $date,
            exercise_type: $exercise_type,
            duration_minutes: $duration_minutes,
            met: $met,
            calories: $calories,
            note: $note,
            created_at: $created_at
        })
        MERGE (u)-[:HAS_EXERCISE_LOG]->(log)
        RETURN log.id AS id
        """
        try:
            graph_db.query(cypher, {
                "log_id": log_id,
                "user_id": user_id,
                "date": date_str,
                "exercise_type": exercise_type,
                "duration_minutes": duration_minutes,
                "met": met,
                "calories": calories,
                "note": note,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return Response({"status": "success", "id": log_id, "calories": round(calories, 2)})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def get(self, request):
        user_id = request.query_params.get("user_id")
        date_str = request.query_params.get("date")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        try:
            if start_date and end_date:
                cypher = """
                MATCH (u:User {id: $user_id})-[:HAS_EXERCISE_LOG]->(log:ExerciseLog)
                WHERE log.date >= $start_date AND log.date <= $end_date
                RETURN log.id AS id,
                       log.date AS date,
                       log.exercise_type AS exercise_type,
                       coalesce(log.duration_minutes, 0) AS duration_minutes,
                       coalesce(log.met, 0) AS met,
                       coalesce(log.calories, 0) AS calories,
                       coalesce(log.note, '') AS note,
                       coalesce(log.created_at, '') AS created_at
                ORDER BY log.date DESC, log.created_at DESC
                """
                params = {"user_id": user_id, "start_date": start_date, "end_date": end_date}
            else:
                if not date_str:
                    date_str = datetime.now().strftime("%Y-%m-%d")
                cypher = """
                MATCH (u:User {id: $user_id})-[:HAS_EXERCISE_LOG]->(log:ExerciseLog {date: $date})
                RETURN log.id AS id,
                       log.date AS date,
                       log.exercise_type AS exercise_type,
                       coalesce(log.duration_minutes, 0) AS duration_minutes,
                       coalesce(log.met, 0) AS met,
                       coalesce(log.calories, 0) AS calories,
                       coalesce(log.note, '') AS note,
                       coalesce(log.created_at, '') AS created_at
                ORDER BY log.created_at DESC
                """
                params = {"user_id": user_id, "date": date_str}

            rows = graph_db.query(cypher, params)
            total = sum(float(r.get("calories") or 0) for r in rows)
            return Response({"logs": rows, "total_calories": round(total, 2)})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def delete(self, request):
        user_id = request.query_params.get("user_id")
        log_id = request.query_params.get("log_id")
        if not user_id or not log_id:
            return Response({"error": "缺少参数"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})-[:HAS_EXERCISE_LOG]->(log:ExerciseLog {id: $log_id})
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
             n.protein AS protein, n.fat AS fat, n.carbs AS carbs,
             coalesce(n.category, '未分类') AS category
        LIMIT 3
        """

        lunch_cypher = f"""
        MATCH (n:Recipe)
        WHERE n.calories >= 300 AND n.calories <= 700
        {avoid_filter}
        WITH n, rand() AS r
        ORDER BY r
        RETURN n.name AS name, n.calories AS calories,
             n.protein AS protein, n.fat AS fat, n.carbs AS carbs,
             coalesce(n.category, '未分类') AS category
        LIMIT 4
        """

        dinner_cypher = f"""
        MATCH (n:Recipe)
        WHERE n.calories >= 200 AND n.calories <= 500
        {avoid_filter}
        WITH n, rand() AS r
        ORDER BY r
        RETURN n.name AS name, n.calories AS calories,
             n.protein AS protein, n.fat AS fat, n.carbs AS carbs,
             coalesce(n.category, '未分类') AS category
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
         WITH s, m ORDER BY coalesce(m.idx, 0) ASC, m.timestamp ASC
         WITH s, [x IN collect({role: m.role, content: m.content, timestamp: m.timestamp, idx: m.idx}) WHERE x.role IS NOT NULL] AS msgs
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