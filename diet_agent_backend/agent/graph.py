# agent/graph.py
import re
import json
import os
from typing import TypedDict, List, Dict, Any, Literal

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from .mcp_tools import vector_search_recipe, get_food_nutrition, check_food_conflicts, search_recipe_by_ingredients


# 状态定义
class AgentState(TypedDict):
    messages: List[BaseMessage]
    user_mode: str
    reflection_count: int
    user_profile: Dict[str, Any]

# 模型与工具初始化
llm = ChatOpenAI(
    base_url=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
    model=os.getenv("LLM_MODEL_NAME"),
    default_headers={"X-Failover-Enabled": "true"},
    model_kwargs={
        "extra_body": {"top_k": 20}
    },
    max_tokens=2048,
    temperature=0.1,
    frequency_penalty=1.1
)

# 绑定四大工具
tools = [vector_search_recipe, get_food_nutrition, check_food_conflicts, search_recipe_by_ingredients]
llm_with_tools = llm.bind_tools(tools)


# 核心节点
# agent/graph.py

def agent_node(state: AgentState):
    mode = state.get('user_mode', 'standard')
    messages = state['messages']
    profile = state.get('user_profile', {})

    # 提取用户的个人信息
    name = profile.get("name", "用户")
    allergies = profile.get("allergies", [])
    dislikes = profile.get("dislikes", [])
    gender = profile.get("gender", "female")
    height = profile.get("height", 0)
    weight = profile.get("weight", 0)
    negative_feedback = profile.get("negative_feedback", [])

    avoid_ingredients = allergies + dislikes

    system_prompt = """你是一个连接了 Neo4j 专业营养知识图谱的膳食健康助手。
    你的任务是根据图谱返回的【真实数据】为用户提供饮食建议。你正在为用户【{name}】提供专属服务。

    【核心指令】：
    1. 优先调用工具：必须且只能调用工具来获取食物信息，严禁胡编乱造。
    2. JSON 解析逻辑：
       - 工具返回的 `nutrients_raw` 或 `ingredients_raw` 是 JSON 字符串。你必须像程序员一样解析它们，提取出“热量”、“蛋白质”、“脂肪”等关键数值告知用户。
       - 如果 `nutrients_raw` 中包含“营养建议”或“建议”，请务必将其作为你回答的一部分。
    3. 减脂意图识别：
       【减脂纪律与营养师解析】：
       - 只要用户提到“减脂、减肥”或处于 weight_loss 模式，必须传 strict_mode=True。
       - 拿到图谱返回的菜谱后，你【必须】像专业营养师一样分析宏量营养素（Macros）：
            1. 点出该菜谱的蛋白质含量（如果高，要夸奖它有助于维持肌肉）。
            2. 提示脂肪或碳水含量（如果碳水偏高，主动建议用户本餐减少米饭等主食的摄入）。
       - 话术示例：“为您推荐【葱爆鸡丁】。这道菜热量仅为 200 大卡，且含有 18g 优质蛋白质，非常适合您的减脂需求。由于菜品本身包含少量碳水，建议搭配粗粮食用。”
    4. 兜底逻辑：
       - 如果 `search_recipe_by_ingredients` 没搜到，必须尝试用 `vector_search_recipe` 进行语义搜索。
       - 若所有工具都显示“未找到”，请礼貌告知并建议用户尝试更通用的食材名词。
    5. 意图分离法则：调用 vector_search_recipe 时，query 只能填正向词。

    【回复风格】：
    - 像朋友一样亲切，但像医生一样专业。
    - 回复示例：“为您在图谱中找到了[菜名]。这道菜含有[热量]大卡，蛋白质[XX]g，非常适合[减脂/日常]需求。做法也很简单：[步骤简述]。”
    """
    if negative_feedback:
        recent_lessons = "\n".join([f"- {item}" for item in negative_feedback[-10:]])
        system_prompt += f"""
        【历史负面反馈】：
        用户曾对你过去的推荐给出过以下严厉的负面反馈（点踩记录）：
        {recent_lessons}

        作为智能体，你必须拥有记忆并进行自我反思！在本次推荐中，请【绝对不要】犯同样的错误。如果你发现图谱搜出的菜品命中了上述黑名单原因，请主动过滤掉它们，寻找其他替代方案！
        """

    if avoid_ingredients:
        system_prompt += f"""
        【忌口警告】：
        用户明确表示过敏或不吃的食材包括：{avoid_ingredients}。
        你在调用任何工具（如 vector_search_recipe 或 search_recipe_by_ingredients）时，
        【必须】主动将 {avoid_ingredients} 填入 `exclude_ingredients` 参数中，绝不能推荐包含这些食材的菜谱！
        """

    if mode == 'weight_loss' and weight > 0 and height > 0:
        # 1. 估算基础代谢 BMR (Mifflin-St Jeor 公式，默认按大学生年龄 22 岁计算)
        age = 22
        if gender == 'male':
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        # 2. 计算日常总消耗 TDEE (假设轻度活动系数 1.375)
        tdee = bmr * 1.375

        # 3. 制造减脂热量缺口 (每日减去 400 大卡)
        target_calories = tdee - 400

        # 4. 三餐科学分配 (30%, 40%, 30%)
        breakfast_cal = target_calories * 0.3
        lunch_cal = target_calories * 0.4
        dinner_cal = target_calories * 0.3

        system_prompt += f"""
        【智能减脂与饱腹感管理引擎】：
        基于用户的身体数据，系统已自动计算出其科学减脂指标：
        - 每日总消耗 (TDEE)：约 {int(tdee)} 千卡
        - 减脂期每日目标热量：约 {int(target_calories)} 千卡
        - 本餐建议分配：早餐 {int(breakfast_cal)}千卡，午餐 {int(lunch_cal)}千卡，晚餐 {int(dinner_cal)}千卡。

        【拼餐与饱腹感(极度重要)】：
        当用户要求推荐特定正餐（如“推荐晚餐”）时，你的推荐总热量必须尽量贴近该餐的目标值（如晚餐需凑够约 {int(dinner_cal)} 千卡）。
        1. 拒绝孤立的低热量食物：如果图谱搜出的菜（如烤肉串、凉拌黄瓜）只有 100 千卡，绝对不能只推荐这一个菜！用户会吃不饱！
        2. 必须进行智能拼餐：你必须挑选 1 个主菜 + 1 个配菜，或者主动建议用户搭配主食（例如：“图谱中的蒜蓉西兰花热量仅为80千卡，为了保证饱腹感，建议您搭配 150g 糙米饭（约170千卡）和一份煎鸡胸肉”），直到一顿饭的总热量接近目标值。
        3. 清晰展示加总逻辑：在回答时，列出推荐组合，并计算总热量给用户看。
        """
    elif weight > 0:
        system_prompt += f"\n【健康参考】：用户当前体重为 {weight}kg。请在推荐时保持营养均衡。"

    if isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=system_prompt)
    else:
        messages.insert(0, SystemMessage(content=system_prompt))

    response = llm_with_tools.invoke(messages)

    if not response.tool_calls:
        content = response.content
        target_tools = [
            "get_food_nutrition",
            "check_food_conflicts",
            "search_recipe_by_ingredients",
            "vector_search_recipe"
        ]

        for tool_name in target_tools:
            if tool_name in content:
                print(f"拦截到 Gitee 漏出的工具标记: {tool_name}")
                try:
                    match = re.search(f"{tool_name}.*?({{.*?}})", content, re.DOTALL)
                    if match:
                        args = json.loads(match.group(1))
                        print(f"强制执行工具: {tool_name} | 参数: {args}")

                        response = AIMessage(
                            content="",
                            tool_calls=[{
                                "name": tool_name,
                                "args": args,
                                "id": f"call_gitee_{tool_name}"
                            }]
                        )
                        break
                except Exception as e:
                    print(f"JSON解析失败: {e}")

    return {"messages": [response]}


