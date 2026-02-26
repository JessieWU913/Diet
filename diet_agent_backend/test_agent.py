# # test_agent.py
# import os
# import django
#
# # 初始化 Django 环境 (因为用到了 neo4j_service)
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diet_agent_backend.settings')
# django.setup()
#
# from langchain_core.messages import HumanMessage
# from agent.graph import app
#
#
# def test_chat():
#     print("🤖 膳食智能体启动... (输入 'q' 退出)")
#     while True:
#         user_input = input("\n用户: ")
#         if user_input.lower() == 'q':
#             break
#
#         # 构造输入
#         inputs = {"messages": [HumanMessage(content=user_input)]}
#
#         # 执行图
#         result = app.invoke(inputs)
#
#         # 获取最终回复
#         final_msg = result['messages'][-1].content
#         print(f"Agent: {final_msg}")
#
#
# if __name__ == "__main__":
#     test_chat()


import os
import django
import time
import threading

# 初始化 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diet_agent_backend.settings')
django.setup()

from langchain_core.messages import HumanMessage
from agent.graph import app


def invoke_agent(content, is_heartbeat=False):
    """封装调用逻辑"""
    try:
        inputs = {"messages": [HumanMessage(content=content)]}
        result = app.invoke(inputs)
        final_msg = result['messages'][-1].content

        prefix = "[心跳保活]" if is_heartbeat else "Agent"
        print(f"\n{prefix}: {final_msg}")

        if is_heartbeat:
            print("用户: ", end="", flush=True)  # 保持输入提示符不乱
    except Exception as e:
        print(f"\n❌ 调用失败: {e}")


def heartbeat_loop():
    """每120秒自动询问一次"""
    while True:
        time.sleep(30)
        invoke_agent("我的忌口是芹菜和香菜，给我推荐减肥期间适合吃的东西？", is_heartbeat=True)


def test_chat():
    print("🤖 膳食智能体启动... (每2分钟自动保活, 输入 'q' 退出)")

    # 启动后台心跳线程
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()

    while True:
        user_input = input("用户: ")
        if user_input.lower() == 'q':
            break
        if not user_input.strip():
            continue

        invoke_agent(user_input)


if __name__ == "__main__":
    test_chat()