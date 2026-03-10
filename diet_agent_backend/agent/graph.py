# agent/graph.py
import re
import json
import os
import operator
from datetime import datetime
from typing import TypedDict, Literal, Annotated, Sequence

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.utils.function_calling import convert_to_openai_function

from .mcp_tools import vector_search_recipe, get_food_nutrition, check_food_conflicts, search_recipe_by_ingredients

from .memory.manager import MemoryManager

# 状态定义
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_mode: str
    reflection_count: int
    user_profile: dict
    user_id: str

# 模型与工具初始化
llm = ChatOpenAI(
    base_url=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
    model=os.getenv("LLM_MODEL_NAME"),
    default_headers={"X-Failover-Enabled": "true"},
    extra_body={"top_k": 20},
    max_tokens=2048,
    temperature=0.1,
    frequency_penalty=1.1
)

# 绑定四大工具（使用 functions 格式兼容 Gitee AI 等国产 API）
tools = [vector_search_recipe, get_food_nutrition, check_food_conflicts, search_recipe_by_ingredients]
openai_fns = [convert_to_openai_function(t) for t in tools]
llm_with_tools = llm.bind(functions=openai_fns)


# 核心节点
def agent_node(state: AgentState):
    mode = state.get('user_mode', 'standard')
    profile = state.get('user_profile', {})
    user_id = state.get('user_id')

    compressed_messages = MemoryManager.apply_working_memory(state['messages'])
    messages = list(compressed_messages)

    # 用户的忌口、负面反馈和历史推荐记录
    memory_prompt = MemoryManager.build_system_memory_prompt(user_id)

    raw_height = profile.get("height")
    raw_weight = profile.get("weight")

    height = float(raw_height) if raw_height else 0.0
    weight = float(raw_weight) if raw_weight else 0.0
    gender = profile.get("gender", "female")
    birth_date = profile.get("birth_date")

    system_prompt = f"""你是一个连接了 Neo4j 专业营养知识图谱的膳食健康助手。
        你的任务是根据图谱返回的【真实数据】为用户提供饮食建议。

        {memory_prompt}

【核心指令】：
1. 优先调用工具：必须且只能调用工具来获取食物信息，严禁胡编乱造。
2. JSON 解析逻辑：
   - 工具返回的 `nutrients_raw` 或 `ingredients_raw` 是 JSON 字符串。你必须像程序员一样解析它们，提取出关键数值告知用户。
   - 如果 `nutrients_raw` 中包含“营养建议”，务必将其作为你回答的一部分。
3. 减脂意图识别：
   - 只要用户提到“减脂、减肥”或处于 weight_loss 模式，必须传 strict_mode=True。
   - 拿到菜谱后，你【必须】像专业营养师一样分析宏量营养素（点出蛋白质含量，提示脂肪或碳水风险）。
4. 兜底逻辑：
   - 如果 `search_recipe_by_ingredients` 没搜到，必须尝试用 `vector_search_recipe` 进行语义搜索。
5. 意图分离法则：调用 vector_search_recipe 时，query 只能填正向词。

【回复风格】：
- 像朋友一样亲切，但像医生一样专业。
"""

    age = 22  # 设个兜底默认值
    if birth_date:
        try:
            birth_year = datetime.strptime(birth_date, "%Y-%m-%d").year
            current_year = datetime.now().year
            age = current_year - birth_year
        except ValueError:
            pass

    if mode == 'weight_loss' and weight > 0 and height > 0:
        if gender == 'male':
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        tdee = bmr * 1.375
        target_calories = tdee - 400
        breakfast_cal = target_calories * 0.3
        lunch_cal = target_calories * 0.4
        dinner_cal = target_calories * 0.3

        system_prompt += f"""
【智能减脂与饱腹感管理引擎】：
基于用户的身体数据，科学减脂指标如下：
- TDEE：约 {int(tdee)} 千卡
- 减脂期每日目标：约 {int(target_calories)} 千卡
- 本餐建议分配：早餐 {int(breakfast_cal)}千卡，午餐 {int(lunch_cal)}千卡，晚餐 {int(dinner_cal)}千卡。

【拼餐与饱腹感(极度重要)】：
当用户要求推荐特定正餐时，推荐总热量必须尽量贴近该餐的目标值。
1. 拒绝孤立的低热量食物：绝对不能只推荐一个 100 千卡的菜，用户会吃不饱！
2. 必须进行智能拼餐：挑选 1个主菜 + 1个配菜，或主动搭配主食，直到总热量接近目标值。
3. 清晰展示加总逻辑：列出推荐组合，并计算总热量。
"""
    elif weight > 0:
        system_prompt += f"\n【健康参考】：用户当前体重为 {weight}kg。请在推荐时保持营养均衡。"

    # 将 System Prompt 置于消息流首位
    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=system_prompt)
    else:
        messages.insert(0, SystemMessage(content=system_prompt))

    response = llm_with_tools.invoke(messages)

    # 🌟 兜底：拦截 Gitee 漏出标记 (保留你的原生逻辑)
    if not response.tool_calls:
        content = response.content
        target_tools = ["get_food_nutrition", "check_food_conflicts", "search_recipe_by_ingredients", "vector_search_recipe"]
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
                            tool_calls=[{"name": tool_name, "args": args, "id": f"call_gitee_{tool_name}"}]
                        )
                        break
                except Exception as e:
                    print(f"JSON解析失败: {e}")

    return {"messages": [response]}


