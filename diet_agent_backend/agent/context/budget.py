"""
TokenBudget — token 估算与预算守卫

中文约 1.5 token/字，英文约 1.3 token/word。
采用保守估算策略，确保不超出模型上下文窗口。
"""


class TokenBudget:
    """token 预算管理器"""

    def __init__(self, total_limit: int = 2048):
        self.total_limit = total_limit
        # 各区块预算分配 (百分比)
        self.allocations = {
            "role":     0.10,   # [角色与策略] 稳定层 ~200 tokens
            "task":     0.05,   # [任务] 当前轮用户消息
            "state":    0.20,   # [状态] 用户画像 + 减脂指标
            "evidence": 0.25,   # [证据] 工具返回 + 知识图谱
            "context":  0.30,   # [上下文] 对话历史
            "output":   0.10,   # [输出] 格式要求
        }

    def estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数：中文字数 × 1.5 + 英文词数 × 1.3"""
        if not text:
            return 0
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        non_chinese = len(text) - chinese_chars
        # 英文部分按字符 / 4 近似 word count
        return int(chinese_chars * 1.5 + non_chinese * 0.4)

    def get_budget(self, section: str) -> int:
        """获取某区块的 token 预算"""
        ratio = self.allocations.get(section, 0.1)
        return int(self.total_limit * ratio)

    def truncate_to_budget(self, text: str, section: str) -> str:
        """将文本截断至预算范围内，从末尾保留（优先保留最新内容）"""
        budget = self.get_budget(section)
        current = self.estimate_tokens(text)
        if current <= budget:
            return text

        # 按比例截断，保留后半部分（最新的内容更重要）
        ratio = budget / max(current, 1)
        keep_chars = int(len(text) * ratio)
        return "...(已压缩)\n" + text[-keep_chars:]

    def within_budget(self, text: str, section: str) -> bool:
        """检查文本是否在预算内"""
        return self.estimate_tokens(text) <= self.get_budget(section)

    def report(self, sections: dict[str, str]) -> dict:
        """返回各区块的实际 token 使用 vs 预算"""
        report = {}
        total_used = 0
        for name, text in sections.items():
            used = self.estimate_tokens(text)
            budget = self.get_budget(name)
            total_used += used
            report[name] = {"used": used, "budget": budget, "over": used > budget}
        report["_total"] = {"used": total_used, "limit": self.total_limit}
        return report
