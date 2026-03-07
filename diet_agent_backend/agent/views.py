from langchain_core.utils import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from langchain_core.messages import HumanMessage

from .memory.manager import MemoryManager
from .memory.semantic import SemanticMemory
from .memory.episodic import EpisodicMemory

from .graph import app
from .neo4j_service import graph_db

# 用户注册与登录接口
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

# 用户资料填写接口
class UserProfileView(APIView):
    def get(self, request):
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "缺少 user_id"}, status=400)

        cypher = """
        MATCH (u:User {id: $user_id})
        RETURN u.gender AS gender, u.height AS height, u.weight AS weight, 
               u.allergies AS allergies, u.dislikes AS dislikes, u.birth_date AS birthDate
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
        birth_date = request.data.get('birthDate')

        # 忌口数组保存到 Neo4j 的 User 节点中
        cypher = """
        MATCH (u:User {id: $user_id})
        SET u.height = toFloat($height),
            u.weight = toFloat($weight),
            u.allergies = $allergies,
            u.dislikes = $dislikes,
            u.birth_date = $birth_date,
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

        if not user_id or not reason:
            return Response({"error": "参数不完整"}, status=400)

        success = MemoryManager.save_user_feedback(user_id, reason, content)

        if success:
            return Response({"status": "success", "message": "反思记忆已写入图谱"})
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