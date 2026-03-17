import os
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

print("正在加载 Embedding 模型...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
driver = GraphDatabase.driver(URI, auth=AUTH)


def generate_embedding(text):
    if not text: return None
    return model.encode(text).tolist()


def create_vector_index(tx):
    print("正在创建 Ingredient 向量索引...")

    tx.run("""
    CREATE VECTOR INDEX ingredient_embedding_index IF NOT EXISTS
    FOR (i:Ingredient) ON (i.embedding)
    OPTIONS {indexConfig: {
     `vector.dimensions`: 384,
     `vector.similarity_function`: 'cosine'
    }}
    """)

    print("正在创建 Recipe 向量索引...")
    tx.run("""
    CREATE VECTOR INDEX recipe_embedding_index IF NOT EXISTS
    FOR (r:Recipe) ON (r.embedding)
    OPTIONS {indexConfig: {
     `vector.dimensions`: 384,
     `vector.similarity_function`: 'cosine'
    }}
    """)


def update_embeddings(tx):
    print("正在计算食材向量...")
    result = tx.run("MATCH (i:Ingredient) WHERE i.embedding IS NULL RETURN i.name AS name")
    for record in result:
        name = record["name"]
        vector = generate_embedding(f"食材名称: {name}")
        if vector:
            tx.run("MATCH (i:Ingredient {name: $name}) SET i.embedding = $vector",
                   name=name, vector=vector)

    print("正在计算食谱向量...")
    result = tx.run("MATCH (r:Recipe) WHERE r.embedding IS NULL RETURN r.name AS name, r.steps AS steps")
    for record in result:
        name = record["name"]
        steps = str(record["steps"])[:200]
        vector = generate_embedding(f"食谱: {name}, 做法: {steps}")
        if vector:
            tx.run("MATCH (r:Recipe {name: $name}) SET r.embedding = $vector",
                   name=name, vector=vector)


if __name__ == "__main__":
    with driver.session() as session:
        session.execute_write(create_vector_index)
        session.execute_write(update_embeddings)

    print("向量化完成！GraphRAG 基础已就绪。")
    driver.close()