# agent/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from langchain_core.messages import HumanMessage

# 引入我们写好的 LangGraph Agent 大脑
from .graph import app
# 引入 Neo4j 数据库驱动 (用于用户画像存取)
from .neo4j_service import graph_db


# ==========================================
# 1. 聊天对话接口
# ==========================================
class AgentChatView(APIView):
    def post(self, request):
        # 解析前端传来的数据
        user_query = request.data.get("query", "")
        user_mode = request.data.get("mode", "standard")

        # 获取 session_id，用于 LangGraph 的短期记忆 (MemorySaver)
        # 实际项目中由前端生成或通过 token 解析，这里默认给一个测试 ID
        session_id = request.data.get("session_id", "xiaowu_session_001")

        print(f"View层收到: query={user_query}, mode={user_mode}, session_id={session_id}")

        if not user_query:
            return Response({"error": "Query is required"}, status=400)

        # 构造图谱输入数据
        inputs = {
            "messages": [HumanMessage(content=user_query)],
            "user_mode": user_mode,
            "reflection_count": 0  # 初始化反思计数器
        }

        config = {"configurable": {"thread_id": session_id}}

        try:
            print(f"正在调用 Agent 引擎...")
            # 注意这里多传了一个 config 参数
            result = app.invoke(inputs, config=config)

            # 提取最终回复
            final_response = result['messages'][-1].content

            return Response({
                "response": final_response,
            })
        except Exception as e:
            print(f"Agent Error: {e}")
            return Response({"error": str(e)}, status=500)


# ==========================================
# 2. 用户资料接口 (处理身高体重、忌口过敏等)
# ==========================================
class UserProfileView(APIView):
    def get(self, request):
        """获取当前用户的个人资料与图谱偏好"""
        user_id = request.query_params.get("user_id", "xiaowu_001")

        cypher = """
        MATCH (u:User {id: $user_id})
        RETURN u.name AS name, u.gender AS gender, u.birthday AS birthday,
               u.height AS height, u.weight AS weight, 
               u.allergies AS allergies, u.dislikes AS dislikes
        """
        try:
            result = graph_db.query(cypher, {"user_id": user_id})
            if result:
                return Response({"status": "success", "data": result[0]})
            return Response({"status": "not_found", "data": {}})
        except Exception as e:
            print(f"Profile Get Error: {e}")
            return Response({"status": "error", "message": str(e)}, status=500)

    def post(self, request):
        """保存前端修改的用户资料到 Neo4j"""
        data = request.data
        user_id = data.get("user_id", "xiaowu_001")

        # 使用 MERGE 确保用户存在，并更新其属性
        cypher = """
        MERGE (u:User {id: $user_id})
        SET u.name = $name,
            u.gender = $gender,
            u.birthday = $birthday,
            u.height = toFloat($height),
            u.weight = toFloat($weight),
            u.allergies = $allergies,
            u.dislikes = $dislikes
        RETURN u
        """
        try:
            graph_db.query(cypher, {
                "user_id": user_id,
                "name": data.get("name", ""),
                "gender": data.get("gender", "female"),
                "birthday": data.get("birthday", ""),
                "height": data.get("height", 0),
                "weight": data.get("weight", 0),
                "allergies": data.get("allergies", []),
                "dislikes": data.get("dislikes", [])
            })
            return Response({"status": "success", "message": "资料已保存入知识图谱"})
        except Exception as e:
            print(f"Profile Post Error: {e}")
            return Response({"status": "error", "message": str(e)}, status=500)