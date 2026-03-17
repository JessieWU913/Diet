import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from neo4j import Driver


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _chunked(items: List[dict], size: int) -> Iterable[List[dict]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "neo4j_data"


def _data_fingerprint(paths: List[Path]) -> str:
    parts = []
    for p in paths:
        stat = p.stat()
        parts.append(f"{p.name}:{stat.st_size}:{int(stat.st_mtime)}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class Neo4jBootstrap:
    def __init__(self, driver: Driver):
        self.driver = driver
        self.batch_size = int(os.getenv("NEO4J_BOOTSTRAP_BATCH", "500"))

    def run_if_needed(self):
        enabled = os.getenv("NEO4J_AUTO_INIT", "true").strip().lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return

        data_dir = Path(os.getenv("NEO4J_DATA_DIR", str(_default_data_dir()))).expanduser().resolve()
        ingredients_file = data_dir / "ingredients_final.json"
        recipes_file = data_dir / "recipes_final.json"
        relations_file = data_dir / "food_relations.json"

        required = [ingredients_file, recipes_file, relations_file]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            print(f"Neo4j 自动初始化跳过：数据文件缺失 {missing}")
            return

        data_version = _data_fingerprint(required)
        env_version = os.getenv("NEO4J_BOOTSTRAP_VERSION", "")
        version = env_version.strip() or f"auto-{data_version}"
        force = os.getenv("NEO4J_FORCE_REIMPORT", "false").strip().lower() in {"1", "true", "yes", "on"}

        with self.driver.session() as session:
            self._ensure_constraints(session)
            stored_version = self._get_stored_version(session)
            if (not force) and stored_version == version:
                return

            ingredients = _read_json(ingredients_file)
            recipes = _read_json(recipes_file)
            relations = _read_json(relations_file)

            ingredient_rows = self._normalize_ingredients(ingredients)
            recipe_rows, contains_rows = self._normalize_recipes(recipes)
            relation_rows = self._normalize_relations(relations)

            self._import_ingredients(session, ingredient_rows)
            self._import_recipes(session, recipe_rows)
            self._import_contains(session, contains_rows)
            self._import_relations(session, relation_rows)

            self._set_stored_version(session, version)
            print(
                "Neo4j 自动初始化完成: "
                f"ingredients={len(ingredient_rows)}, recipes={len(recipe_rows)}, "
                f"contains={len(contains_rows)}, relations={len(relation_rows)}, version={version}"
            )

    def _ensure_constraints(self, session):
        queries = [
            "CREATE CONSTRAINT ingredient_name_unique IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.name IS UNIQUE",
            "CREATE CONSTRAINT recipe_name_unique IF NOT EXISTS FOR (r:Recipe) REQUIRE r.name IS UNIQUE",
            "CREATE CONSTRAINT nutrient_name_unique IF NOT EXISTS FOR (n:Nutrient) REQUIRE n.name IS UNIQUE",
            "CREATE CONSTRAINT system_meta_key_unique IF NOT EXISTS FOR (m:SystemMeta) REQUIRE m.key IS UNIQUE",
            "CREATE INDEX ingredient_category_idx IF NOT EXISTS FOR (i:Ingredient) ON (i.category)",
            "CREATE INDEX recipe_category_idx IF NOT EXISTS FOR (r:Recipe) ON (r.category)",
        ]
        for q in queries:
            session.run(q)

    def _get_stored_version(self, session) -> str:
        row = session.run(
            "MATCH (m:SystemMeta {key:'neo4j_bootstrap_version'}) RETURN m.value AS value LIMIT 1"
        ).single()
        return str(row["value"]) if row and row.get("value") else ""

    def _set_stored_version(self, session, version: str):
        session.run(
            "MERGE (m:SystemMeta {key:'neo4j_bootstrap_version'}) "
            "SET m.value=$value, m.updated_at=datetime()",
            {"value": version},
        )

    def _normalize_ingredients(self, rows: List[dict]) -> List[dict]:
        dedup: Dict[str, dict] = {}
        for item in rows:
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            nutrients = item.get("nutrients") if isinstance(item.get("nutrients"), dict) else {}
            payload = {
                "name": name,
                "original_name": str(item.get("original_name", name)).strip(),
                "category": str(item.get("category", "Other")).strip() or "Other",
                "cal_per_100g": _to_float(item.get("cal_per_100g", 0)),
                "calories": _to_float((nutrients.get("热量") or {}).get("value", 0)),
                "protein": _to_float((nutrients.get("蛋白质") or {}).get("value", 0)),
                "fat": _to_float((nutrients.get("脂肪") or {}).get("value", 0)),
                "carbs": _to_float((nutrients.get("碳水化合物") or {}).get("value", 0)),
                "fiber": _to_float((nutrients.get("纤维素") or {}).get("value", 0)),
                "unit_info": json.dumps(item.get("unit_info", []), ensure_ascii=False),
                "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
                "raw_json": json.dumps(item, ensure_ascii=False),
            }
            dedup[name] = payload
        return list(dedup.values())

    def _normalize_recipes(self, rows: List[dict]) -> Tuple[List[dict], List[dict]]:
        recipe_dedup: Dict[str, dict] = {}
        contain_dedup: Dict[Tuple[str, str], dict] = {}

        for item in rows:
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            nutrients = item.get("nutrients") if isinstance(item.get("nutrients"), dict) else {}
            steps = item.get("steps") if isinstance(item.get("steps"), list) else []
            ingredients = item.get("ingredients") if isinstance(item.get("ingredients"), list) else []

            recipe_dedup[name] = {
                "name": name,
                "category": str(item.get("category", "")).strip(),
                "image": str(item.get("image", "")).strip(),
                "calories": _to_float((nutrients.get("热量") or {}).get("value", 0)),
                "protein": _to_float((nutrients.get("蛋白质") or {}).get("value", 0)),
                "fat": _to_float((nutrients.get("脂肪") or {}).get("value", 0)),
                "carbs": _to_float((nutrients.get("碳水化合物") or {}).get("value", 0)),
                "fiber": _to_float((nutrients.get("纤维素") or {}).get("value", 0)),
                "steps": "\n".join(str(s).strip() for s in steps if str(s).strip()),
                "steps_raw": json.dumps(steps, ensure_ascii=False),
                "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
                "ingredients_raw": json.dumps(ingredients, ensure_ascii=False),
                "raw_json": json.dumps(item, ensure_ascii=False),
            }

            for ing in ingredients:
                if not isinstance(ing, dict):
                    continue
                ing_name = str(ing.get("ingredient_name", "")).strip()
                if not ing_name:
                    continue
                key = (name, ing_name)
                contain_dedup[key] = {
                    "recipe_name": name,
                    "ingredient_name": ing_name,
                    "weight_g": _to_float(ing.get("weight_g", 0)),
                    "raw_text": str(ing.get("raw_text", "")),
                    "is_linked": bool(ing.get("is_linked", False)),
                }

        return list(recipe_dedup.values()), list(contain_dedup.values())

    def _normalize_relations(self, payload: dict) -> List[dict]:
        relation_map = {
            "互补": "COMPLEMENT_WITH",
            "互斥": "CLASH_WITH",
            "重叠": "SIMILAR_TO",
        }

        result: Dict[Tuple[str, str, str, str], dict] = {}

        if not isinstance(payload, dict):
            return []

        for _, category_block in payload.items():
            if not isinstance(category_block, dict):
                continue
            for _, foods in category_block.items():
                if not isinstance(foods, list):
                    continue
                for food in foods:
                    if not isinstance(food, dict):
                        continue
                    src = str(food.get("食物名称", "")).strip()
                    if not src:
                        continue

                    rel_obj = food.get("食物关系", {})
                    if not isinstance(rel_obj, dict):
                        continue

                    for cn_type, rel_type in relation_map.items():
                        items = rel_obj.get(cn_type, [])
                        if not isinstance(items, list):
                            continue
                        for it in items:
                            if not isinstance(it, dict):
                                continue
                            dst = str(it.get("食物名称", "")).strip()
                            reason = str(it.get("描述", "")).strip()
                            if not dst or src == dst:
                                continue
                            key = (src, dst, rel_type, reason)
                            result[key] = {
                                "src": src,
                                "dst": dst,
                                "rel_type": rel_type,
                                "reason": reason,
                            }

        return list(result.values())

    def _import_ingredients(self, session, rows: List[dict]):
        if not rows:
            return
        query = """
        UNWIND $rows AS row
        MERGE (i:Ingredient {name: row.name})
        SET i.original_name = row.original_name,
            i.category = row.category,
            i.cal_per_100g = row.cal_per_100g,
            i.calories = row.calories,
            i.protein = row.protein,
            i.fat = row.fat,
            i.carbs = row.carbs,
            i.fiber = row.fiber,
            i.unit_info = row.unit_info,
            i.nutrients_raw = row.nutrients_raw,
            i.raw_json = row.raw_json,
            i.updated_at = datetime()
        """
        for batch in _chunked(rows, self.batch_size):
            session.run(query, {"rows": batch})

    def _import_recipes(self, session, rows: List[dict]):
        if not rows:
            return
        query = """
        UNWIND $rows AS row
        MERGE (r:Recipe {name: row.name})
        SET r.category = row.category,
            r.image = row.image,
            r.calories = row.calories,
            r.protein = row.protein,
            r.fat = row.fat,
            r.carbs = row.carbs,
            r.fiber = row.fiber,
            r.steps = row.steps,
            r.steps_raw = row.steps_raw,
            r.nutrients_raw = row.nutrients_raw,
            r.ingredients_raw = row.ingredients_raw,
            r.raw_json = row.raw_json,
            r.updated_at = datetime()
        """
        for batch in _chunked(rows, self.batch_size):
            session.run(query, {"rows": batch})

    def _import_contains(self, session, rows: List[dict]):
        if not rows:
            return
        query = """
        UNWIND $rows AS row
        MERGE (r:Recipe {name: row.recipe_name})
        MERGE (i:Ingredient {name: row.ingredient_name})
        ON CREATE SET i.category = 'Unknown', i.created_from = 'recipe_contains_only', i.updated_at = datetime()
        MERGE (r)-[rel:CONTAINS]->(i)
        SET rel.weight_g = row.weight_g,
            rel.raw_text = row.raw_text,
            rel.is_linked = row.is_linked,
            rel.updated_at = datetime()
        """
        for batch in _chunked(rows, self.batch_size):
            session.run(query, {"rows": batch})

    def _import_relations(self, session, rows: List[dict]):
        if not rows:
            return

        grouped: Dict[str, List[dict]] = {
            "COMPLEMENT_WITH": [],
            "CLASH_WITH": [],
            "SIMILAR_TO": [],
        }
        for row in rows:
            rel_type = row.get("rel_type")
            if rel_type in grouped:
                grouped[rel_type].append(row)

        queries = {
            "COMPLEMENT_WITH": """
                UNWIND $rows AS row
                MERGE (a:Ingredient {name: row.src})
                ON CREATE SET a.category = 'Unknown', a.created_from = 'food_relations', a.updated_at = datetime()
                MERGE (b:Ingredient {name: row.dst})
                ON CREATE SET b.category = 'Unknown', b.created_from = 'food_relations', b.updated_at = datetime()
                MERGE (a)-[r:COMPLEMENT_WITH]->(b)
                SET r.reason = row.reason, r.source = 'food_relations', r.updated_at = datetime()
            """,
            "CLASH_WITH": """
                UNWIND $rows AS row
                MERGE (a:Ingredient {name: row.src})
                ON CREATE SET a.category = 'Unknown', a.created_from = 'food_relations', a.updated_at = datetime()
                MERGE (b:Ingredient {name: row.dst})
                ON CREATE SET b.category = 'Unknown', b.created_from = 'food_relations', b.updated_at = datetime()
                MERGE (a)-[r:CLASH_WITH]->(b)
                SET r.reason = row.reason, r.source = 'food_relations', r.updated_at = datetime()
            """,
            "SIMILAR_TO": """
                UNWIND $rows AS row
                MERGE (a:Ingredient {name: row.src})
                ON CREATE SET a.category = 'Unknown', a.created_from = 'food_relations', a.updated_at = datetime()
                MERGE (b:Ingredient {name: row.dst})
                ON CREATE SET b.category = 'Unknown', b.created_from = 'food_relations', b.updated_at = datetime()
                MERGE (a)-[r:SIMILAR_TO]->(b)
                SET r.reason = row.reason, r.source = 'food_relations', r.updated_at = datetime()
            """,
        }

        for rel_type, rel_rows in grouped.items():
            if not rel_rows:
                continue
            for batch in _chunked(rel_rows, self.batch_size):
                session.run(queries[rel_type], {"rows": batch})
