# agent/neo4j_service.py
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

class Neo4jService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jService, cls).__new__(cls)
            uri = os.getenv("NEO4J_URI")
            user = os.getenv("NEO4J_USER")
            password = os.getenv("NEO4J_PASSWORD")
            cls._instance.driver = GraphDatabase.driver(uri, auth=(user, password))
        return cls._instance

    def close(self):
        self.driver.close()

    def query(self, cypher_query, params=None):
        """执行 Cypher 查询并返回列表结果"""
        if params is None:
            params = {}
        with self.driver.session() as session:
            result = session.run(cypher_query, params)
            return [record.data() for record in result]

# 实例化一个全局对象供其他模块调用
graph_db = Neo4jService()