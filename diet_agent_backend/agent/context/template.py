"""
PromptTemplate — 6 段式结构化提示词模板

[Role & Policies]  — 角色定义与不变铁律 (稳定层，每轮不变)
[Task]             — 当前用户意图 / 本轮任务描述
[State]            — 用户画像 + 体征 + 减脂指标
[Evidence]         — 来自工具 / 知识图谱的事实证据
[Context]          — 长期记忆 + 情景记忆 + 对话历史
[Output]           — 输出格式与风格约束
"""

from datetime import datetime


class PromptTemplate:
    """6 段式结构化 system prompt 构建器"""

    ROLE_AND_POLICIES = """你是一个连接了 Neo4j 专业营养知识图谱的膳食健康助手。
你的任务是根据图谱返回的【真实数据】为用户提供饮食建议。

【铁律】：
1. 优先调用工具获取食物信息，严禁编造数据。
2. 工具返回的 nutrients_raw / ingredients_raw 是 JSON 字符串，你必须解析并提取关键数值。
3. 若 nutrients_raw 含"营养建议"，务必纳入回答。
4. 调用 vector_search_recipe 时 query 只填正向需求词，忌口放 exclude_ingredients。
5. search_recipe_by_ingredients 未命中时，必须降级到 vector_search_recipe 二次搜索。"""

    OUTPUT_STYLE = """【回复风格】：像朋友一样亲切，但像医生一样专业。"""

    @classmethod
    def build_role_section(cls) -> str:
        return cls.ROLE_AND_POLICIES

    @classmethod
    def build_task_section(cls, user_mode: str) -> str:
        """根据用户模式生成任务描述"""
        if user_mode == "weight_loss":
            return "【当前任务】：用户处于减脂模式。所有推荐必须传 strict_mode=True，并进行宏量营养素分析（蛋白质含量、脂肪/碳水风险）。"
        return "【当前任务】：用户处于日常饮食模式，保持营养均衡即可。"

    @classmethod
    def build_state_section(cls, profile: dict, user_mode: str) -> str:
        """构建用户物理状态 + 减脂指标"""
        raw_height = profile.get("height")
        raw_weight = profile.get("weight")
        height = float(raw_height) if raw_height else 0.0
        weight = float(raw_weight) if raw_weight else 0.0
        gender = profile.get("gender", "female")
        birth_date = profile.get("birth_date")

        age = 22
        if birth_date:
            try:
                birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
                age = datetime.now().year - birth_year
            except ValueError:
                pass

        lines = [f"【用户状态】：身高 {height}cm，体重 {weight}kg，性别 {gender}，年龄约 {age} 岁。"]

        if user_mode == "weight_loss" and weight > 0 and height > 0:
            if gender == "male":
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161

            tdee = bmr * 1.375
            target = tdee - 400
            lines.append(f"""
【智能减脂引擎】：
- TDEE：约 {int(tdee)} 千卡
- 减脂期每日目标：约 {int(target)} 千卡
- 餐次分配：早餐 {int(target * 0.3)} 千卡 | 午餐 {int(target * 0.4)} 千卡 | 晚餐 {int(target * 0.3)} 千卡

【拼餐与饱腹感(极度重要)】：
推荐特定正餐时，总热量必须贴近该餐目标值。
1. 拒绝孤立的低热量食物——只推 100 千卡的菜，用户会吃不饱！
2. 必须智能拼餐：1 个主菜 + 1 个配菜 / 搭配主食，直到总热量接近目标。
3. 清晰展示加总逻辑：列出推荐组合并计算总热量。""")
        elif weight > 0:
            lines.append(f"用户体重 {weight}kg，推荐时保持营养均衡。")

        return "\n".join(lines)

    @classmethod
    def build_evidence_section(cls) -> str:
        """证据区块 — 由工具调用结果动态填充，初始为空提示"""
        return ""  # 工具返回时由 LangGraph ToolMessage 自动注入

    @classmethod
    def build_context_section(cls, memory_prompt: str) -> str:
        """长期记忆 + 情景记忆"""
        if not memory_prompt:
            return ""
        return memory_prompt

    @classmethod
    def build_output_section(cls) -> str:
        return cls.OUTPUT_STYLE

    @classmethod
    def assemble(cls, user_mode: str, profile: dict, memory_prompt: str) -> str:
        """组装 6 段式 system prompt"""
        sections = [
            cls.build_role_section(),
            cls.build_task_section(user_mode),
            cls.build_state_section(profile, user_mode),
            cls.build_context_section(memory_prompt),
            cls.build_output_section(),
        ]

        return "\n\n".join(s for s in sections if s)
