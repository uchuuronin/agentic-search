# query expansion and schema inference.
import logging
from pipeline.llm_client import LLMClient
from pipeline.models import PlannerOutput, SearchQuery, InferredSchema

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = """Given a topic query, generate search sub-queries and a table schema.

Instructions:
1. Generate 3-5 search sub-queries that cover different facets of the topic.
   Vary terminology and specificity. Include one broad and one niche query.
2. Infer a table schema with 4-7 column names appropriate for comparing 
   entities of this type. First column must be a name/identifier.

Constraints:
- Respond with valid JSON only
- Do not add commentary or explanation
- If the topic is ambiguous, make a reasonable interpretation

Output format:
{
  "sub_queries": [
    {"query": "search string", "purpose": "why this helps"}
  ],
  "entity_schema": {
    "columns": ["Name", "Col2", "Col3"],
    "entity_type": "company/restaurant/tool/etc",
    "description": "what entities we are looking for"
  }
}"""

PLANNER_PROMPT = """Topic: "{query}"

Generate sub-queries and entity schema."""

class QueryPlanner:
    def __init__(self, llm: LLMClient = None):
        self.llm = llm or LLMClient()

    async def plan(self, query: str) -> PlannerOutput:
        # Decompose query into sub-queries and infer schema
        logger.info(f"Planning: {query}")

        result = await self.llm.complete_json(
            PLANNER_PROMPT.format(query=query),
            system=PLANNER_SYSTEM,
        )

        sub_queries = [SearchQuery(**sq) for sq in result["sub_queries"]]
        schema = InferredSchema(**result["entity_schema"])

        #ensure there's always a name column
        has_name = any("name" in col.lower() for col in schema.columns)
        if not has_name:
            schema.columns.insert(0, f"{schema.entity_type.title()} Name")

        return PlannerOutput(
            original_query=query,
            sub_queries=sub_queries,
            entity_schema=schema,
        )