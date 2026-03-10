from agent.neo4j_service import graph_db


class SemanticMemory:
    """
    语义记忆：管理用户长期的结构化知识、偏好与图谱关系
    """

    @staticmethod
    def get_user_profile(user_id):
        """从 Neo4j 提取用户的完整长期记忆画像"""
        if not user_id:
            return {}

        cypher = """
        MATCH (u:User {id: $user_id})
        RETURN u.name AS name, u.weight AS weight, u.height AS height, u.gender AS gender,
               u.allergies AS allergies, u.dislikes AS dislikes,
               coalesce(u.negative_feedback, []) AS negative_feedback,
               coalesce(u.birth_date, "") AS birthDate
        """
        try:
            result = graph_db.query(cypher, {"user_id": user_id})
            return result[0] if result else {}
        except Exception as e:
            print(f"提取语义记忆失败: {e}")
            return {}

    @staticmethod
    def add_negative_feedback(user_id, memory_entry):
        """向图谱追加一条负面偏好记忆 (RLHF落地)"""
        if not user_id:
            return False

        cypher = """
        MATCH (u:User {id: $user_id})
        SET u.negative_feedback = coalesce(u.negative_feedback, []) + [$memory_entry]
        RETURN u.negative_feedback
        """
        try:
            graph_db.query(cypher, {"user_id": user_id, "memory_entry": memory_entry})
            return True
        except Exception as e:
            print(f"写入负面记忆失败: {e}")
            return False