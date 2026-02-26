# agent/mcp_tools.py
from langchain_core.tools import tool
from .neo4j_service import graph_db
from sentence_transformers import SentenceTransformer
from langchain_community.tools import DuckDuckGoSearchResults

embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')


@tool
def vector_search_recipe(query: str, strict_mode: bool = False):
    """
    [语义搜索] 查找食谱。
    Args:
        query: 用户的自然语言描述
        strict_mode: 是否开启严格健康过滤。True=过滤高糖高油及高热量菜品。
    """
    print(f"🕵️ 向量搜索 | 关键词: {query} | 严格模式: {strict_mode}")
    query_vector = embedding_model.encode(query).tolist()

    # 动态构建过滤条件
    if strict_mode:
        # 1. 过滤掉明确标记为不健康的
        # 2. 强制过滤掉热量 > 400 大卡的 (防止漏网之鱼)
        # 3. 过滤掉烹饪方式里含“糖”、“油炸”的
        filter_clause = """
        AND (node.is_unhealthy_for_diet = false OR node.is_unhealthy_for_diet IS NULL)
        AND toFloat(node.calories) < 400
        AND NOT node.health_advice CONTAINS '糖'
        AND NOT node.health_advice CONTAINS '油炸'
        """
    else:
        filter_clause = ""

    cypher = f"""
    CALL db.index.vector.queryNodes('recipe_embedding_index', 15, $embedding)
    YIELD node, score
    WHERE score > 0.4 
    {filter_clause}
    RETURN node.name AS name, node.calories AS calories, node.health_advice AS advice, score
    LIMIT 3
    """

    try:
        results = graph_db.query(cypher, {"embedding": query_vector})
        if not results:
            return "减脂模式下未找到符合严格标准的食谱，数据库中的相关菜品热量过高。"
        return f"搜索结果：{results}"
    except Exception as e:
        return f"搜索出错: {e}"


ddg_search = DuckDuckGoSearchResults()

@tool
def web_search_tavily(query: str):
    """
    [联网搜索] 当 Neo4j 知识库中没有相关信息（如最新流行饮食法、网红食谱）时使用。
    """
    print(f"正在调用联网搜索 (DuckDuckGo): {query}")
    try:
        # 这里直接调用 DuckDuckGo
        return ddg_search.run(query)
    except Exception as e:
        return f"网络搜索超时或失败: {e}"



@tool
def search_recipe_by_ingredients(ingredients: list[str]):
    """
    [冰箱清库存工具]
    触发条件：当用户说“我有XXX和XXX，能做什么菜”、“用XXX做菜”时【必须】调用。
    功能：根据用户提供的食材列表，在知识图谱中精确匹配包含这些食材的食谱。
    输入：食材名称列表，例如 ["白菜", "生姜"]
    """
    print(f"正在根据食材查询食谱: {ingredients}")
    # 使用 Cypher 查找包含这些食材的食谱，按匹配程度排序
    cypher = """
    MATCH (r:Recipe)-[:HAS_INGREDIENT]->(i:Ingredient)
    WHERE any(ing IN $ingredients WHERE i.name CONTAINS ing)
    WITH r, collect(i.name) AS matched_ings, count(i) AS match_count
    ORDER BY match_count DESC
    RETURN r.name AS name, r.calories AS calories, matched_ings
    LIMIT 5
    """
    results = graph_db.query(cypher, {"ingredients": ingredients})
    if not results:
        return "数据库中没有找到同时包含这些食材的菜谱，请尝试更换食材。"
    return f"根据食材为您找到以下菜谱：{results}"

@tool
def get_food_nutrition(food_name: str):
    """
    [精准数据查询工具]
    触发条件：当用户具体询问某个菜品或食材的“热量”、“卡路里”、“GI值”、“营养成分”时【绝对必须】调用此工具！
    警告：严禁大模型自己编造或猜测热量数据，必须以此工具返回的数据为准！
    输入：食物名称，例如 "白灼菜心", "白菜"
    """
    print(f"正在精确查询营养数据: {food_name}")
    cypher = """
    MATCH (n) 
    WHERE (n:Recipe OR n:Ingredient) AND n.name CONTAINS $food_name
    RETURN labels(n)[0] AS type, n.name AS name, n.calories AS calories, n.gi_level AS gi_level
    LIMIT 3
    """
    results = graph_db.query(cypher, {"food_name": food_name})
    if not results:
        return f"数据库中未找到关于 {food_name} 的精确热量数据。"
    return f"数据库真实营养数据：{results}"

@tool
def check_food_conflicts(food_name: str):
    """
    [饮食禁忌与相宜查询工具]
    触发条件：当用户询问某物“不能和什么一起吃”、“相克”、“相宜”、“搭配禁忌”时【必须】调用。
    输入：单一食材名称，例如 "芹菜"
    """
    print(f"正在查询食物相克/相宜关系: {food_name}")
    # 假设你的图谱中有 [:CLASH_WITH] 或类似的相克关系
    cypher = """
    MATCH (i1:Ingredient)-[r:CLASH_WITH]-(i2:Ingredient)
    WHERE i1.name CONTAINS $food_name
    RETURN i1.name AS food, i2.name AS conflict_food, r.reason AS reason
    """
    results = graph_db.query(cypher, {"food_name": food_name})
    if not results:
        return f"图谱中暂无关于 {food_name} 的相克记录，但这不代表绝对安全，请遵医嘱。"
    return f"饮食禁忌记录：{results}"