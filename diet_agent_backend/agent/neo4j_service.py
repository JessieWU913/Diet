import os
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, ConfigurationError
from dotenv import load_dotenv

load_dotenv()

class Neo4jService:
    _instance = None

    @staticmethod
    def _normalize_bolt_uri(uri: str) -> str:
        """将 neo4j 路由 URI 降级为 bolt 直连 URI，适配单机 Neo4j。"""
        if uri.startswith("neo4j://"):
            return "bolt://" + uri[len("neo4j://"):]
        if uri.startswith("neo4j+s://"):
            return "bolt+s://" + uri[len("neo4j+s://"):]
        if uri.startswith("neo4j+ssc://"):
            return "bolt+ssc://" + uri[len("neo4j+ssc://"):]
        return uri

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jService, cls).__new__(cls)
            uri = os.getenv("NEO4J_URI")
            user = os.getenv("NEO4J_USER")
            password = os.getenv("NEO4J_PASSWORD")

            if not uri:
                raise ConfigurationError("NEO4J_URI 未配置，请检查 .env")

            try:
                driver = GraphDatabase.driver(uri, auth=(user, password))
                driver.verify_connectivity()
            except ServiceUnavailable as e:
                if "routing information" not in str(e).lower():
                    raise
                fallback_uri = cls._normalize_bolt_uri(uri)
                print(f"Neo4j 路由连接失败，自动降级为直连: {fallback_uri}")
                driver = GraphDatabase.driver(fallback_uri, auth=(user, password))
                driver.verify_connectivity()

            cls._instance.driver = driver
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

graph_db = Neo4jService()