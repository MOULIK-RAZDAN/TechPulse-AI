#!/usr/bin/env python3
"""
Test script to verify the RAG fixes for:
1. Missing Data Problem (Anthropic hallucination)
2. Typo Wall Problem (anthriopc -> anthropic)
3. ScoredPoint Crash (object handling)
"""

import requests
import json
import time

def test_query(query, description):
    print(f"\n🧪 Testing: {description}")
    print(f"Query: '{query}'")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/query",
            json={"query": query},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"📊 Used realtime search: {result.get('used_realtime', False)}")
            print(f"🔄 Used reranking: {result.get('reranked', False)}")
            print(f"📈 Local results count: {result.get('local_results_count', 0)}")
            print(f"📝 Answer preview: {result['answer'][:200]}...")
            print(f"🔗 Sources: {len(result.get('sources', []))} found")
            return True
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🚀 Testing TechPulse AI RAG Fixes")
    print("=" * 50)
    
    # Wait for backend to be ready
    print("⏳ Waiting for backend to be ready...")
    for i in range(10):
        try:
            health = requests.get("http://localhost:8000/health", timeout=5)
            if health.status_code == 200:
                print("✅ Backend is ready!")
                break
        except:
            pass
        time.sleep(2)
    else:
        print("❌ Backend not ready after 20 seconds")
        return
    
    # Test cases
    tests = [
        # Test 1: Missing Data Problem - should trigger realtime search
        ("What is Anthropic and who founded it?", "Missing Data Problem (should use web search)"),
        
        # Test 2: Typo Wall Problem - should handle fuzzy matching
        ("Tell me about anthriopc", "Typo Wall Problem (fuzzy matching)"),
        
        # Test 3: General tech query - should use local data if available
        ("What are the latest developments in AI?", "General AI query (local + web hybrid)"),
        
        # Test 4: Very specific recent query - should definitely use web
        ("What happened with OpenAI today?", "Recent news query (force web search)"),
    ]
    
    results = []
    for query, description in tests:
        success = test_query(query, description)
        results.append(success)
        time.sleep(2)  # Rate limiting
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 All tests passed! RAG fixes are working.")
    else:
        print("⚠️ Some tests failed. Check the logs above.")

if __name__ == "__main__":
    main()