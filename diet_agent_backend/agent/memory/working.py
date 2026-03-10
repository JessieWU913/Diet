from langchain_core.messages import ToolMessage, AIMessage, SystemMessage

class WorkingMemory:
    @staticmethod
    def compress_messages(messages, max_history=6):
        if not messages:
            return []

        compressed = list(messages)
        if len(compressed) > max_history:
            compressed = compressed[-max_history:]

        while compressed:
            first = compressed[0]
            if isinstance(first, (ToolMessage, SystemMessage)) or (
                    isinstance(first, AIMessage) and getattr(first, 'tool_calls', None)):
                compressed.pop(0)
            else:
                break

        return compressed