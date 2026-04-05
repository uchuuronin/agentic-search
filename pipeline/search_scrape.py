#first-stage retrieval and document preprocessing.
import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from pipeline.config import settings
from pipeline.models import SearchQuery, SearchResult, ScrapedPage
import time
logger = logging.getLogger(__name__)

# noise html content
REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "aside",
               "form", "iframe", "noscript", "svg", "img", "video", "audio",
               "button", "input", "select", "textarea"]
REMOVE_CLASSES = ["nav", "navbar", "sidebar", "footer", "header", "menu",
                  "advertisement", "ad", "cookie", "popup", "modal", "banner",
                  "comment", "comments", "related", "share", "social", "subscribe"]

# For sub-query generation on duckduckgo api
class WebSearcher:
    async def search_single(self, sub_query: SearchQuery, max_results: int = 10) -> list[SearchResult]:
        logger.info(f"Searching: {sub_query.query}")
        try:
            loop = asyncio.get_event_loop()
            def _do_search():
                time.sleep(1)
                with DDGS() as ddgs:
                    return list(ddgs.text(sub_query.query, max_results=max_results))

            raw_results = await loop.run_in_executor(None, _do_search)

            results = []
            for r in raw_results:
                url = r.get("href", r.get("link", ""))
                if not url:
                    continue
                results.append(SearchResult(
                    url=url,
                    title=r.get("title", ""),
                    snippet=r.get("body", r.get("snippet", "")),
                    source_query=sub_query.query,
                ))
            return results
        except Exception as e:
            logger.error(f"Search failed for '{sub_query.query}': {e}")
            return []

    async def search_all(self, sub_queries: list[SearchQuery], max_results_per_query: int = 10) -> list[SearchResult]:
        # parallel run of sub-queries
        tasks = [
            self.search_single(sq, max_results_per_query)
            for sq in sub_queries
        ]
        all_results_nested = await asyncio.gather(*tasks)
        all_results = [r for batch in all_results_nested for r in batch]
        return self._deduplicate(all_results)

    def _deduplicate(self, results: list[SearchResult]) -> list[SearchResult]:
        #duplicate removal
        seen = set()
        unique = []
        for r in results:
            normalized = r.url.rstrip("/").lower()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(r)
        return unique


class PageScraper:
    def clean_html(self, html: str, max_chars: int = None) -> str:
        """Strip non-content elements, return clean text."""
        max_chars = max_chars or settings.MAX_CONTENT_CHARS
        soup = BeautifulSoup(html, "html.parser")

        # Remove known noise tags
        for tag_name in REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Collect elements to remove
        to_remove = []
        for el in soup.find_all(True):
            el_classes = el.get("class") or []
            if isinstance(el_classes, list):
                classes = " ".join(el_classes)
            else:
                classes = str(el_classes)
            el_id = el.get("id") or ""
            combined = f"{classes} {el_id}".lower()
            if any(cls in combined for cls in REMOVE_CLASSES):
                to_remove.append(el)

        for el in to_remove:
            el.decompose()

        # Extract text, collapse whitespace
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[... truncated]"

        return text

    async def scrape_single(self, result: SearchResult) -> ScrapedPage:
        try:
            async with httpx.AsyncClient(
                timeout=settings.SCRAPE_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                response = await client.get(result.url)
                response.raise_for_status()
                content = self.clean_html(response.text)
                return ScrapedPage(
                    url=result.url,
                    title=result.title,
                    content=content,
                    success=True,
                )
        except Exception as e:
            logger.warning(f"Failed to scrape {result.url}: {e}")
            return ScrapedPage(
                url=result.url,
                title=result.title,
                content="",
                success=False,
                error=str(e),
            )

    async def scrape_all(self, results: list[SearchResult], max_pages: int = None) -> list[ScrapedPage]:
        #parallel scrape with concurrency limit
        max_pages = max_pages or settings.MAX_PAGES_TO_SCRAPE
        to_scrape = results[:max_pages]
        semaphore = asyncio.Semaphore(5)

        async def _limited(result: SearchResult) -> ScrapedPage:
            async with semaphore:
                return await self.scrape_single(result)

        pages = await asyncio.gather(*[_limited(r) for r in to_scrape])

        # Backfill failed pages with search snippets as fallback
        for i, page in enumerate(pages):
            if not page.success and to_scrape[i].snippet:
                pages[i] = ScrapedPage(
                    url=page.url,
                    title=page.title,
                    content=to_scrape[i].snippet,
                    success=True,  # snippet is usable content
                    error="used search snippet as fallback",
                )

        successful = [p for p in pages if p.success]
        logger.info(f"Scraped {len(successful)}/{len(to_scrape)} pages")
        return list(pages)