# 反思节点
def reflector_node(state: AgentState):
    mode = state.get('user_mode', 'standard')
    messages = state['messages']
    count = state.get('reflection_count', 0)

    human_msgs = [m.content for m in messages if isinstance(m, HumanMessage)]
    is_diet_intent = any(keyword in msg for msg in human_msgs for keyword in ["减脂", "减肥", "瘦身", "轻食"])

    is_strict = (mode == 'weight_loss') or is_diet_intent

    if not is_strict or count >= 2:
        return {"reflection_count": count}

    last_msg = messages[-1]

    if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
        content = last_msg.content

        unhealthy_keywords = ["大肠", "奶油", "拔丝", "糖溜", "油炸", "肥肉", "猪板油", "腊肉", "红烧", "深炸"]
        found_problems = [k for k in unhealthy_keywords if k in content]

        if found_problems:
            print(f"触发AI反思：检测到违禁词汇 {found_problems}，打回重做！")

            # 用严厉的语气逼迫模型重新生成
            correction_msg = HumanMessage(
                content=f"系统强制拦截：用户明确要求减脂，但你的推荐中竟然包含了高脂肪的【{', '.join(found_problems)}】！"
                        f"请立刻重新思考并回答。如果没有找到低脂的鸡肉菜谱，你就坦白告诉用户没找到，绝对不允许推荐大肠、奶油等不健康的食物！"
                        f"错误拦截：用户想做的是【菜】，而你推荐的是【{found_problems}】类甜点/高油炸食品。请重新从图谱中寻找更像‘正菜’的鸡蛋料理（如西红柿炒蛋、蒸蛋等）！"
            )
            return {"messages": [correction_msg], "reflection_count": count + 1}

    return {"reflection_count": count}


# 路由判断逻辑
def router(state: AgentState) -> Literal["tools", "reflector"]:
    """判断是去执行工具，还是去进行输出反思"""
    last_msg = state['messages'][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        return "tools"
    return "reflector"


def reflector_router(state: AgentState) -> Literal["agent", "__end__"]:
    """判断反思后是否需要让Agent重做"""
    if isinstance(state['messages'][-1], HumanMessage):
        return "agent"
    return "__end__"


# 构建图结构

workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))
workflow.add_node("reflector", reflector_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges("agent", router)
workflow.add_edge("tools", "agent")
workflow.add_conditional_edges("reflector", reflector_router)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)