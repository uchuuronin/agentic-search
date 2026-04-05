# Pipeline test
import asyncio
import time
from pipeline.planner import QueryPlanner
from pipeline.search_scrape import WebSearcher, PageScraper
from pipeline.extractor import EntityExtractor
from pipeline.config import settings


async def test_intelligence_pipeline():
    query = "AI startups in healthcare"
    print(f"Using model: {settings.LLM_MODEL}")
    print(f"Max content chars: {settings.MAX_CONTENT_CHARS}")

    # Planner test
    t = time.time()
    planner = QueryPlanner()
    plan = await planner.plan(query)
    print(f"\n[Planner] {time.time()-t:.1f}s")
    print(f"Schema: {plan.entity_schema.columns}")
    print(f"Sub-queries: {len(plan.sub_queries)}")

    # Search
    t = time.time()
    searcher = WebSearcher()
    results = await searcher.search_all(plan.sub_queries, max_results_per_query=2)
    print(f"\n[Search] {time.time()-t:.1f}s — {len(results)} results")

    # Scrape
    t = time.time()
    scraper = PageScraper()
    pages = await scraper.scrape_all(results, max_pages=3)
    successful = [p for p in pages if p.success]
    print(f"\n[Scrape] {time.time()-t:.1f}s — {len(successful)}/{len(pages)} pages")
    for p in pages:
        print(f"\t{len(p.content):5d} chars | {p.url[:60]}")

    # Extract
    t = time.time()
    extractor = EntityExtractor()
    entities = await extractor.extract_from_all_pages(pages, plan.entity_schema)
    print(f"\n[Extract] {time.time()-t:.1f}s — {len(entities)} entities")

    for e in entities:
        name_col = plan.entity_schema.columns[0]
        name = e.attributes.get(name_col, "???")
        filled = sum(1 for v in e.attributes.values() if v)
        total = len(plan.entity_schema.columns)
        print(f"\t{name} ({filled}/{total} fields)")

    if entities:
        print(f"\nExample entity:")
        e = entities[0]
        for col, val in e.attributes.items():
            source = e.sources.get(col)
            snippet = f' ← "{source.snippet[:50]}"' if source else ""
            print(f"\t{col}: {val}{snippet}")

    print(f"\ntest pipeline works.")


if __name__ == "__main__":
    asyncio.run(test_intelligence_pipeline())