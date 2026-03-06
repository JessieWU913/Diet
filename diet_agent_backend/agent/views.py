# agent/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from langchain_core.messages import HumanMessage
import uuid

from .graph import app
from .neo4j_service import graph_db


# ==========================================
# 1. 用户注册与登录接口)
# ==========================================
class UserAuthView(APIView):
    def post(self, request):
        action = request.data.get("action")
        username = request.data.get("username")
        password = request.data.get("password")

        if action == "register":
            # 检查是否已存在
            check_cypher = "MATCH (u:User {username: $username}) RETURN u"
            if graph_db.query(check_cypher, {"username": username}):
                return Response({"error": "用户名已存在"}, status=400)

            user_id = str(uuid.uuid4())
            create_cypher = """
            CREATE (u:User {
                id: $user_id, username: $username, password: $password,
                name: $username, allergies: [], dislikes: []
            }) RETURN u.id AS user_id
            """
            result = graph_db.query(create_cypher, {"user_id": user_id, "username": username, "password": password})
            return Response({"status": "success", "user_id": result[0]["user_id"]})

        elif action == "login":
            login_cypher = "MATCH (u:User {username: $username, password: $password}) RETURN u.id AS user_id, u.name AS name"
            result = graph_db.query(login_cypher, {"username": username, "password": password})
            if result:
                return Response({"status": "success", "user_id": result[0]["user_id"], "name": result[0]["name"]})
            return Response({"error": "账号或密码错误"}, status=401)


# ==========================================
# 2. 用户资料填写接口
# ==========================================
class UserProfileView(APIView):
    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})
        RETURN u.gender AS gender, u.height AS height, u.weight AS weight, 
               u.allergies AS allergies, u.dislikes AS dislikes
        """
        try:
            result = graph_db.query(cypher, {"user_id": user_id})
            if result:
                return Response({"status": "success", "data": result[0]})
            return Response({"status": "success", "data": {}})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def post(self, request):
        data = request.data
        user_id = data.get("user_id")

        # 忌口数组保存到 Neo4j 的 User 节点中
        cypher = """
        MATCH (u:User {id: $user_id})
        SET u.height = toFloat($height),
            u.weight = toFloat($weight),
            u.allergies = $allergies,
            u.dislikes = $dislikes,
            u.gender = $gender
        RETURN u
        """
        try:
            graph_db.query(cypher, {
                "user_id": user_id,
                "height": data.get("height", 0),
                "weight": data.get("weight", 0),
                "allergies": data.get("allergies", []),
                "dislikes": data.get("dislikes", []),
                "gender": data.get("gender", "female")
            })
            return Response({"status": "success", "message": "个人信息已更新"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# ==========================================
# 3. 聊天接口
# ==========================================
class AgentChatView(APIView):
    def post(self, request):
        user_query = request.data.get("query", "")
        user_mode = request.data.get("mode", "standard")
        user_id = request.data.get("user_id")  # 前端必须传当前登录的 user_id
        session_id = request.data.get("session_id", f"session_{user_id}")

        user_profile = {}
        if user_id:
            profile_cypher = """
                        MATCH (u:User {id: $user_id})
                        RETURN u.name AS name, u.weight AS weight, u.height AS height, u.gender AS gender,
                               u.allergies AS allergies, u.dislikes AS dislikes,
                               coalesce(u.negative_feedback, []) AS negative_feedback
                        """
            profile_result = graph_db.query(profile_cypher, {"user_id": user_id})
            if profile_result:
                user_profile = profile_result[0]

        # 构造带有 user_profile 的图谱输入数据
        inputs = {
            "messages": [HumanMessage(content=user_query)],
            "user_mode": user_mode,
            "reflection_count": 0,
            "user_profile": user_profile  # <--- 自动注入！
        }

        config = {"configurable": {"thread_id": session_id}}

        try:
            result = app.invoke(inputs, config=config)
            return Response({"response": result['messages'][-1].content})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# ==========================================
# 用户负面反馈收集接口 (RLHF机制)
# ==========================================
class FeedbackView(APIView):
    def post(self, request):
        user_id = request.data.get("user_id")
        reason = request.data.get("reason")
        content = request.data.get("content", "") # 大模型原本的回答

        if not user_id or not reason:
            return Response({"error": "参数不完整"}, status=400)

        # 构造黑名单记忆（提取原回答的前40个字作为上下文关联）
        memory_entry = f"【不满意原因】：{reason}。（当时的失败推荐内容：{content[:40]}...）"

        # Cypher: 如果数组不存在就初始化为空数组，然后把新反馈追加进去
        cypher = """
        MATCH (u:User {id: $user_id})
        SET u.negative_feedback = coalesce(u.negative_feedback, []) + $memory_entry
        RETURN u.negative_feedback
        """
        try:
            graph_db.query(cypher, {"user_id": user_id, "memory_entry": memory_entry})
            return Response({"status": "success", "message": "反思记忆已写入图谱"})
        except Exception as e:
            return Response({"error": str(e)}, status=500)


# agent/views.py 追加以下代码

class RecipeDetailView(APIView):
    """
    [前端专用接口] 传入菜名列表，返回图谱中真实的完整菜谱数据
    """
    def post(self, request):
        names = request.data.get("names", [])
        if not names:
            return Response({"error": "未提供菜名"}, status=400)

        # 在数据库里精准匹配这些菜名，把真实数据捞出来
        cypher = """
        MATCH (n:Recipe)
        WHERE n.name IN $names
        RETURN n.name AS name, 
               n.calories AS calories,
               n.ingredients_raw AS ingredients,
               n.steps AS steps
        """
        try:
            results = graph_db.query(cypher, {"names": names})
            return Response({"status": "success", "data": results})
        except Exception as e:
            return Response({"error": str(e)}, status=500)