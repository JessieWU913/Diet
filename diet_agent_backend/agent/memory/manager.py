from .semantic import SemanticMemory
from .working import WorkingMemory
from .episodic import EpisodicMemory

class MemoryManager:
    """
    记忆调度中枢：为 Agent 提供统一的记忆存取接口
    """

    @staticmethod
    def build_system_memory_prompt(user_id):
        """
        获取用户的全部长期记忆，并将其组装为 System Prompt 字符串
        """
        profile = SemanticMemory.get_user_profile(user_id)
        if not profile:
            return "当前为未登录访客，无历史记忆数据。"

        name = profile.get("name", "用户")
        allergies = profile.get("allergies", [])
        dislikes = profile.get("dislikes", [])
        avoid_str = "、".join(allergies + dislikes) if (allergies or dislikes) else "无特殊忌口"

        prompt_lines = [
            f"【长期记忆 - 基础画像】：",
            f"- 用户姓名：{name}",
            f"- 明确忌口/过敏源：{avoid_str}",
        ]

        negative_feedback = profile.get("negative_feedback", [])
        if negative_feedback:
            recent_lessons = "\n".join([f"  * {item}" for item in negative_feedback[-3:]])
            prompt_lines.append("\n【长期记忆 - 历史教训】：")
            prompt_lines.append("该用户曾对你的推荐给出过极度不满的负面反馈。在本次对话中，你必须主动避开以下雷区：")
            prompt_lines.append(recent_lessons)

        recent_meals = EpisodicMemory.get_recent_meals(user_id, days_limit=3)
        if recent_meals:
            prompt_lines.append("\n【情景记忆 - 近期饮食记录】：")
            prompt_lines.append("为了保证饮食多样性，以下是用户近期的菜谱安排：")
            prompt_lines.extend([f"- {meal}" for meal in recent_meals])
            prompt_lines.append("请在本次推荐中尽量避开上述最近吃过的菜品，推荐一些新鲜的搭配！")

        return "\n".join(prompt_lines)

    @staticmethod
    def save_user_feedback(user_id, reason, original_content):
        """统一封装：存储反馈记忆"""
        memory_entry = f"【不满意原因】：{reason}。（失败推荐上下文：{original_content[:40]}...）"
        return SemanticMemory.add_negative_feedback(user_id, memory_entry)

    @staticmethod
    def save_user_positive_feedback(user_id, reason, original_content):
        """统一封装：存储正向反馈记忆"""
        memory_entry = f"【满意点】：{reason}。（成功推荐上下文：{original_content[:40]}...）"
        return SemanticMemory.add_positive_feedback(user_id, memory_entry)

    @staticmethod
    def apply_working_memory(messages):
        """统一封装：压缩工作记忆"""
        return WorkingMemory.compress_messages(messages)