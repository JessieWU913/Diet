# agent/memory/manager.py
from .semantic import SemanticMemory
from .working import WorkingMemory


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

        # 1. 基础画像记忆
        name = profile.get("name", "用户")
        allergies = profile.get("allergies", [])
        dislikes = profile.get("dislikes", [])
        avoid_str = "、".join(allergies + dislikes) if (allergies or dislikes) else "无特殊忌口"

        prompt_lines = [
            f"【长期记忆 - 基础画像】：",
            f"- 用户姓名：{name}",
            f"- 明确忌口/过敏源：{avoid_str}",
        ]

        # 2. 负面反馈记忆 (RLHF 进化机制)
        negative_feedback = profile.get("negative_feedback", [])
        if negative_feedback:
            # 提取最近的 3 次教训防止过长
            recent_lessons = "\n".join([f"  * {item}" for item in negative_feedback[-3:]])
            prompt_lines.append("\n【长期记忆 - 历史教训】：")
            prompt_lines.append("该用户曾对你的推荐给出过极度不满的负面反馈。在本次对话中，你必须主动避开以下雷区：")
            prompt_lines.append(recent_lessons)

        return "\n".join(prompt_lines)

    @staticmethod
    def save_user_feedback(user_id, reason, original_content):
        """统一封装：存储反馈记忆"""
        memory_entry = f"【不满意原因】：{reason}。（失败推荐上下文：{original_content[:40]}...）"
        return SemanticMemory.add_negative_feedback(user_id, memory_entry)

    @staticmethod
    def apply_working_memory(messages):
        """统一封装：压缩工作记忆"""
        return WorkingMemory.compress_messages(messages)