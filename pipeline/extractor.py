#schema-bound extraction with source provenance.
import asyncio
import logging
from pipeline.llm_client import LLMClient
from pipeline.models import InferredSchema, ScrapedPage, ExtractedEntity, CellSource
import time
logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM = """Extract structured entity data from web page content.

Constraints:
- Only extract entities explicitly mentioned in the provided text
- Every value MUST have a supporting text snippet from the source
- If a value is not stated in the text, set it to null
- Do not infer, guess, or fabricate any values
- If no matching entities exist in the text, return {"entities": []}
- Keep snippets under 100 characters, taken verbatim from the content

Respond with valid JSON only."""

EXTRACTION_PROMPT = """Extract all {entity_type} entities from this content.

Columns to extract: {columns}
Entity description: {description}
Source URL: {url}

Content:
{content}

Return JSON:
{{
  "entities": [
    {{
      "attributes": {{
        "{first_col}": "value or null",
        ...one key per column...
      }},
      "sources": {{
        "{first_col}": {{"snippet": "verbatim text from content"}},
        ...one per non-null column...
      }},
      "confidence": 0.0 to 1.0
    }}
  ]
}}"""

class EntityExtractor:
    def __init__(self, llm: LLMClient = None):
        self.llm = llm or LLMClient()

    async def extract_from_page(
        self, page: ScrapedPage, schema: InferredSchema
    ) -> list[ExtractedEntity]:
        """Extract entities from one page using the schema."""
        if not page.success or not page.content.strip():
            return []

        print(f"Extracting from: {page.url[:70]}... ({len(page.content)} chars)")
        prompt = EXTRACTION_PROMPT.format(
            entity_type=schema.entity_type,
            columns=", ".join(schema.columns),
            description=schema.description,
            url=page.url,
            content=page.content,
            first_col=schema.columns[0],
        )
        try:
            result = await self.llm.complete_json(prompt, system=EXTRACTION_SYSTEM)
        except Exception as e:
            logger.error(f"Extraction failed for {page.url}: {e}")
            return []

        entities = []
        for raw in result.get("entities", []):
            sources = {}
            for col, src in raw.get("sources", {}).items():
                if isinstance(src, dict) and "snippet" in src:
                    sources[col] = CellSource(url=page.url, snippet=src["snippet"])
                elif isinstance(src, str):
                    sources[col] = CellSource(url=page.url, snippet=src)

            # Convert all values to strings (LLM sometimes returns ints/floats)
            raw_attrs = raw.get("attributes", {})
            attributes = {k: str(v) if v is not None else None for k, v in raw_attrs.items()}

            entities.append(ExtractedEntity(
                attributes=attributes,
                sources=sources,
                source_url=page.url,
                confidence=raw.get("confidence"),
            ))

        logger.info(f"Extracted {len(entities)} entities from {page.url}")
        return entities

    async def extract_from_all_pages(
        self, pages: list[ScrapedPage], schema: InferredSchema
    ) -> list[ExtractedEntity]:
        #sequential extraction
        all_entities = []
        successful_pages = [p for p in pages if p.success]
        for i, page in enumerate(successful_pages):
            print(f"Extracting page {i+1}/{len(successful_pages)}")
            entities = await self.extract_from_page(page, schema)
            all_entities.extend(entities)
            time.sleep(2)
        print(f"Total entities extracted: {len(all_entities)}")
        return all_entities