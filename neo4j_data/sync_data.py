import json
from neo4j import GraphDatabase

# ================= 配置区域 =================
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "Wjx20041026")

RECIPE_FILE = 'recipes_final.json'
INGREDIENT_FILE = 'ingredients_final.json'


class DietGraphImporter:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def create_constraints(self):
        print("正在创建索引和约束...")
        with self.driver.session() as session:
            queries = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.name IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Recipe) REQUIRE r.name IS UNIQUE",
            ]
            for q in queries:
                session.run(q)

    def import_recipes(self):
        print("正在进行全量食谱导入（补全食材与营养属性）...")
        with open(RECIPE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 🌟 升级后的 Cypher 语句
        # 我们把 nutrients 和 ingredients 完整存入，同时把热量单独提取出来方便过滤
        query_recipe = """
        MERGE (r:Recipe {name: $name})
        SET r.category = $category,
            r.image = $image,
            r.calories = toFloat($calories),
            r.protein = toFloat($protein),
            r.fat = toFloat($fat),
            r.carbs = toFloat($carbs),
            r.steps = $steps,
            r.ingredients_raw = $ingredients_raw,  // 存储完整的食材 JSON 字符串
            r.nutrients_raw = $nutrients_raw       // 存储完整的营养 JSON 字符串
        """

        query_relation = """
        MATCH (r:Recipe {name: $r_name})
        MERGE (i:Ingredient {name: $i_name})
        MERGE (r)-[rel:CONTAINS]->(i)
        SET rel.weight_g = $weight,
            rel.raw_text = $raw_text
        """

        with self.driver.session() as session:
            count = 0
            for item in data:
                nutrients = item.get("nutrients", {})

                # 1. 提取核心数值（用于后续的 > 或 < 过滤查询）
                calories = nutrients.get("热量", {}).get("value", 0)
                protein = nutrients.get("蛋白质", {}).get("value", 0)
                fat = nutrients.get("脂肪", {}).get("value", 0)
                carbs = nutrients.get("碳水化合物", {}).get("value", 0)

                # 2. 序列化完整对象（用于 Agent 的“全知视角”读取）
                # ensure_ascii=False 保证存入的是中文而不是 \u4f60
                ingredients_json = json.dumps(item.get("ingredients", []), ensure_ascii=False)
                nutrients_json = json.dumps(nutrients, ensure_ascii=False)
                steps_str = "\n".join(item.get("steps", []))

                # 3. 执行写入
                session.run(query_recipe,
                            name=item["name"],
                            category=item.get("category"),
                            image=item.get("image"),
                            calories=calories,
                            protein=protein,
                            fat=fat,
                            carbs=carbs,
                            steps=steps_str,
                            ingredients_raw=ingredients_json,
                            nutrients_raw=nutrients_json)

                # 4. 建立配料连线 (保持之前的逻辑，方便可视化)
                for ing in item.get("ingredients", []):
                    # 即使没有 is_linked，我们也建议创建 Ingredient 节点以丰富图谱密度
                    # 如果你只想要匹配成功的，就保留 if ing.get("is_linked"):
                    session.run(query_relation,
                                r_name=item["name"],
                                i_name=ing["ingredient_name"],
                                weight=ing.get("weight_g", 0),
                                raw_text=ing.get("raw_text", ""))

                count += 1
                if count % 50 == 0:
                    print(f"已同步 {count} 个完整食谱数据...")
        print(f"✅ 全量导入完成，共 {count} 个。")


if __name__ == "__main__":
    importer = DietGraphImporter(URI, AUTH)
    try:
        importer.create_constraints()
        # 建议先运行一次食材导入，再运行这个食谱导入
        importer.import_recipes()
    finally:
        importer.close()