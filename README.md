# Agentic Search

A search system that takes a topic query and produces a structured table of entities with attributes, sourced from the web. Type your query and get back a table with company names, funding amounts, founding years (each value linked to where it came from)

## How it works

The system runs a six-stage pipeline:
```
Query → Planner → Searcher → Scraper → Extractor → Refiner → Table
                                                       ↑         |
                                                       └─────────┘
                                                    (reflection loop)
```

1. **Planner**: LLM decomposes your query into 3-5 sub-queries and infers what columns the result table should have. "Top pizza places in Brooklyn" might get columns like Name, Address, Rating, CuisineType, HasOutdoorSeating. This is based on query expansion and schema-first extraction.

2. **Searcher**: Runs each sub-query against DuckDuckGo. No API key needed, evaluator can run it immediately.

3. **Scraper**: Fetches pages, strips HTML noise (nav bars, ads, scripts, footers), truncates to fit the LLM context window. Some sites block automated access, so failed scrapes fall back to the search snippet DuckDuckGo already provided.

4. **Extractor**: LLM reads each cleaned page and extracts entities that match the schema. Every value must include a source snippet (the actual text from the page that supports it). Uses Groq's JSON mode for reliable structured output.

5. **Refiner**: Deduplicates entities across pages (fuzzy name matching), merges partial records. "Tempus" from one page and "Tempus AI" from another become one row with data from both sources.

6. **Reflection**: LLM reviews the table for gaps (missing cells), decides whether to re-search. If it finds that Verily is missing a founding year, it generates a targeted query like "Verily founding year" and the pipeline loops back through search-scrape-extract for that specific gap.

The reflection loop is what makes this agentic rather than a fixed pipeline. The system decides on its own whether the results are good enough or whether it should keep looking.

## Setup

```bash
git clone https://github.com/uchuuronin/agentic-search.git
cd agentic-search/code
conda create -n ciir python=3.11 -y
conda activate ciir
pip install -r requirements.txt
```

Create a `.env` file in the `code/` directory:

```
GROQ_API_KEY=gsk_your_key_here
LLM_MODEL=llama-3.1-8b-instant
MAX_SEARCH_RESULTS=10
MAX_PAGES_TO_SCRAPE=8
MAX_REFLECTION_ROUNDS=1
SCRAPE_TIMEOUT_SECONDS=10
MAX_CONTENT_CHARS=3000
LOG_LEVEL=INFO
```
Get a free Groq API key at console.groq.com/keys

For better output quality, use `LLM_MODEL=llama-3.3-70b-versatile`. The 8B model is faster but less accurate at extraction. The 70B model produces better structured output but hits Groq's free tier rate limits more often, which adds latency from automatic retries.

Start the server using the line below and open http://localhost:8000 in your browser.

```bash
uvicorn main:app --reload --port 8000
```

## API
```
GET /api/search?q=your+query # returns JSON
GET /api/search/stream?q=your+query # returns SSE stream with stage updates + final JSON
GET /api/health # returns status and model name
```

## Design choices

**LLM provider:** Groq free tier. No credit card needed. Uses the OpenAI SDK pointed at Groq's endpoint, so switching providers is a one-line change in .env.

**Search:** DuckDuckGo. Free, no API key. Results come from Bing's ranking pipeline under the hood. The Python library is just an HTTP wrapper, not a search engine itself.

**Schema-first extraction:** The LLM infers table columns before extraction, not after. This was based on reading the WebLists paper: where they found that LLMs with search achieve 3% recall in structured extraction without a schema, vs 66% with schema-bound extraction.

**Constrained JSON output:** We use Groq's `json_object` response format instead of prompting the LLM to return JSON. This guarantees valid JSON syntax. Note: `llama-3.3-70b-versatile` supports `json_object` mode (valid JSON guaranteed) but not `json_schema` mode (schema-level constrained decoding), which is currently limited to GPT-OSS models on Groq.

**Reflection loop:** After initial extraction, the LLM reviews the table and can trigger re-search for specific gaps. This is one round by default. Based on reading about pseudo-relevance feedback in IR and the Self-RAG paper's idea of models critiquing their own output.

**Sequential LLM calls:** Extraction runs one page at a time with delays between calls. Groq's free tier has token-per-minute limits, and parallel calls trigger 429 errors with exponential backoff that ends up slower than sequential processing.

**HTML cleaning:** We strip nav/footer/ad elements before sending content to the LLM. This is the web equivalent of stopword removal, it reduces noise so the extractor sees actual content.

**Snippet fallback:** When scraping fails (403, timeout, JS-rendered page), we use the search snippet DuckDuckGo already returned. Short but real content, so the pipeline never returns empty.

## Known limitations

- **JavaScript-rendered pages** return empty or minimal content. The scraper fetches raw HTML, not rendered DOM. A browser-based scraper would fix this but adds complexity and latency.
- **Rate limiting** on Groq's free tier causes 429 errors with retry delays. A typical query takes 180-250 seconds, mostly waiting on LLM calls and retries.
- **Entity deduplication** uses string matching. "Alphabet" and "Google" would not be recognised as the same entity. Embedding-based similarity would improve this.
- **Some sites block scraping** (Yelp, TripAdvisor, LinkedIn). The snippet fallback helps, but provides less data.
- **LLM hallucination** still happens despite anti-hallucination prompts. The source snippet requirement makes fabricated data easier to spot, but does not eliminate it.
- **No persistent caching.** Repeating the same query re-runs the entire pipeline.

## Running tests

```bash
cd code
$env:PYTHONPATH = "."          # PowerShell
# export PYTHONPATH=.          # bash/zsh

python tests/test_llm.py       # test Groq connection
python tests/test_search.py    # test search + scrape
python tests/test_refiner.py   # test dedup/merge with mock data
python tests/test_pipeline.py  # end-to-end (takes 30-60s)
```
