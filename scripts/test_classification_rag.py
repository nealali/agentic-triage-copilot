"""
Quick test script for Classification, RAG, and LLM features.

This script provides a simple way to test:
- Issue classification (deterministic vs LLM-required)
- RAG (keyword and semantic)
- LLM enhancement

Usage:
    python scripts/test_classification_rag.py [--base-url URL] [--api-key KEY]

Environment variables:
    LLM_ENABLED=1 - Enable LLM enhancement
    OPENAI_API_KEY=sk-... - OpenAI API key
    RAG_SEMANTIC=1 - Enable semantic RAG
    CLASSIFIER_USE_LLM_FALLBACK=1 - Enable LLM fallback for classification
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

# Add repo root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.classify.classifier import _classify_rule_based  # noqa: E402
from agent.schemas.issue import IssueCreate  # noqa: E402


def test_classification(base_url: str, api_key: str | None = None) -> None:
    """Test issue classification."""
    print("\n" + "=" * 60)
    print("TEST 1: Issue Classification")
    print("=" * 60)

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    # Test deterministic issue
    print("\n1a. Testing deterministic issue...")
    deterministic_issue = {
        "source": "edit_check",
        "domain": "AE",
        "subject_id": "SUBJ-TEST-DET",
        "fields": ["AESTDTC", "AEENDTC"],
        "description": "AE end date is before start date.",
        "evidence_payload": {"start_date": "2024-01-15", "end_date": "2024-01-10"},
    }

    # Test classification locally
    ic = IssueCreate(**deterministic_issue)
    result = _classify_rule_based(ic)
    print(f"   Local classification: {result.issue_type.value} (confidence: {result.confidence})")

    # Create via API
    with httpx.Client() as client:
        resp = client.post(f"{base_url}/issues", json=deterministic_issue, headers=headers)
        if resp.status_code == 200:
            issue = resp.json()
            print(f"   API issue_type: {issue.get('issue_type', 'N/A')}")
            print(f"   ✅ Deterministic issue created: {issue['issue_id'][:8]}...")
        else:
            print(f"   ❌ Failed to create issue: {resp.status_code} - {resp.text}")

    # Test LLM-required issue
    print("\n1b. Testing LLM-required issue...")
    llm_issue = {
        "source": "listing",
        "domain": "AE",
        "subject_id": "SUBJ-TEST-LLM",
        "fields": ["AETERM", "AESEV"],
        "description": "Complex adverse event with multiple related conditions. Requires medical review to determine if single or multiple events.",
        "evidence_payload": {},
    }

    # Test classification locally
    ic2 = IssueCreate(**llm_issue)
    result2 = _classify_rule_based(ic2)
    print(f"   Local classification: {result2.issue_type.value} (confidence: {result2.confidence})")

    # Create via API
    with httpx.Client() as client:
        resp = client.post(f"{base_url}/issues", json=llm_issue, headers=headers)
        if resp.status_code == 200:
            issue2 = resp.json()
            print(f"   API issue_type: {issue2.get('issue_type', 'N/A')}")
            print(f"   ✅ LLM-required issue created: {issue2['issue_id'][:8]}...")
        else:
            print(f"   ❌ Failed to create issue: {resp.status_code} - {resp.text}")


def test_rag(base_url: str, api_key: str | None = None) -> None:
    """Test RAG (document retrieval)."""
    print("\n" + "=" * 60)
    print("TEST 2: RAG (Document Retrieval)")
    print("=" * 60)

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    # Check if documents exist
    print("\n2a. Checking documents...")
    with httpx.Client() as client:
        resp = client.get(f"{base_url}/documents/search?q=AE", headers=headers)
        if resp.status_code == 200:
            docs = resp.json()
            print(f"   Found {len(docs)} documents matching 'AE'")
            if len(docs) == 0:
                print("   ⚠️  No documents found. Run: python scripts/ingest_mock_documents.py")
        else:
            print(f"   ❌ Failed to search documents: {resp.status_code}")

    # Create issue and analyze
    print("\n2b. Testing RAG with analysis...")
    issue_data = {
        "source": "edit_check",
        "domain": "AE",
        "subject_id": "SUBJ-RAG-TEST",
        "fields": ["AESTDTC", "AEENDTC"],
        "description": "AE end date is before start date.",
        "evidence_payload": {},
    }

    with httpx.Client() as client:
        # Create issue
        resp = client.post(f"{base_url}/issues", json=issue_data, headers=headers)
        if resp.status_code != 200:
            print(f"   ❌ Failed to create issue: {resp.status_code}")
            return
        issue = resp.json()
        issue_id = issue["issue_id"]

        # Analyze
        resp = client.post(f"{base_url}/issues/{issue_id}/analyze", headers=headers)
        if resp.status_code == 200:
            run = resp.json()
            rec = run.get("recommendation", {})
            tool_results = rec.get("tool_results", {})
            rag_method = tool_results.get("rag_method", "unknown")
            citations = rec.get("citations", [])
            citation_hits = tool_results.get("citation_hits", [])

            print(f"   RAG method: {rag_method}")
            print(f"   Citations: {len(citations)} document IDs")
            print(f"   Citation hits: {len(citation_hits)}")
            if citation_hits:
                print(f"   First citation: {citation_hits[0].get('title', 'N/A')}")
            print("   ✅ RAG test completed")
        else:
            print(f"   ❌ Failed to analyze: {resp.status_code} - {resp.text}")


def test_llm_enhancement(base_url: str, api_key: str | None = None) -> None:
    """Test LLM enhancement."""
    print("\n" + "=" * 60)
    print("TEST 3: LLM Enhancement")
    print("=" * 60)

    llm_enabled = os.getenv("LLM_ENABLED", "").strip().lower() in ("1", "true", "yes")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not llm_enabled or not openai_key:
        print("\n   ⚠️  LLM not enabled. Set LLM_ENABLED=1 and OPENAI_API_KEY")
        return

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key

    # Create LLM-required issue
    print("\n3a. Testing LLM enhancement for LLM-required issue...")
    issue_data = {
        "source": "listing",
        "domain": "AE",
        "subject_id": "SUBJ-LLM-TEST",
        "fields": ["AETERM"],
        "description": "Complex adverse event with multiple related conditions. Requires medical review.",
        "evidence_payload": {},
    }

    with httpx.Client() as client:
        # Create issue
        resp = client.post(f"{base_url}/issues", json=issue_data, headers=headers)
        if resp.status_code != 200:
            print(f"   ❌ Failed to create issue: {resp.status_code}")
            return
        issue = resp.json()
        issue_id = issue["issue_id"]
        issue_type = issue.get("issue_type", "unknown")
        print(f"   Issue type: {issue_type}")

        # Analyze (should automatically use LLM for LLM-required)
        resp = client.post(f"{base_url}/issues/{issue_id}/analyze", headers=headers)
        if resp.status_code == 200:
            run = resp.json()
            rec = run.get("recommendation", {})
            tool_results = rec.get("tool_results", {})
            llm_enhanced = tool_results.get("llm_enhanced", False)
            llm_model = tool_results.get("llm_model")

            print(f"   LLM enhanced: {llm_enhanced}")
            print(f"   LLM model: {llm_model or 'N/A'}")
            print(f"   Rationale: {rec.get('rationale', 'N/A')[:100]}...")
            if llm_enhanced:
                print("   ✅ LLM enhancement working")
            else:
                print("   ⚠️  LLM not used (check LLM_ENABLED and OPENAI_API_KEY)")
        else:
            print(f"   ❌ Failed to analyze: {resp.status_code} - {resp.text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Classification, RAG, and LLM features")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--api-key", help="API key if auth is enabled")
    args = parser.parse_args()

    print("=" * 60)
    print("Testing Classification, RAG, and LLM Features")
    print("=" * 60)
    print(f"\nAPI Base URL: {args.base_url}")
    print(f"LLM Enabled: {os.getenv('LLM_ENABLED', '0')}")
    print(f"RAG Semantic: {os.getenv('RAG_SEMANTIC', '0')}")
    print(f"Classifier LLM Fallback: {os.getenv('CLASSIFIER_USE_LLM_FALLBACK', '0')}")

    try:
        # Test classification
        test_classification(args.base_url, args.api_key)

        # Test RAG
        test_rag(args.base_url, args.api_key)

        # Test LLM enhancement
        test_llm_enhancement(args.base_url, args.api_key)

        print("\n" + "=" * 60)
        print("Testing Complete!")
        print("=" * 60)
        print("\nFor detailed testing guide, see: TESTING_CLASSIFICATION_RAG.md")
        return 0

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
