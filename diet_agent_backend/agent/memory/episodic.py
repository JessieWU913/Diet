# agent/memory/episodic.py
from agent.neo4j_service import graph_db
from datetime import datetime


class EpisodicMemory:
    """
    情景/事件记忆：记录用户在特定时间点发生的事件（如：昨天的菜谱排期记录）
    """

    @staticmethod
    def record_meal_event(user_id, recipe_names, date_str=None):
        """
        当用户在前端生成或导出一份菜谱时，将这个【推荐事件】存入图谱
        recipe_names: 菜名列表，例如 ['番茄炒蛋', '蒜蓉西兰花']
        """
        if not user_id or not recipe_names:
            return False

        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")

        cypher = """
        MATCH (u:User {id: $user_id})
        // 1. 创建当天的饮食事件节点
        MERGE (e:Event {user_id: $user_id, date: $date, type: 'daily_meal'})
        MERGE (u)-[:HAS_EVENT]->(e)

        WITH e
        // 2. 将推荐的菜品与事件节点相连
        UNWIND $recipe_names AS recipe_name
        MATCH (r:Recipe {name: recipe_name})
        MERGE (e)-[:ATE]->(r)
        """
        try:
            graph_db.query(cypher, {
                "user_id": user_id,
                "date": date_str,
                "recipe_names": recipe_names
            })
            return True
        except Exception as e:
            print(f"写入情景记忆失败: {e}")
            return False

    @staticmethod
    def get_recent_meals(user_id, days_limit=3):
        """
        提取用户最近几天的就餐记录，用于给大模型进行去重反思
        """
        if not user_id:
            return []

        cypher = """
        MATCH (u:User {id: $user_id})-[:HAS_EVENT]->(e:Event)-[:ATE]->(r:Recipe)
        RETURN e.date AS date, collect(r.name) AS recipes
        ORDER BY e.date DESC
        LIMIT $limit
        """
        try:
            results = graph_db.query(cypher, {"user_id": user_id, "limit": days_limit})
            formatted_history = [f"{record['date']}安排了: {', '.join(record['recipes'])}" for record in results]
            return formatted_history
        except Exception as e:
            print(f"提取情景记忆失败: {e}")
            return []