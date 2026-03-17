import json
from neo4j import GraphDatabase

# ================= 配置区域 =================
# 修改为你的 Neo4j 账号密码
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "Wjx20041026")

RECIPE_FILE = 'recipes_final.json'
INGREDIENT_FILE = 'ingredients_final.json'


# ================= 核心代码 =================

class DietGraphImporter:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def create_constraints(self):
        """创建唯一性约束，提高查询速度"""
        print("正在创建索引和约束...")
        with self.driver.session() as session:
            # 针对 Neo4j 5.x 的语法 (如果是 4.x 请用 CREATE CONSTRAINT ON ...)
            queries = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.name IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Recipe) REQUIRE r.name IS UNIQUE",
                "CREATE INDEX IF NOT EXISTS FOR (i:Ingredient) ON (i.category)"
            ]
            for q in queries:
                session.run(q)

    def clear_database(self):
        """危险操作：清空数据库"""
        print("⚠️ 正在清空数据库...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def import_ingredients(self):
        print("正在导入食材...")
        with open(INGREDIENT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        query = """
        MERGE (i:Ingredient {name: $name})
        SET i.category = $category,
            i.calories = $cal,
            i.protein = $prot,
            i.fat = $fat,
            i.carbs = $carb,
            i.fiber = $fiber,
            i.unit_info = $unit_info
        """

        with self.driver.session() as session:
            count = 0
            batch = []
            for item in data:
                # 提取关键营养素 (扁平化处理)
                nutrients = item.get("nutrients", {})
                props = {
                    "name": item["name"],
                    "category": item.get("category", "其他"),
                    "cal": nutrients.get("热量", {}).get("value", 0),
                    "prot": nutrients.get("蛋白质", {}).get("value", 0),
                    "fat": nutrients.get("脂肪", {}).get("value", 0),
                    "carb": nutrients.get("碳水化合物", {}).get("value", 0),
                    "fiber": nutrients.get("纤维素", {}).get("value", 0),
                    # 把单位换算信息存为字符串，方便 Agent 读取
                    "unit_info": json.dumps(item.get("unit_info", []), ensure_ascii=False)
                }

                # 简单执行
                session.run(query, **props)
                count += 1
                if count % 100 == 0:
                    print(f"已导入 {count} 个食材...")
        print(f"✅ 食材导入完成，共 {count} 个。")

    def import_recipes(self):
        print("正在导入食谱及关系...")
        with open(RECIPE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. 创建食谱节点
        query_recipe = """
        MERGE (r:Recipe {name: $name})
        SET r.category = $category,
            r.image = $image,
            r.calories = $calories,
            r.steps = $steps
        """

        # 2. 建立关系 (Recipe)-[CONTAINS]->(Ingredient)
        query_relation = """
        MATCH (r:Recipe {name: $r_name})
        MATCH (i:Ingredient {name: $i_name})
        MERGE (r)-[rel:CONTAINS]->(i)
        SET rel.weight_g = $weight,
            rel.raw_text = $raw_text
        """

        with self.driver.session() as session:
            count = 0
            for item in data:
                # A. 创建食谱
                # 提取步骤为字符串，方便存储
                steps_str = "\n".join(item.get("steps", []))
                # 提取食谱自带的总热量（如果有）
                nutrients = item.get("nutrients", {})
                total_cal = nutrients.get("热量", {}).get("value", 0)

                session.run(query_recipe,
                            name=item["name"],
                            category=item.get("category"),
                            image=item.get("image"),
                            calories=total_cal,
                            steps=steps_str)

                # B. 建立配料关系
                for ing in item.get("ingredients", []):
                    if ing.get("is_linked"):  # 只导入成功匹配的
                        session.run(query_relation,
                                    r_name=item["name"],
                                    i_name=ing["ingredient_name"],
                                    weight=ing["weight_g"],
                                    raw_text=ing["raw_text"])

                count += 1
                if count % 50 == 0:
                    print(f"已导入 {count} 个食谱...")
        print(f"✅ 食谱导入完成，共 {count} 个。")


if __name__ == "__main__":
    importer = DietGraphImporter(URI, AUTH)
    try:
        # 1. (可选) 清空旧数据，防止重复
        # importer.clear_database()

        # 2. 创建约束
        importer.create_constraints()

        # 3. 导入数据
        importer.import_ingredients()
        importer.import_recipes()

        print("\n🎉 全部导入成功！去 Neo4j Browser 看看吧！")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
    finally:
        importer.close()