# agent/tools.py
from langchain_core.tools import tool
from .neo4j_service import graph_db


@tool
def search_recipe_by_ingredients(ingredients: list[str]):
    """
    根据用户拥有的食材查询推荐食谱。
    输入示例: ['猪肉', '青椒']
    """
    # 并按匹配度排序
    query = """
    MATCH (r:Recipe)-[:CONTAINS]->(i:Ingredient)
    WHERE i.name IN $ingredients
    WITH r, count(i) as match_count, collect(i.name) as matched_ingredients
    RETURN r.name as recipe, r.calories as calories, matched_ingredients
    ORDER BY match_count DESC
    LIMIT 5
    """
    return graph_db.query(query, {"ingredients": ingredients})


@tool
def check_food_conflicts(foods: list[str]):
    """
    检查一组食物之间是否存在相克（互斥）关系。
    输入示例: ['菠菜', '豆腐', '蜂蜜']
    """
    query = """
    MATCH (a:Ingredient)-[r:CLASH_WITH]->(b:Ingredient)
    WHERE a.name IN $foods AND b.name IN $foods
    RETURN a.name as food1, b.name as food2, r.desc as reason
    """
    results = graph_db.query(query, {"foods": foods})
    if not results:
        return "未发现已知冲突。"
    return results


@tool
def calculate_recipe_calories(recipe_name: str):
    """
    查询某道菜的具体热量构成。
    """
    query = """
    MATCH (r:Recipe {name: $name})-[rel:CONTAINS]->(i:Ingredient)
    RETURN i.name as ingredient, rel.weight_g as weight, 
           (rel.weight_g * i.calories / 100) as cal
    """
    data = graph_db.query(query, {"name": recipe_name})
    if not data:
        return "未找到该食谱。"

    total_cal = sum([item['cal'] for item in data])
    return f"食谱【{recipe_name}】的预估总热量为: {total_cal:.1f} 大卡。明细: {data}"