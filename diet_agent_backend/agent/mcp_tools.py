# agent/mcp_tools.py
from langchain_core.tools import tool
from .neo4j_service import graph_db
from sentence_transformers import SentenceTransformer
from langchain_community.tools import DuckDuckGoSearchResults

embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

ddg_search = DuckDuckGoSearchResults()

@tool
def web_search_tavily(query: str):
    """
    [联网搜索] 当 Neo4j 知识库中没有相关信息（如最新流行饮食法、网红食谱）时使用。
    """
    print(f"正在调用联网搜索 (DuckDuckGo): {query}")
    try:
        # 直接调用DuckDuckGo
        return ddg_search.run(query)
    except Exception as e:
        return f"网络搜索超时或失败: {e}"

@tool
def get_food_nutrition(food_names: list[str]):
    """
    [精细营养查询工具]
    触发条件：当用户询问具体某个菜或食材的“热量”、“脂肪”、“碳水”等营养数据时调用。
    输入：同义词扩展后的列表，如 ["锅塌里脊", "里脊肉"]
    """
    print(f"正在查询营养明细: {food_names}")

    # 同时在Recipe和Ingredient标签中寻找
    cypher = """
    MATCH (n)
    WHERE (n:Recipe OR n:Ingredient)
      AND any(name IN $food_names WHERE n.name CONTAINS name)
    RETURN 
        labels(n)[0] AS type,
        n.name AS name,
        n.calories AS calories,
        n.protein AS protein,
        n.fat AS fat,
        n.carbs AS carbs,
        n.nutrients_raw AS nutrients_detail
    LIMIT 3
    """
    try:
        results = graph_db.query(cypher, {"food_names": food_names})
        if not results:
            return f"抱歉，图谱中暂未收录 {food_names} 的精确营养数据。"
        return f"查询到以下数据：{results}"
    except Exception as e:
        return f"查询出错: {e}"

@tool
def search_recipe_by_ingredients(ingredients: list[str], strict_mode: bool = False):
    """
    [冰箱清库存工具]
    """
    print(f"匹配食材: {ingredients} | 减脂模式: {strict_mode}")

    if strict_mode:
        strict_filter = """
        AND n.calories < 500 
        AND n.fat < 25 
        AND NOT n.name CONTAINS '拔丝' 
        AND NOT n.name CONTAINS '炸'
        """
        # 给蛋白质极高的权重，脂肪扣分
        order_logic = "ORDER BY (n.protein * 5) - (n.fat * 3) - (n.calories * 0.2) DESC"
    else:
        strict_filter = "AND NOT n.name CONTAINS '拔丝'"
        order_logic = """
                      WITH n, \
                           size([ing IN $ingredients WHERE n.name CONTAINS ing]) * 10 +
                          size ([ing IN $ingredients WHERE n.ingredients_raw CONTAINS ing]) AS match_score
                      ORDER BY match_score DESC, n.calories ASC \
                      """

    cypher = f"""
    MATCH (n:Recipe)
    WHERE any(ing IN $ingredients WHERE 
        n.name CONTAINS ing OR 
        n.ingredients_raw CONTAINS ing OR 
        n.steps CONTAINS ing
    )
    {strict_filter}
    {order_logic}
    RETURN 
        n.name AS name, 
        n.calories AS calories, 
        n.protein AS protein,
        n.fat AS fat,
        n.carbs AS carbs,
        n.nutrients_raw AS nutrients
    LIMIT 8
    """
    try:
        results = graph_db.query(cypher, {"ingredients": ingredients})
        if not results:
            return "未能找到符合当前健康标准的菜谱（高脂高热量选项已被系统自动拦截）。"
        return f"找到以下菜谱：{results}"
    except Exception as e:
        return f"查询异常: {e}"

@tool
def check_food_conflicts(food_names: list[str]):
    """
    [饮食禁忌与相宜查询工具]
    触发条件：当用户询问某物“不能和什么一起吃”、“相克”、“相宜”、“搭配禁忌”时【必须】调用。

    【参数生成铁律 - 同义词扩展】：
    必须对口语化食材进行同义词扩展。例如用户问"芹菜"，必须传入 ["芹菜", "水芹菜", "西芹"]。

    输入示例：["芹菜", "西芹"]
    """
    print(f"正在查询食物相克关系(含同义词): {food_names}")

    cypher = """
    MATCH (i1:Ingredient)-[r:CLASH_WITH]-(i2:Ingredient)
    WHERE any(name IN $food_names WHERE i1.name CONTAINS name OR name CONTAINS i1.name)
    RETURN i1.name AS food, i2.name AS conflict_food, r.reason AS reason
    LIMIT 10
    """
    try:
        results = graph_db.query(cypher, {"food_names": food_names})
        if not results:
            return f"图谱中暂无关于 {food_names} 的相克记录，但这不代表绝对安全，请遵医嘱。"
        return f"饮食禁忌记录：{results}"
    except Exception as e:
        print(f"相克查询错误: {e}")
        return "查询图谱时发生错误。"

@tool
def vector_search_recipe(query: str, strict_mode: bool = False, exclude_ingredients: list[str] = None):
    """
    [模糊需求推荐工具]
    触发条件：用户提出模糊需求（如“想吃点中式的”、“推荐晚餐”）时调用。

    【参数提取铁律】：
    1. query: 只能包含正向需求（如 "中式晚餐"、"清淡"）。绝不能把“不吃XXX”写进 query 里，否则会导致搜索完全失效！
    2. exclude_ingredients: 提取用户明确表示不吃、忌口或过敏的食材，放入此列表（如 ["鱼", "海鲜", "香菜"]）。
    """
    print(f"向量搜索 | 正向词: {query} | 忌口: {exclude_ingredients} | 减脂: {strict_mode}")

    try:
        query_vector = embedding_model.encode(query).tolist()

        extra_filter = """
        AND node.calories < 500 
        AND node.fat < 25
        AND NOT node.name CONTAINS '炸'
        """ if strict_mode else ""

        if exclude_ingredients:
            extra_filter += """ 
            AND none(exc IN $exclude_ingredients WHERE 
                node.name CONTAINS exc OR 
                (node.ingredients_raw IS NOT NULL AND node.ingredients_raw CONTAINS exc)
            ) 
            """

        params = {
            "embedding": query_vector,
            "exclude_ingredients": exclude_ingredients if exclude_ingredients else []
        }

        cypher = f"""
        CALL db.index.vector.queryNodes('recipe_embedding_index', 15, $embedding)
        YIELD node, score
        WHERE score > 0.25
        {extra_filter}
        RETURN 
            node.name AS name, 
            node.calories AS calories, 
            node.protein AS protein,
            node.nutrients_raw AS nutrients,
            (score * 100) + (COALESCE(node.protein, 0) * 0.5) AS final_score
        ORDER BY final_score DESC
        LIMIT 8
        """
        results = graph_db.query(cypher, params)
        if not results:
            return "数据库中未能找到符合口味且避开忌口的菜谱。"
        return f"语义搜索结果：{results}"
    except Exception as e:
        print(f"向量搜索异常: {e}")
        return f"搜索出错: {e}"