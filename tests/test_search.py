# tests ddg api and scraping
import asyncio
from pipeline.search_scrape import WebSearcher, PageScraper
from pipeline.models import SearchQuery


async def test_search_and_scrape():
    # Test search
    searcher = WebSearcher()
    query = SearchQuery(query="AI startups healthcare 2024", purpose="test")
    results = await searcher.search_single(query, max_results=5)

    print(f"test search found {len(results)} results:")
    for r in results:
        print(f"\t{r.title[:60]}; URL:{r.url[:80]}")
    assert len(results) > 0, "Search returned no results"

    scraper = PageScraper()
    pages = await scraper.scrape_all(results)
    successful = [p for p in pages if p.success]

    print(f"\ntest scrape resulted in {len(successful)}/{len(results)} pages:")
    for p in pages:
        status = "scraped" if p.success else "failed"
        print(f"\t{status}; {p.url[:70]} ({len(p.content)} chars)")

    assert len(successful) > 0, "All scrapes failed"
    print(f"\nFirst 300 chars of best result:\n{successful[0].content[:300]}")
    print("\ntest search and scrape works.")

if __name__ == "__main__":
    asyncio.run(test_search_and_scrape())