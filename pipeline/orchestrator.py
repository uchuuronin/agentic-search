#connecting workflow together and with self relection calling for a re-search
import time
import logging
from pipeline.planner import QueryPlanner
from pipeline.search_scrape import WebSearcher, PageScraper
from pipeline.extractor import EntityExtractor
from pipeline.refiner import deduplicate_and_merge, ReflectionAgent
from pipeline.models import PipelineResult, SearchQuery
from pipeline.config import settings

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(self):
        self.planner = QueryPlanner()
        self.searcher = WebSearcher()
        self.scraper = PageScraper()
        self.extractor = EntityExtractor()
        self.reflector = ReflectionAgent()

    async def run(self, query: str, on_stage=None) -> PipelineResult:
        start = time.time()
        stages = []

        def stage(name):
            stages.append(name)
            logger.info(f"Stage: {name}")
            if on_stage:
                on_stage(name)

        stage("planning")
        plan = await self.planner.plan(query)

        stage("searching")
        search_results = await self.searcher.search_all(
            plan.sub_queries, max_results_per_query=3
        )

        stage("scraping")
        pages = await self.scraper.scrape_all(search_results)

        stage("extracting")
        all_entities = await self.extractor.extract_from_all_pages(
            pages, plan.entity_schema
        )

        stage("refining")
        merged = deduplicate_and_merge(all_entities, plan.entity_schema)

        reflection_rounds = 0 #track self-reflection loops
        for _ in range(settings.MAX_REFLECTION_ROUNDS):
            stage("reflecting")
            reflection = await self.reflector.reflect(
                merged, plan.entity_schema, query
            )
            reflection_rounds += 1

            if not reflection.should_research_more or not reflection.additional_queries:
                break

            # Re-search with targeted queries
            stage("re-searching")
            new_queries = [
                SearchQuery(query=q, purpose="fill gap from reflection")
                for q in reflection.additional_queries[:3]
            ]
            new_results = await self.searcher.search_all(new_queries, max_results_per_query=2)
            new_pages = await self.scraper.scrape_all(new_results)
            new_entities = await self.extractor.extract_from_all_pages(
                new_pages, plan.entity_schema
            )
            all_entities.extend(new_entities)
            merged = deduplicate_and_merge(all_entities, plan.entity_schema)

        elapsed = time.time() - start
        logger.info(f"done in {elapsed:.1f}s resulting in {len(merged)} entities")

        return PipelineResult(
            query=query,
            entity_schema=plan.entity_schema,
            entities=merged,
            total_sources_consulted=len(search_results),
            total_pages_scraped=len([p for p in pages if p.success]),
            pipeline_stages=stages,
            reflection_rounds=reflection_rounds,
        )