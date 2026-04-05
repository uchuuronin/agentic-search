# deduplication, merging, and gap-filling.
import logging
from pipeline.llm_client import LLMClient
from pipeline.models import (
    ExtractedEntity, MergedEntity, CellSource,
    InferredSchema, ReflectionResult,
)

logger = logging.getLogger(__name__)

def _normalize_name(name: str) -> str:
    return (name.lower().strip()
            .replace(",", "").replace(".", "")
            .replace("inc", "").replace("llc", "")
            .replace("ltd", "").replace("corp", ""))


def _names_match(a: str, b: str) -> bool:
    na, nb = _normalize_name(a), _normalize_name(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return False


def deduplicate_and_merge(entities: list[ExtractedEntity],schema: InferredSchema) -> list[MergedEntity]:
    if not entities:
        return []

    name_col = schema.columns[0]
    for col in schema.columns:
        if "name" in col.lower():
            name_col = col
            break

    # Group entities by name
    groups: list[list[ExtractedEntity]] = []
    for entity in entities:
        entity_name = entity.attributes.get(name_col, "")
        if not entity_name:
            groups.append([entity])
            continue

        matched = False
        for group in groups:
            group_name = group[0].attributes.get(name_col, "")
            if group_name and _names_match(entity_name, group_name):
                group.append(entity)
                matched = True
                break

        if not matched:
            groups.append([entity])

    merged = []
    for group in groups:
        all_cols = set()
        for e in group:
            all_cols.update(e.attributes.keys())

        attributes = {}
        sources = {}
        source_urls = []

        for col in all_cols:
            best_value = None
            col_sources = []
            for e in group:
                val = e.attributes.get(col)
                if val and not best_value:
                    best_value = val
                if col in e.sources:
                    col_sources.append(e.sources[col])
            attributes[col] = best_value
            if col_sources:
                sources[col] = col_sources

        for e in group:
            if e.source_url not in source_urls:
                source_urls.append(e.source_url)

        # Use longest name variant as representative
        names = [e.attributes.get(name_col, "") for e in group if e.attributes.get(name_col)]
        if names:
            attributes[name_col] = max(names, key=len)

        merged.append(MergedEntity(
            attributes=attributes,
            sources=sources,
            source_urls=source_urls,
        ))

    logger.info(f"Cleaned {len(entities)} raw values to {len(merged)} unique entities")
    return merged


REFLECTION_SYSTEM = """Review a structured table of extracted entities for completeness.

Constraints:
- Identify specific missing values (null cells)
- Only suggest re-search if there are significant gaps
- Suggest specific, targeted search queries to fill gaps
- If the table is reasonably complete, set should_research_more to false
- Respond with valid JSON only"""

REFLECTION_PROMPT = """Original query: "{query}"
Entity type: {entity_type}
Columns: {columns}

Current table ({count} entities):
{table_summary}

Respond with JSON:
{{
  "gaps": ["list of specific gaps"],
  "additional_queries": ["targeted search queries to fill gaps"],
  "should_research_more": true/false
}}"""


class ReflectionAgent:
    def __init__(self, llm: LLMClient = None):
        self.llm = llm or LLMClient()

    async def reflect(
        self,
        entities: list[MergedEntity],
        schema: InferredSchema,
        original_query: str,
    ) -> ReflectionResult:
        # Review raw for gaps, suggest follow-up searches.
        table_lines = []
        for i, e in enumerate(entities):
            parts = [f"{col}: {e.attributes.get(col, 'null') or 'null'}"
                     for col in schema.columns]
            table_lines.append(f"\t{i+1}. {' | '.join(parts)}")
        table_summary = "\n".join(table_lines) or "  (empty)"

        prompt = REFLECTION_PROMPT.format(
            query=original_query,
            entity_type=schema.entity_type,
            columns=", ".join(schema.columns),
            count=len(entities),
            table_summary=table_summary,
        )

        try:
            result = await self.llm.complete_json(prompt, system=REFLECTION_SYSTEM)
            return ReflectionResult(
                gaps=result.get("gaps", []),
                additional_queries=result.get("additional_queries", []),
                should_research_more=result.get("should_research_more", False),
            )
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return ReflectionResult(
                gaps=[], additional_queries=[], should_research_more=False
            )