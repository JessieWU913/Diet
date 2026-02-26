# agent/graph.py
import re
import json
import os
from typing import TypedDict, List, Literal

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
    temperature=0.1,  # 保持极低温度，保证工具调用的稳定性
    frequency_penalty=1.1
)

# 绑定四大工具
tools = [vector_search_recipe, get_food_nutrition, check_food_conflicts, search_recipe_by_ingredients]
llm_with_tools = llm.bind_tools(tools)


# 核心节点
def agent_node(state: AgentState):
    mode = state.get('user_mode', 'standard')
    messages = state['messages']

    # 极简且严厉的铁律指令
    system_prompt = """你是连接了Neo4j知识图谱的专业膳食Agent。
    【最高纪律】：绝不自己编造任何数据，必须且只能调用以下工具：
    1. 查具体食物的热量/卡路里/营养 -> 调用 `get_food_nutrition`
    2. 查食物的相克/禁忌/不能同食 -> 调用 `check_food_conflicts`
    3. 给出已有食材，问能做什么菜 -> 调用 `search_recipe_by_ingredients`
    4. 提出模糊需求推荐菜谱/食谱 -> 调用 `vector_search_recipe`

    如果工具返回结果为“没有查到”，直接如实回答用户“知识图谱中暂无记录”。
    """

    if mode == 'weight_loss':
        system_prompt += "\n当前为严格减脂模式，调用 vector_search_recipe 时必须传入 strict_mode=True。"

    # 注入 System Prompt
    if isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=system_prompt)
    else:
        messages.insert(0, SystemMessage(content=system_prompt))

    # 调用大模型
    response = llm_with_tools.invoke(messages)

    # 作用：捕捉 DeepSeek 漏出的 `<｜tool...｜>` 乱码并强行纠正为标准 ToolCall
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
                    # 使用正则贪婪匹配抓取紧跟其后的 JSON 参数
                    match = re.search(f"{tool_name}.*?({{.*?}})", content, re.DOTALL)
                    if match:
                        args = json.loads(match.group(1))
                        print(f"强制执行工具: {tool_name} | 参数: {args}")

                        # 偷天换日，用合法的 AIMessage 替换掉旧的
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

    # 只在减脂模式下进行反思审查，且最多重试2次
    if mode != 'weight_loss' or count >= 2:
        return {"reflection_count": count}

    last_msg = messages[-1]

    # 如果是 Agent 生成的最终文本（而非工具调用指令）
    if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
        content = last_msg.content

        # 严禁推荐糖油混合物或高油脂食物
        unhealthy_keywords = ["糖溜", "拔丝", "油炸", "红烧", "肥肉", "腊肉", "香肠"]
        found_problems = [k for k in unhealthy_keywords if k in content]

        if found_problems:
            print(f"⚠️ 触发反思：检测到违禁词汇 {found_problems}，打回重做！")
            correction_msg = HumanMessage(
                content=f"系统提示：你刚才的推荐中包含了 {found_problems}，严重违反减脂规则。请立刻撤回，并重新调用工具搜索低脂低热量的食材进行替代。")
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
    # 如果 reflector 添加了新的纠正意见 (HumanMessage)，就跳回 agent 重新生成
    if isinstance(state['messages'][-1], HumanMessage):
        return "agent"
    return "__end__"


# 构建图结构

workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(tools))
workflow.add_node("reflector", reflector_node)

# 设置起点
workflow.set_entry_point("agent")

# 添加连线规则
workflow.add_conditional_edges("agent", router)
workflow.add_edge("tools", "agent")  # 工具执行完，永远返回给 Agent 思考
workflow.add_conditional_edges("reflector", reflector_router)

# 挂载记忆存储器并编译
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)