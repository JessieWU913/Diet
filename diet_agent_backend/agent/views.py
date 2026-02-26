# agent/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from langchain_core.messages import HumanMessage
from .graph import app
from .neo4j_service import graph_db

class AgentChatView(APIView):

    def post(self, request):
        # 1. 获取数据
        user_query = request.data.get("query", "")
        user_mode = request.data.get("mode", "standard")

        print(f"View层收到: query={user_query}, mode={user_mode}")

        if not user_query:
            return Response({"error": "Query is required"}, status=400)

        # 2. 构造输入
        inputs = {
            "messages": [HumanMessage(content=user_query)],
            "user_mode": user_mode,
            "reflection_count": 0  # 初始化计数器
        }

        try:
            # 3. 调用 Agent
            print(f"正在调用 Agent, inputs: {inputs}")
            result = app.invoke(inputs)

            final_response = result['messages'][-1].content

            return Response({
                "response": final_response,
            })
        except Exception as e:
            print(f"Agent Error: {e}")
            return Response({"error": str(e)}, status=500)


class FeedbackView(APIView):
    def post(self, request):
        data = request.data
        msg_content = data.get('message_content')
        feedback_type = data.get('type')  # like / dislike
        reasons = data.get('reasons', [])

        print(f"收到用户反馈: {feedback_type} | 原因: {reasons}")

        # 【核心逻辑】：如何影响未来？
        # 简单做法：将不喜欢的内容存入 User Profile (Neo4j 或 Session)
        # 比如：用户选了"食材过敏"，且内容里包含"虾" -> 提取"虾" -> 存入 "Allergy" 列表

        # 毕设演示阶段，我们可以简单打印或存个 Log 文件
        # 进阶做法是存入 Neo4j: (User)-[:DISLIKES]->(Recipe)

        return Response({"status": "success"})




class UserProfileView(APIView):
    # 获取用户资料
    def get(self, request):
        # 实际项目中这里用 token 解析出 user_id，毕设演示先用固定 ID
        user_id = request.query_params.get("user_id", "xiaowu_001")

        cypher = """
        MATCH (u:User {id: $user_id})
        RETURN u.name AS name, u.gender AS gender, u.birthday AS birthday,
               u.height AS height, u.weight AS weight, 
               u.allergies AS allergies, u.dislikes AS dislikes
        """
        result = graph_db.query(cypher, {"user_id": user_id})

        if result:
            return Response({"status": "success", "data": result[0]})
        return Response({"status": "not_found", "data": {}})

    # 保存用户资料
    def post(self, request):
        data = request.data
        user_id = data.get("user_id", "xiaowu_001")

        # 将用户属性直接打到 User 节点上
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
            return Response({"status": "error", "message": str(e)}, status=500)