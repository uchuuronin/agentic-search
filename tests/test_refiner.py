# using mock data, test merge and reflecttion re-searching logic 
import asyncio
from pipeline.models import (
    ExtractedEntity, CellSource, InferredSchema,
)
from pipeline.refiner import deduplicate_and_merge, ReflectionAgent


# Mock data based on actual output from test_pipeline
MOCK_SCHEMA = InferredSchema(
    columns=["Name", "Founding Year", "Location", "Funding Status", "Technology Used", "Regulatory Status"],
    entity_type="healthcare AI startup",
    description="AI-focused healthcare startup companies",
)

MOCK_ENTITIES = [
    ExtractedEntity(
        attributes={"Name": "Tempus", "Founding Year": "2015", "Location": None, "Funding Status": None, "Technology Used": "genomic sequencing", "Regulatory Status": None},
        sources={"Name": CellSource(url="https://a.com", snippet="Tempus"), "Founding Year": CellSource(url="https://a.com", snippet="founded in 2015")},
        source_url="https://a.com",
    ),
    ExtractedEntity(
        attributes={"Name": "Tempus AI", "Founding Year": None, "Location": "Chicago", "Funding Status": "$1.1B raised", "Technology Used": None, "Regulatory Status": None},
        sources={"Name": CellSource(url="https://b.com", snippet="Tempus AI"), "Location": CellSource(url="https://b.com", snippet="based in Chicago"), "Funding Status": CellSource(url="https://b.com", snippet="raised $1.1B")},
        source_url="https://b.com",
    ),
    # Duplicate pair: Aidence twice
    ExtractedEntity(
        attributes={"Name": "Aidence", "Founding Year": "2017", "Location": None, "Funding Status": None, "Technology Used": "lung CT analysis", "Regulatory Status": None},
        sources={"Name": CellSource(url="https://a.com", snippet="Aidence")},
        source_url="https://a.com",
    ),
    ExtractedEntity(
        attributes={"Name": "Aidence", "Founding Year": None, "Location": "Amsterdam", "Funding Status": None, "Technology Used": None, "Regulatory Status": "CE marked"},
        sources={"Name": CellSource(url="https://c.com", snippet="Aidence"), "Location": CellSource(url="https://c.com", snippet="Amsterdam-based")},
        source_url="https://c.com",
    ),
    # Unique entity
    ExtractedEntity(
        attributes={"Name": "Verily", "Founding Year": None, "Location": "Dallas, Texas", "Funding Status": None, "Technology Used": "digital health tools", "Regulatory Status": None},
        sources={"Name": CellSource(url="https://a.com", snippet="Verily")},
        source_url="https://a.com",
    ),
]


def test_dedup_merge():
    """5 raw entities → 3 merged (Tempus pair + Aidence pair + Verily)."""
    merged = deduplicate_and_merge(MOCK_ENTITIES, MOCK_SCHEMA)

    print(f"removing duplicates test: {len(MOCK_ENTITIES)} raw should become {len(merged)} merged\n")
    assert len(merged) == 3, f"Expected 3, got {len(merged)}"

    # merge data test
    tempus = next(e for e in merged if "tempus" in e.attributes.get("Name", "").lower())
    print(f"Tempus merged:")
    for col, val in tempus.attributes.items():
        print(f"  {col}: {val}")

    assert tempus.attributes["Name"] == "Tempus AI"  # longest name wins
    assert tempus.attributes["Founding Year"] == "2015"  # from source A
    assert tempus.attributes["Location"] == "Chicago"  # from source B
    assert tempus.attributes["Funding Status"] == "$1.1B raised"  # from source B
    assert len(tempus.source_urls) == 2  # both sources tracked

    # merge location + tech
    aidence = next(e for e in merged if "aidence" in e.attributes.get("Name", "").lower())
    assert aidence.attributes["Location"] == "Amsterdam"
    assert aidence.attributes["Technology Used"] == "lung CT analysis"
    assert aidence.attributes["Regulatory Status"] == "CE marked"

    print("\nremoving duplicates and merging works.")


async def test_reflection():
    """Reflector should identify gaps in merged entities."""
    merged = deduplicate_and_merge(MOCK_ENTITIES, MOCK_SCHEMA)
    reflector = ReflectionAgent()
    result = await reflector.reflect(merged, MOCK_SCHEMA, "AI startups in healthcare")

    print(f"\nReflection test:")
    print(f"Gaps found: {len(result.gaps)}")
    for g in result.gaps:
        print(f"\t- {g}")
    print(f"note: should research more: {result.should_research_more}")
    print(f"note: suggested queries: {result.additional_queries}")

    assert len(result.gaps) > 0, "Should find some gaps"
    print("\nself-reflection works.")


if __name__ == "__main__":
    # Test dedup (no LLM needed)
    test_dedup_merge()

    # Test reflection (needs LLM)
    asyncio.run(test_reflection())