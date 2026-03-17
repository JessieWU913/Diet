import json
from neo4j import GraphDatabase

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "Wjx20041026")
RECIPE_FILE = 'bohee_food_all.json'  # 用最原始的那个文件，里面有 cooking_type_detail

driver = GraphDatabase.driver(URI, auth=AUTH)


def patch_advice():
    print("正在补全健康建议数据...")
    with open(RECIPE_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with driver.session() as session:
        count = 0
        for item in data:
            basic = item.get("basic_info", {})
            name = basic.get("food_name")
            advice = basic.get("cooking_type_detail", "")

            # 如果建议里包含负面词汇，标记为不推荐
            is_unhealthy = False
            if "不宜食用" in advice or "少吃" in advice:
                is_unhealthy = True

            if name and advice:
                session.run("""
                    MATCH (r:Recipe {name: $name})
                    SET r.health_advice = $advice,
                        r.is_unhealthy_for_diet = $is_unhealthy
                """, name=name, advice=advice, is_unhealthy=is_unhealthy)
                count += 1
                if count % 100 == 0: print(f"已更新 {count} 条...")
    print("✅ 补全完成！")


if __name__ == "__main__":
    patch_advice()