# Test api call
import asyncio
from pipeline.llm_client import LLMClient


async def test_groq_connection():
    client = LLMClient()
    
    # for raw text
    response = await client.complete("Say 'hello world' and nothing else.")
    print(f"test text response: {response}")
    assert "hello" in response.lower()
    
    # for JSON output
    result = await client.complete_json(
        'Return a JSON object with keys "name" and "age" for a fictional person.'
    )
    print(f"test JSON response: {result}")
    assert "name" in result
    assert "age" in result
    
    print("\nGroq connection works")


if __name__ == "__main__":
    asyncio.run(test_groq_connection())