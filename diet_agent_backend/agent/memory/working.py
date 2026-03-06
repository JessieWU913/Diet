class WorkingMemory:
    """
    工作记忆：管理多轮对话的上下文窗口与 Token 压缩
    """

    @staticmethod
    def compress_messages(messages, max_history=6):
        """
        滑动窗口机制：保留系统设定和最近的 max_history 条消息
        （注意：Langchain 的 messages 列表中，最后一条通常是当前问题）
        """
        if not messages or len(messages) <= max_history:
            return messages

        # 截取最后 max_history 条消息，确保 Agent 只记住“短期上下文”
        # 这里预留了扩展空间，未来如果换成用 LLM 生成摘要，逻辑就可以写在这里
        compressed = messages[-max_history:]

        return compressed