# 反思节点 (保持不变)
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
            correction_msg = HumanMessage(
                content=f"系统强制拦截：用户明确要求减脂，但你的推荐中包含了高脂肪的【{', '.join(found_problems)}】！请立刻重新思考并回答。拒绝推荐大肠、奶油等食物！"
            )
            return {"messages": [correction_msg], "reflection_count": count + 1}

    return {"reflection_count": count}


# 路由判断与构建 (保持不变)
def router(state: AgentState) -> Literal["tools", "reflector"]:
    last_msg = state['messages'][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        return "tools"
    return "reflector"

def reflector_router(state: AgentState) -> Literal["agent", "__end__"]:
    if isinstance(state['messages'][-1], HumanMessage):
        return "agent"
    return "__end__"

# 自定义工具执行节点，兼容字典和对象格式的 tool_calls
def custom_tools_execution_node(state: AgentState):
    messages = state['messages']
    last_msg = messages[-1]
    results = []

    # 构建工具映射表
    tool_map = {t.name: t for t in tools}

    # 检查是否有 tool_calls
    tool_calls = getattr(last_msg, 'tool_calls', [])

    if tool_calls:
        print(f"执行工具调用: {len(tool_calls)} 个")
        for call in tool_calls:
            try:
                # 兼容字典和对象访问
                if isinstance(call, dict):
                    tool_name = call.get('name')
                    tool_args = call.get('args', {})
                    call_id = call.get('id')
                else:
                    tool_name = getattr(call, 'name')
                    tool_args = getattr(call, 'args', {})
                    call_id = getattr(call, 'id')

                print(f"调用工具: {tool_name} | 参数: {tool_args}")

                if tool_name in tool_map:
                    tool_instance = tool_map[tool_name]
                    # 执行工具
                    tool_output = tool_instance.invoke(tool_args)

                    # 构造 ToolMessage
                    results.append(ToolMessage(
                        tool_call_id=call_id,
                        name=tool_name,
                        content=str(tool_output)
                    ))
                else:
                    results.append(ToolMessage(
                        tool_call_id=call_id,
                        name=tool_name,
                        content=f"Error: Tool {tool_name} not found."
                    ))
            except Exception as e:
                print(f"工具执行异常: {e}")
                results.append(ToolMessage(
                    tool_call_id=call_id if call_id else "unknown",
                    name=tool_name if tool_name else "unknown",
                    content=f"Error executing tool: {str(e)}"
                ))

    return {"messages": results}

workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", custom_tools_execution_node)
workflow.add_node("reflector", reflector_node)

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", router)
workflow.add_edge("tools", "agent")
workflow.add_conditional_edges("reflector", reflector_router)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)