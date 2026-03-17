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
from .context import ContextBuilder

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_mode: str
    reflection_count: int
    user_profile: dict
    user_id: str

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

tools = [vector_search_recipe, get_food_nutrition, check_food_conflicts, search_recipe_by_ingredients]
openai_fns = [convert_to_openai_function(t) for t in tools]
llm_with_tools = llm.bind(functions=openai_fns)


def agent_node(state: AgentState):
    mode = state.get('user_mode', 'standard')
    profile = state.get('user_profile', {})
    user_id = state.get('user_id')

    builder = ContextBuilder(
        user_id=user_id,
        user_mode=mode,
        profile=profile,
        max_tokens=2048,
        max_history=6,
    )
    system_prompt, compressed_messages = builder.build(state['messages'])
    messages = list(compressed_messages)

    if messages and isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=system_prompt)
    else:
        messages.insert(0, SystemMessage(content=system_prompt))

    response = llm_with_tools.invoke(messages)

    if not response.tool_calls:
        content = response.content
        target_tools = ["get_food_nutrition", "check_food_conflicts", "search_recipe_by_ingredients", "vector_search_recipe"]
        for tool_name in target_tools:
            if tool_name in content:
                print(f"拦截到 Gitee 漏出的工具标记: {tool_name}")
                try:
                    match = re.search(tool_name + r".*?(\{.*?\})", content, re.DOTALL)
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


def router(state: AgentState) -> Literal["tools", "reflector"]:
    last_msg = state['messages'][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        return "tools"
    return "reflector"

def reflector_router(state: AgentState) -> Literal["agent", "__end__"]:
    if isinstance(state['messages'][-1], HumanMessage):
        return "agent"
    return "__end__"

def custom_tools_execution_node(state: AgentState):
    messages = state['messages']
    last_msg = messages[-1]
    results = []

    tool_map = {t.name: t for t in tools}

    tool_calls = getattr(last_msg, 'tool_calls', [])

    if tool_calls:
        print(f"执行工具调用: {len(tool_calls)} 个")
        for call in tool_calls:
            try:
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
                    tool_output = tool_instance.invoke(tool_args)

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