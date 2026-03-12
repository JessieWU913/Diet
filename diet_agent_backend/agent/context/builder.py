"""
ContextBuilder — GSSC 上下文工程管线

Gather  → 从所有来源收集原始上下文碎片
Select  → 按相关性 / 时效性评分，淘汰低价值碎片
Structure → 用 PromptTemplate 组装为 6 段式结构化 prompt
Compress → TokenBudget 守卫，超预算时逐层降级压缩

用法:
    from agent.context import ContextBuilder

    builder = ContextBuilder(user_id="u1", user_mode="weight_loss", profile={...})
    system_prompt, compressed_messages = builder.build(messages)
"""

from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage

from .template import PromptTemplate
from .budget import TokenBudget
from ..memory.semantic import SemanticMemory
from ..memory.episodic import EpisodicMemory


class ContextBuilder:
    """GSSC 上下文管线的统一入口"""

    def __init__(
        self,
        user_id: str,
        user_mode: str = "standard",
        profile: dict = None,
        max_tokens: int = 2048,
        max_history: int = 6,
    ):
        self.user_id = user_id
        self.user_mode = user_mode
        self.profile = profile or {}
        self.max_history = max_history
        self.budget = TokenBudget(total_limit=max_tokens)

    # Gather: 收集所有原始上下文碎片
    def _gather(self) -> dict:
        """从各个记忆层收集原始信息"""
        fragments = {}

        # 语义记忆（用户画像 + 忌口 + 负面反馈）
        profile_data = SemanticMemory.get_user_profile(self.user_id)
        fragments["profile"] = profile_data or {}

        # 情景记忆（近期饮食记录）
        fragments["recent_meals"] = EpisodicMemory.get_recent_meals(
            self.user_id, days_limit=3
        )

        # 当前会话传入前端的身高体重等
        fragments["session_profile"] = self.profile

        return fragments

    # Select: 按价值评分，只保留高价值碎片
    def _select(self, fragments: dict) -> dict:
        """根据用户模式和相关性，过滤 / 优先排序碎片"""
        selected = {}

        # 合并profile数据
        merged_profile = {**fragments["profile"], **fragments["session_profile"]}
        selected["profile"] = merged_profile

        # 负反馈只保留最近3条
        neg = merged_profile.get("negative_feedback", [])
        selected["negative_feedback"] = neg[-3:] if neg else []

        # 情景记忆：减脂模式下保留3天，普通模式2天
        meals = fragments["recent_meals"]
        if self.user_mode != "weight_loss" and len(meals) > 2:
            meals = meals[:2]
        selected["recent_meals"] = meals

        return selected

    # Structure: 组装为6段式结构化prompt
    def _structure(self, selected: dict) -> str:
        """将筛选后的碎片注入 PromptTemplate"""
        # 构建memory_prompt（Context区块）
        memory_lines = []

        profile = selected["profile"]
        name = profile.get("name", "用户")
        allergies = profile.get("allergies", [])
        dislikes = profile.get("dislikes", [])
        avoid_str = "、".join(allergies + dislikes) if (allergies or dislikes) else "无特殊忌口"

        memory_lines.append("【长期记忆 - 基础画像】：")
        memory_lines.append(f"- 用户姓名：{name}")
        memory_lines.append(f"- 明确忌口/过敏源：{avoid_str}")

        # 负面反馈
        neg = selected.get("negative_feedback", [])
        if neg:
            memory_lines.append("\n【长期记忆 - 历史教训】：")
            memory_lines.append("该用户曾对你的推荐给出过负面反馈，必须主动避开以下雷区：")
            for item in neg:
                memory_lines.append(f"  * {item}")

        # 近期饮食
        meals = selected.get("recent_meals", [])
        if meals:
            memory_lines.append("\n【情景记忆 - 近期饮食记录】：")
            memory_lines.append("为保证饮食多样性，以下是用户近期的菜谱安排：")
            for meal in meals:
                memory_lines.append(f"- {meal}")
            memory_lines.append("请在本次推荐中尽量避开上述最近吃过的菜品，推荐新鲜搭配！")

        memory_prompt = "\n".join(memory_lines)

        # PromptTemplate组装
        return PromptTemplate.assemble(
            user_mode=self.user_mode,
            profile=self.profile,
            memory_prompt=memory_prompt,
        )

    # Compress: token 预算
    def _compress_prompt(self, prompt: str) -> str:
        """如果 system prompt 超预算，逐层压缩"""
        # system prompte分role+state+context+output
        # 分配约70%给system prompt，30%留给对话历史
        system_budget = int(self.budget.total_limit * 0.7)
        current = self.budget.estimate_tokens(prompt)

        if current <= system_budget:
            return prompt

        # 找到情景记忆段并截断
        marker = "【情景记忆 - 近期饮食记录】"
        if marker in prompt:
            idx = prompt.index(marker)
            next_section = prompt.find("\n【", idx + len(marker))
            if next_section == -1:
                next_section = len(prompt)
            episode_block = prompt[idx:next_section]
            lines = episode_block.split("\n")
            # 只保留标题和最近1天
            if len(lines) > 3:
                trimmed = "\n".join(lines[:3]) + "\n- ...(更早记录已省略)"
                prompt = prompt[:idx] + trimmed + prompt[next_section:]

        return prompt

    def _compress_messages(self, messages: list) -> list:
        """智能消息压缩：保留最近 N 轮，去除孤立 ToolMessage"""
        if not messages:
            return []

        compressed = list(messages)

        if len(compressed) > self.max_history:
            compressed = compressed[-self.max_history:]

        while compressed:
            first = compressed[0]
            if isinstance(first, (ToolMessage, SystemMessage)):
                compressed.pop(0)
            elif isinstance(first, AIMessage) and getattr(first, "tool_calls", None):
                compressed.pop(0)
            else:
                break

        return compressed

    # 统一构建入口
    def build(self, messages: list) -> tuple[str, list]:
        """
        执行完整 GSSC 管线。

        返回:
            (system_prompt, compressed_messages)
        """
        fragments = self._gather()

        selected = self._select(fragments)

        system_prompt = self._structure(selected)

        system_prompt = self._compress_prompt(system_prompt)
        compressed_messages = self._compress_messages(messages)

        return system_prompt, compressed_messages
