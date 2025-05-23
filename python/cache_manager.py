from pathlib import Path
import pickle
import hashlib
import json
import time
import os
from typing import List, Dict

class CacheManager:
    def __init__(self, cache_dir="cache", version="5.0"):  # Added version parameter
        self.version = version
        self.base_cache_dir = Path(cache_dir)
        self.cache_dir = self.base_cache_dir / f"v{version}"  # Add version to path
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.entity_cache_dir = self.cache_dir / "entities"
        self.comparison_cache_dir = self.cache_dir / "comparisons"
        self.relation_cache_dir = self.cache_dir / "relations"
        self.entity_cache_dir.mkdir(exist_ok=True)
        self.comparison_cache_dir.mkdir(exist_ok=True)
        self.relation_cache_dir.mkdir(exist_ok=True)

    def _get_cache_key(self, text):
        """Generate cache key for text."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _normalize_entity_list(self, entity_list: List[Dict]) -> List[Dict]:
        """Normalize entity list to ensure consistent cache keys."""
        return sorted([
            {
                "entity": str(item["entity"]).lower().strip(),
                "variants": sorted(str(v).lower().strip() for v in item.get("variants", []))
            }
            for item in entity_list
        ], key=lambda x: x["entity"])

    def _get_comparison_cache_key(self, list1: List[Dict], list2: List[Dict]) -> str:
        """Generate a unique cache key for a comparison of two entity lists."""
        normalized_list1 = self._normalize_entity_list(list1)
        normalized_list2 = self._normalize_entity_list(list2)

        combined = json.dumps([normalized_list1, normalized_list2], sort_keys=True)
        return hashlib.sha256(combined.encode()).hexdigest()

    def get_cached_entities(self, text):
        cache_key = self._get_cache_key(text)
        cache_file = self.entity_cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            with cache_file.open('rb') as f:
                return pickle.load(f)
        return None

    def cache_entities(self, text, entities):
        cache_key = self._get_cache_key(text)
        cache_file = self.entity_cache_dir / f"{cache_key}.pkl"

        with cache_file.open('wb') as f:
            pickle.dump(entities, f)

    def get_cached_comparison(self, list1, list2):
        cache_key = self._get_comparison_cache_key(list1, list2)
        cache_file = self.comparison_cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            with cache_file.open('rb') as f:
                return pickle.load(f)
        return None

    def cache_comparison(self, list1, list2, result):
        cache_key = self._get_comparison_cache_key(list1, list2)
        cache_file = self.comparison_cache_dir / f"{cache_key}.pkl"

        with cache_file.open('wb') as f:
            pickle.dump(result, f)

    def cleanup_old_cache(self, days=30):
        """Delete cache files older than specified days."""
        now = time.time()
        for cache_file in self.base_cache_dir.rglob("*.pkl"):
            if os.stat(cache_file).st_mtime < now - days * 86400:
                cache_file.unlink()

    def clear_current_cache(self):
        """Clear all cache files for current version."""
        if self.cache_dir.exists():
            for cache_file in self.cache_dir.rglob("*.pkl"):
                cache_file.unlink()

    def list_cache_versions(self):
        """List all available cache versions."""
        versions = []
        if self.base_cache_dir.exists():
            for dir in self.base_cache_dir.iterdir():
                if dir.is_dir() and dir.name.startswith('v'):
                    versions.append(dir.name[1:])  # Remove 'v' prefix
        return sorted(versions)

    def cache_relations(self, concepts, text, relations):
        """Cache relations for a set of concepts and text."""
        cache_key = self._get_relation_cache_key(concepts, text)
        cache_file = self.relation_cache_dir / f"{cache_key}.pkl"

        try:
            serializable_relations = []
            for rel in relations:
                if hasattr(rel, '__dict__'):
                    rel_dict = {
                        "source": rel.source,
                        "relation_type": rel.relation_type,
                        "target": rel.target,
                        "evidence": rel.evidence,
                        "section_index": rel.section_index,
                        "section_name": rel.section_name,
                        "confidence": getattr(rel, 'confidence', 1.0)
                    }
                    serializable_relations.append(rel_dict)
                else:
                    serializable_relations.append(rel)

            with cache_file.open('wb') as f:
                pickle.dump(serializable_relations, f)

            return True
        except Exception as e:
            print(f"Error caching relations: {str(e)}")
            return False

    def get_cached_relations(self, concepts, text):
        """Get cached relations for a set of concepts and text."""
        cache_key = self._get_relation_cache_key(concepts, text)
        cache_file = self.relation_cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            try:
                with cache_file.open('rb') as f:
                    cached_relations = pickle.load(f)

                result_relations = []
                for rel_dict in cached_relations:
                    if isinstance(rel_dict, dict):
                        from entity_extraction import Relation
                        relation = Relation(
                            source=rel_dict["source"],
                            relation_type=rel_dict["relation_type"],
                            target=rel_dict["target"],
                            evidence=rel_dict["evidence"],
                            section_index=rel_dict.get("section_index", -1),
                            section_name=rel_dict.get("section_name", "global"),
                            confidence=rel_dict.get("confidence", 1.0)
                        )
                        result_relations.append(relation)
                    else:
                        result_relations.append(rel_dict)

                return result_relations
            except (EOFError, pickle.PickleError, Exception) as e:
                print(f"Error loading cached relations: {str(e)}")
                try:
                    cache_file.unlink()
                except:
                    pass
        return None

    def _get_relation_cache_key(self, concepts, text):
        """Generate cache key for relations."""
        sorted_concepts = sorted([c.get('id', '').lower() for c in concepts])

        combined = f"{','.join(sorted_concepts)}::{text}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()