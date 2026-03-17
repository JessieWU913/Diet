import json
import re
from neo4j import GraphDatabase
import difflib

# ================= 配置区域 =================
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "Wjx20041026")  # 记得改密码
EXISTING_INGREDIENTS_FILE = 'ingredients_final.json'
RELATION_FILE = 'food_relations.json'

# 依然保留字典，优先解决常见的别名问题
SYNONYM_DICT = {
    "小麦粉(标准粉)": "小麦粉(标准粉)",
    "小麦粉": "小麦粉(标准粉)",
    "西红柿": "番茄",
    "地瓜": "红薯",
    "马铃薯": "土豆",
    "洋芋": "土豆",
    "大蒜": "蒜",
    "姜": "生姜",
    "鲜牛奶": "牛奶",
    "纯牛奶": "牛奶",
    "瘦肉": "猪肉(瘦)",
    "精肉": "猪肉(瘦)",
    "蔬菜": "蔬菜",  # 这种泛化概念，直接保留原名即可
    "海鲜": "海鲜"
}


# ================= 核心代码 =================

def clean_name_for_match(name):
    if name in SYNONYM_DICT: return SYNONYM_DICT[name]
    name_clean = re.sub(r"\(.*?\)", "", name).strip()
    name_clean = re.sub(r"（.*?）", "", name_clean).strip()
    return name_clean


class RelationImporter:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.valid_names = set()

    def close(self):
        self.driver.close()

    def load_existing_ingredients(self):
        print("正在加载已入库的食材名单...")
        try:
            with open(EXISTING_INGREDIENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    self.valid_names.add(item['name'])
            print(f"✅ 已加载 {len(self.valid_names)} 个已知食材。")
        except:
            print("❌ 警告: 找不到基础食材文件，所有关系中的食材都将作为新节点创建。")

    def find_or_create_name(self, raw_name):
        """
        核心修改：
        1. 先尝试匹配已有食材。
        2. 如果匹配不到，直接返回清洗后的名字（准备创建新节点）。
        返回: (最终名字, 是否是新节点)
        """
        # 1. 尝试直接匹配
        if raw_name in self.valid_names:
            return raw_name, False

        # 2. 尝试字典和清洗
        cleaned = clean_name_for_match(raw_name)
        if cleaned in self.valid_names:
            return cleaned, False

        # 3. 尝试模糊匹配
        matches = difflib.get_close_matches(cleaned, self.valid_names, n=1, cutoff=0.85)
        if matches:
            return matches[0], False

        # 4. 彻底匹配失败 -> 返回清洗后的名字 (标记为需要创建)
        return cleaned, True

    def import_data(self):
        print("正在解析并导入关系数据 (开启自动补全模式)...")
        with open(RELATION_FILE, 'r', encoding='utf-8') as f:
            full_data = json.load(f)

        # 修改后的 Cypher：使用 MERGE 自动创建不存在的节点
        # 注意：新创建的节点会打上 :Ingredient 和 :MissingInfo 两个标签
        queries = {
            "互斥": """
                MERGE (a:Ingredient {name: $src})
                ON CREATE SET a.source = 'relation_db', a.missing_info = true
                MERGE (b:Ingredient {name: $tgt})
                ON CREATE SET b.source = 'relation_db', b.missing_info = true
                MERGE (a)-[r:CLASH_WITH]->(b) 
                SET r.desc = $desc
            """,
            "互补": """
                MERGE (a:Ingredient {name: $src})
                ON CREATE SET a.source = 'relation_db', a.missing_info = true
                MERGE (b:Ingredient {name: $tgt})
                ON CREATE SET b.source = 'relation_db', b.missing_info = true
                MERGE (a)-[r:COMPLEMENTS]->(b) 
                SET r.desc = $desc
            """,
            "重叠": """
                MERGE (a:Ingredient {name: $src})
                ON CREATE SET a.source = 'relation_db', a.missing_info = true
                MERGE (b:Ingredient {name: $tgt})
                ON CREATE SET b.source = 'relation_db', b.missing_info = true
                MERGE (a)-[r:SIMILAR_TO]->(b) 
                SET r.desc = $desc
            """
        }

        stats = {"matched": 0, "created_new": 0}

        with self.driver.session() as session:
            for category, sub_dict in full_data.items():
                if not isinstance(sub_dict, dict): continue
                for sub_cat, item_list in sub_dict.items():
                    if not isinstance(item_list, list): continue
                    for item in item_list:
                        src_raw = item.get("食物名称")

                        # 获取源头名字 (如果是新的，cypher里的 MERGE 会自动创建)
                        src_final, src_is_new = self.find_or_create_name(src_raw)

                        relations = item.get("食物关系", {})
                        for rel_type, targets in relations.items():
                            if rel_type not in queries: continue

                            for target in targets:
                                tgt_raw = target.get("食物名称")
                                desc = target.get("描述", "")

                                # 获取目标名字
                                tgt_final, tgt_is_new = self.find_or_create_name(tgt_raw)

                                # 执行写入
                                session.run(queries[rel_type], src=src_final, tgt=tgt_final, desc=desc)

                                if src_is_new or tgt_is_new:
                                    stats["created_new"] += 1
                                else:
                                    stats["matched"] += 1

        print("\n" + "=" * 30)
        print(f"🎉 导入完成！")
        print(f"🔗 纯已有节点关系: {stats['matched']} 条")
        print(f"🆕 包含新节点的关系: {stats['created_new']} 条")
        print(f"   (新节点已标记为 missing_info=true，方便后续补充)")
        print("=" * 30)


if __name__ == "__main__":
    importer = RelationImporter(URI, AUTH)
    try:
        importer.load_existing_ingredients()
        importer.import_data()
    except Exception as e:
        print(f"❌ 发生错误: {e}")
    finally:
        importer.close()