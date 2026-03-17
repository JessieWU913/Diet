import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable


load_dotenv()


def chunked(items: List[dict], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def discover_neo4j_import_dirs() -> List[Path]:
    dirs: List[Path] = []

    env_dir = os.getenv("NEO4J_IMPORT_DIR", "").strip()
    if env_dir:
        dirs.append(Path(env_dir).expanduser())

    desktop_glob = Path.home() / "Library" / "Application Support" / "Neo4j Desktop" / "Application" / "relate-data" / "dbmss"
    if desktop_glob.exists():
        for p in desktop_glob.glob("*/import"):
            dirs.append(p)

    dirs.extend(
        [
            Path("/opt/homebrew/var/neo4j/import"),
            Path("/usr/local/var/neo4j/import"),
            Path("/var/lib/neo4j/import"),
            Path.cwd() / "import",
        ]
    )

    seen = set()
    result = []
    for d in dirs:
        key = str(d)
        if key in seen:
            continue
        seen.add(key)
        if d.exists():
            result.append(d)
    return result


def resolve_data_file(path_or_name: str, import_dir: str = "") -> str:
    p = Path(path_or_name).expanduser()
    if p.is_file():
        return str(p)

    if p.is_absolute() and not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")

    cwd_candidate = Path.cwd() / p
    if cwd_candidate.is_file():
        return str(cwd_candidate)

    candidate_dirs: List[Path] = []
    if import_dir.strip():
        candidate_dirs.append(Path(import_dir).expanduser())
    candidate_dirs.extend(discover_neo4j_import_dirs())

    for d in candidate_dirs:
        fp = d / p.name
        if fp.is_file():
            return str(fp)

    tried = [str(cwd_candidate)] + [str(d / p.name) for d in candidate_dirs]
    raise FileNotFoundError(
        "Could not locate data file.\n"
        f"Requested: {path_or_name}\n"
        "Tried:\n- " + "\n- ".join(tried) + "\n"
        "Tip: pass --neo4j-import-dir /path/to/neo4j/import or use absolute file path."
    )


def nutrients_to_items(nutrients: Dict) -> List[dict]:
    rows = []
    if not isinstance(nutrients, dict):
        return rows
    for n_name, n_payload in nutrients.items():
        if isinstance(n_payload, dict):
            value = safe_float(n_payload.get("value", 0))
            unit = str(n_payload.get("unit", "")).strip()
        else:
            value = safe_float(n_payload)
            unit = ""
        rows.append({"name": str(n_name).strip(), "value": value, "unit": unit})
    return rows


class DietGraphImporter:
    def __init__(self, uri: str, auth: Tuple[str, str]):
        self.driver = self._connect(uri, auth)

    @staticmethod
    def _connect(uri: str, auth: Tuple[str, str]):
        try:
            driver = GraphDatabase.driver(uri, auth=auth)
            driver.verify_connectivity()
            return driver
        except ServiceUnavailable as e:
            msg = str(e).lower()
            if "routing information" in msg and uri.startswith("neo4j://"):
                fallback = "bolt://" + uri[len("neo4j://") :]
                print(f"Routing failed, fallback to direct bolt: {fallback}")
                driver = GraphDatabase.driver(fallback, auth=auth)
                driver.verify_connectivity()
                return driver
            raise

    def close(self):
        self.driver.close()

    def create_constraints(self):
        print("Creating constraints and indexes...")
        queries = [
            "CREATE CONSTRAINT ingredient_name_unique IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.name IS UNIQUE",
            "CREATE CONSTRAINT recipe_name_unique IF NOT EXISTS FOR (r:Recipe) REQUIRE r.name IS UNIQUE",
            "CREATE CONSTRAINT nutrient_name_unique IF NOT EXISTS FOR (n:Nutrient) REQUIRE n.name IS UNIQUE",
            "CREATE INDEX ingredient_category_idx IF NOT EXISTS FOR (i:Ingredient) ON (i.category)",
            "CREATE INDEX recipe_category_idx IF NOT EXISTS FOR (r:Recipe) ON (r.category)",
        ]
        with self.driver.session() as session:
            for q in queries:
                session.run(q)

    def clear_database(self):
        print("WARNING: clearing graph...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def clear_domain_data(self):
        """Clear only import domain data, keep user/account/history nodes."""
        print("WARNING: clearing ingredient/recipe domain data (preserve user/account data)...")
        with self.driver.session() as session:
            session.run(
                """
                MATCH (n)
                WHERE n:Ingredient OR n:Recipe OR n:Nutrient
                DETACH DELETE n
                """
            )

    def import_ingredients(self, ingredient_file: str, batch_size: int = 500, import_nutrient_nodes: bool = True):
        print(f"Importing ingredients from: {ingredient_file}")
        with open(ingredient_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        ingredient_rows = []
        nutrient_rel_rows = []

        for item in data:
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            nutrients = item.get("nutrients", {}) if isinstance(item.get("nutrients"), dict) else {}
            nutrient_items = nutrients_to_items(nutrients)

            row = {
                "name": name,
                "original_name": str(item.get("original_name", name)).strip(),
                "category": str(item.get("category", "Other")).strip() or "Other",
                "calories": safe_float(nutrients.get("热量", {}).get("value", 0) if isinstance(nutrients.get("热量"), dict) else 0),
                "protein": safe_float(nutrients.get("蛋白质", {}).get("value", 0) if isinstance(nutrients.get("蛋白质"), dict) else 0),
                "fat": safe_float(nutrients.get("脂肪", {}).get("value", 0) if isinstance(nutrients.get("脂肪"), dict) else 0),
                "carbs": safe_float(nutrients.get("碳水化合物", {}).get("value", 0) if isinstance(nutrients.get("碳水化合物"), dict) else 0),
                "fiber": safe_float(nutrients.get("纤维素", {}).get("value", 0) if isinstance(nutrients.get("纤维素"), dict) else 0),
                "cal_per_100g": safe_float(item.get("cal_per_100g", 0)),
                "unit_info": json.dumps(item.get("unit_info", []), ensure_ascii=False),
                "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
                "nutrient_count": len(nutrient_items),
            }
            ingredient_rows.append(row)

            if import_nutrient_nodes:
                for n in nutrient_items:
                    nutrient_rel_rows.append(
                        {
                            "ingredient_name": name,
                            "nutrient_name": n["name"],
                            "nutrient_value": n["value"],
                            "nutrient_unit": n["unit"],
                        }
                    )

        ingredient_query = """
        UNWIND $rows AS row
        MERGE (i:Ingredient {name: row.name})
        SET i.original_name = row.original_name,
            i.category = row.category,
            i.calories = row.calories,
            i.protein = row.protein,
            i.fat = row.fat,
            i.carbs = row.carbs,
            i.fiber = row.fiber,
            i.cal_per_100g = row.cal_per_100g,
            i.unit_info = row.unit_info,
            i.nutrients_raw = row.nutrients_raw,
            i.nutrient_count = row.nutrient_count,
            i.updated_at = datetime()
        """

        nutrient_query = """
        UNWIND $rows AS row
        MATCH (i:Ingredient {name: row.ingredient_name})
        MERGE (n:Nutrient {name: row.nutrient_name})
        ON CREATE SET n.default_unit = row.nutrient_unit
        MERGE (i)-[r:HAS_NUTRIENT]->(n)
        SET r.value = row.nutrient_value,
            r.unit = row.nutrient_unit,
            r.updated_at = datetime()
        """

        with self.driver.session() as session:
            done = 0
            for batch in chunked(ingredient_rows, batch_size):
                session.run(ingredient_query, rows=batch)
                done += len(batch)
                print(f"Ingredients imported: {done}/{len(ingredient_rows)}")

            if import_nutrient_nodes:
                done_rel = 0
                for batch in chunked(nutrient_rel_rows, batch_size):
                    session.run(nutrient_query, rows=batch)
                    done_rel += len(batch)
                print(f"Nutrient relations imported: {done_rel}")

        print(f"Ingredient import complete: {len(ingredient_rows)}")

    def import_recipes(self, recipe_file: str, batch_size: int = 300):
        print(f"Importing recipes from: {recipe_file}")
        with open(recipe_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        recipe_rows = []
        contain_rows = []

        for item in data:
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            nutrients = item.get("nutrients", {}) if isinstance(item.get("nutrients"), dict) else {}
            steps_list = item.get("steps", []) if isinstance(item.get("steps"), list) else []
            ingredients_list = item.get("ingredients", []) if isinstance(item.get("ingredients"), list) else []

            recipe_rows.append(
                {
                    "name": name,
                    "category": item.get("category", ""),
                    "image": item.get("image", ""),
                    "calories": safe_float(nutrients.get("热量", {}).get("value", 0) if isinstance(nutrients.get("热量"), dict) else 0),
                    "protein": safe_float(nutrients.get("蛋白质", {}).get("value", 0) if isinstance(nutrients.get("蛋白质"), dict) else 0),
                    "fat": safe_float(nutrients.get("脂肪", {}).get("value", 0) if isinstance(nutrients.get("脂肪"), dict) else 0),
                    "carbs": safe_float(nutrients.get("碳水化合物", {}).get("value", 0) if isinstance(nutrients.get("碳水化合物"), dict) else 0),
                    "steps": "\n".join(steps_list),
                    "steps_raw": json.dumps(steps_list, ensure_ascii=False),
                    "nutrients_raw": json.dumps(nutrients, ensure_ascii=False),
                    "ingredients_raw": json.dumps(ingredients_list, ensure_ascii=False),
                }
            )

            for ing in ingredients_list:
                i_name = str(ing.get("ingredient_name", "")).strip()
                if not i_name:
                    continue
                contain_rows.append(
                    {
                        "recipe_name": name,
                        "ingredient_name": i_name,
                        "weight_g": safe_float(ing.get("weight_g", 0)),
                        "raw_text": str(ing.get("raw_text", "")),
                        "is_linked": bool(ing.get("is_linked", False)),
                    }
                )

        recipe_query = """
        UNWIND $rows AS row
        MERGE (r:Recipe {name: row.name})
        SET r.category = row.category,
            r.image = row.image,
            r.calories = row.calories,
            r.protein = row.protein,
            r.fat = row.fat,
            r.carbs = row.carbs,
            r.steps = row.steps,
            r.steps_raw = row.steps_raw,
            r.nutrients_raw = row.nutrients_raw,
            r.ingredients_raw = row.ingredients_raw,
            r.updated_at = datetime()
        """

        contains_query = """
        UNWIND $rows AS row
        MERGE (r:Recipe {name: row.recipe_name})
        MERGE (i:Ingredient {name: row.ingredient_name})
        ON CREATE SET i.category = 'Unknown', i.created_from = 'recipe_contains_only'
        MERGE (r)-[rel:CONTAINS]->(i)
        SET rel.weight_g = row.weight_g,
            rel.raw_text = row.raw_text,
            rel.is_linked = row.is_linked,
            rel.updated_at = datetime()
        """

        with self.driver.session() as session:
            done = 0
            for batch in chunked(recipe_rows, batch_size):
                session.run(recipe_query, rows=batch)
                done += len(batch)
                print(f"Recipes imported: {done}/{len(recipe_rows)}")

            done_rel = 0
            for batch in chunked(contain_rows, batch_size):
                session.run(contains_query, rows=batch)
                done_rel += len(batch)
            print(f"CONTAINS relations imported: {done_rel}")

        print(f"Recipe import complete: {len(recipe_rows)}")

    def import_food_relations(self, relation_file: str, batch_size: int = 1000):
        print(f"Importing ingredient relations from: {relation_file}")
        with open(relation_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("food_relations.json must be a dict by category")

        relation_map = {
            "互补": "COMPLEMENT_WITH",
            "互斥": "CLASH_WITH",
            "重叠": "SIMILAR_TO",
        }

        rel_rows_by_type: Dict[str, List[dict]] = {v: [] for v in relation_map.values()}
        seen = set()

        for _, category_block in data.items():
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
                            if key in seen:
                                continue
                            seen.add(key)
                            rel_rows_by_type[rel_type].append(
                                {"src": src, "dst": dst, "reason": reason}
                            )

        query_map = {
            "COMPLEMENT_WITH": """
                UNWIND $rows AS row
                MERGE (a:Ingredient {name: row.src})
                ON CREATE SET a.category = 'Unknown', a.created_from = 'food_relations'
                MERGE (b:Ingredient {name: row.dst})
                ON CREATE SET b.category = 'Unknown', b.created_from = 'food_relations'
                MERGE (a)-[r:COMPLEMENT_WITH]->(b)
                SET r.reason = row.reason, r.source = 'food_relations', r.updated_at = datetime()
            """,
            "CLASH_WITH": """
                UNWIND $rows AS row
                MERGE (a:Ingredient {name: row.src})
                ON CREATE SET a.category = 'Unknown', a.created_from = 'food_relations'
                MERGE (b:Ingredient {name: row.dst})
                ON CREATE SET b.category = 'Unknown', b.created_from = 'food_relations'
                MERGE (a)-[r:CLASH_WITH]->(b)
                SET r.reason = row.reason, r.source = 'food_relations', r.updated_at = datetime()
            """,
            "SIMILAR_TO": """
                UNWIND $rows AS row
                MERGE (a:Ingredient {name: row.src})
                ON CREATE SET a.category = 'Unknown', a.created_from = 'food_relations'
                MERGE (b:Ingredient {name: row.dst})
                ON CREATE SET b.category = 'Unknown', b.created_from = 'food_relations'
                MERGE (a)-[r:SIMILAR_TO]->(b)
                SET r.reason = row.reason, r.source = 'food_relations', r.updated_at = datetime()
            """,
        }

        with self.driver.session() as session:
            total = 0
            for rel_type, rows in rel_rows_by_type.items():
                if not rows:
                    continue
                done = 0
                for batch in chunked(rows, batch_size):
                    session.run(query_map[rel_type], rows=batch)
                    done += len(batch)
                total += done
                print(f"{rel_type} imported: {done}")

        print(f"Ingredient relation import complete: {total}")

    def validate_import(self):
        checks = {
            "ingredients_total": "MATCH (i:Ingredient) RETURN count(i) AS v",
            "recipes_total": "MATCH (r:Recipe) RETURN count(r) AS v",
            "ingredients_missing_nutrients_raw": "MATCH (i:Ingredient) WHERE i.nutrients_raw IS NULL OR trim(toString(i.nutrients_raw)) = '' RETURN count(i) AS v",
            "ingredients_missing_original_name": "MATCH (i:Ingredient) WHERE i.original_name IS NULL OR trim(toString(i.original_name)) = '' RETURN count(i) AS v",
            "ingredients_missing_cal_per_100g": "MATCH (i:Ingredient) WHERE i.cal_per_100g IS NULL RETURN count(i) AS v",
            "ingredient_has_nutrient_rel": "MATCH (:Ingredient)-[r:HAS_NUTRIENT]->(:Nutrient) RETURN count(r) AS v",
            "recipe_contains_rel": "MATCH (:Recipe)-[r:CONTAINS]->(:Ingredient) RETURN count(r) AS v",
        }

        print("\n=== Import Validation Report ===")
        with self.driver.session() as session:
            for name, q in checks.items():
                v = session.run(q).single()["v"]
                print(f"{name}: {v}")

            sample = session.run(
                "MATCH (i:Ingredient {name: $name}) RETURN i.name AS name, i.calories AS calories, i.nutrient_count AS nutrient_count, i.nutrients_raw AS nutrients_raw LIMIT 1",
                name="菠菜",
            ).single()
            if sample:
                print("sample 菠菜:")
                print(
                    {
                        "name": sample["name"],
                        "calories": sample["calories"],
                        "nutrient_count": sample["nutrient_count"],
                        "nutrients_raw_preview": (sample["nutrients_raw"] or "")[:160],
                    }
                )


def parse_args():
    parser = argparse.ArgumentParser(description="Full importer for Diet Graph")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "neo4j://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--recipe-file", default="recipes_final.json")
    parser.add_argument("--ingredient-file", default="ingredients_final.json")
    parser.add_argument("--relation-file", default="food_relations.json")
    parser.add_argument(
        "--neo4j-import-dir",
        default=os.getenv("NEO4J_IMPORT_DIR", ""),
        help="Directory containing JSON files (e.g. Neo4j import directory)",
    )
    parser.add_argument("--clear", action="store_true", help="Clear ingredient/recipe/nutrient graph data before import (preserve users)")
    parser.add_argument("--clear-all", action="store_true", help="Clear all graph data before import (including users/history)")
    parser.add_argument("--ingredient-batch", type=int, default=500)
    parser.add_argument("--recipe-batch", type=int, default=300)
    parser.add_argument("--relation-batch", type=int, default=1000)
    parser.add_argument("--only-relations", action="store_true", help="Import only food relations without ingredient/recipe reload")
    parser.add_argument("--no-nutrient-nodes", action="store_true", help="Do not create HAS_NUTRIENT relations")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not args.password:
        raise SystemExit("Missing Neo4j password. Pass --password or set NEO4J_PASSWORD.")

    importer = DietGraphImporter(args.uri, (args.user, args.password))
    try:
        ingredient_file = None
        recipe_file = None
        relation_file = None

        if not args.only_relations:
            ingredient_file = resolve_data_file(args.ingredient_file, args.neo4j_import_dir)
            recipe_file = resolve_data_file(args.recipe_file, args.neo4j_import_dir)
            print(f"Resolved ingredient file: {ingredient_file}")
            print(f"Resolved recipe file: {recipe_file}")

        if args.relation_file:
            try:
                relation_file = resolve_data_file(args.relation_file, args.neo4j_import_dir)
                print(f"Resolved relation file: {relation_file}")
            except FileNotFoundError as e:
                print(f"WARNING: relation file not found, skip relation import. {e}")

        if args.clear_all:
            importer.clear_database()
        elif args.clear:
            importer.clear_domain_data()

        importer.create_constraints()

        if not args.only_relations:
            importer.import_ingredients(
                ingredient_file=ingredient_file,
                batch_size=args.ingredient_batch,
                import_nutrient_nodes=not args.no_nutrient_nodes,
            )
            importer.import_recipes(recipe_file=recipe_file, batch_size=args.recipe_batch)

        if relation_file:
            importer.import_food_relations(relation_file=relation_file, batch_size=args.relation_batch)

        importer.validate_import()
        print("\nImport finished successfully.")
    except Exception as e:
        print(f"Import failed: {e}")
        raise
    finally:
        importer.close()
