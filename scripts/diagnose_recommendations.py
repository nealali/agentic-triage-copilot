"""
Diagnostic script to check why recommendations aren't changing.

This script helps debug:
1. Whether LLM is being called
2. Whether RAG citations are being added
3. What differences exist between runs

Usage:
    python scripts/diagnose_recommendations.py <ISSUE_ID> [--base-url URL]
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


def compare_recommendations(
    run1: dict, run2: dict, label1: str = "Run 1", label2: str = "Run 2"
) -> None:
    """Compare two recommendation runs and show differences."""
    rec1 = run1.get("recommendation", {})
    rec2 = run2.get("recommendation", {})
    tool1 = rec1.get("tool_results", {})
    tool2 = rec2.get("tool_results", {})

    print("\n" + "=" * 70)
    print("COMPARISON")
    print("=" * 70)

    # Compare basic fields
    print(f"\n{label1}:")
    print(f"  Action: {rec1.get('action')}")
    print(f"  Severity: {rec1.get('severity')}")
    print(f"  Confidence: {rec1.get('confidence')}")
    print(f"  Rationale: {rec1.get('rationale', '')[:100]}...")
    print(
        f"  Draft Message: {rec1.get('draft_message', 'N/A')[:100] if rec1.get('draft_message') else 'N/A'}"
    )
    print(f"  Citations: {len(rec1.get('citations', []))}")
    print(f"  RAG Method: {tool1.get('rag_method', 'N/A')}")
    print(f"  LLM Enhanced: {tool1.get('llm_enhanced', False)}")
    if tool1.get("llm_enhanced"):
        print(f"  LLM Model: {tool1.get('llm_model', 'N/A')}")
        print(
            f"  Original Rationale: {tool1.get('llm_rationale_original', 'N/A')[:100] if tool1.get('llm_rationale_original') else 'N/A'}..."
        )

    print(f"\n{label2}:")
    print(f"  Action: {rec2.get('action')}")
    print(f"  Severity: {rec2.get('severity')}")
    print(f"  Confidence: {rec2.get('confidence')}")
    print(f"  Rationale: {rec2.get('rationale', '')[:100]}...")
    print(
        f"  Draft Message: {rec2.get('draft_message', 'N/A')[:100] if rec2.get('draft_message') else 'N/A'}"
    )
    print(f"  Citations: {len(rec2.get('citations', []))}")
    print(f"  RAG Method: {tool2.get('rag_method', 'N/A')}")
    print(f"  LLM Enhanced: {tool2.get('llm_enhanced', False)}")
    if tool2.get("llm_enhanced"):
        print(f"  LLM Model: {tool2.get('llm_model', 'N/A')}")
        print(
            f"  Original Rationale: {tool2.get('llm_rationale_original', 'N/A')[:100] if tool2.get('llm_rationale_original') else 'N/A'}..."
        )

    # Show differences
    print("\n" + "-" * 70)
    print("DIFFERENCES:")
    print("-" * 70)

    if rec1.get("rationale") != rec2.get("rationale"):
        print("✓ Rationale differs")
        print(f"  {label1}: {rec1.get('rationale', '')[:80]}...")
        print(f"  {label2}: {rec2.get('rationale', '')[:80]}...")
    else:
        print("✗ Rationale is the same")

    if rec1.get("draft_message") != rec2.get("draft_message"):
        print("✓ Draft message differs")
    else:
        print("✗ Draft message is the same")

    if rec1.get("confidence") != rec2.get("confidence"):
        print(f"✓ Confidence differs: {rec1.get('confidence')} vs {rec2.get('confidence')}")
    else:
        print("✗ Confidence is the same")

    if len(rec1.get("citations", [])) != len(rec2.get("citations", [])):
        print(
            f"✓ Citations differ: {len(rec1.get('citations', []))} vs {len(rec2.get('citations', []))}"
        )
    else:
        print("✗ Citations are the same")

    if tool1.get("rag_method") != tool2.get("rag_method"):
        print(f"✓ RAG method differs: {tool1.get('rag_method')} vs {tool2.get('rag_method')}")
    else:
        print("✗ RAG method is the same")

    if tool1.get("llm_enhanced") != tool2.get("llm_enhanced"):
        print(
            f"✓ LLM enhancement differs: {tool1.get('llm_enhanced')} vs {tool2.get('llm_enhanced')}"
        )
    else:
        print("✗ LLM enhancement status is the same")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose recommendation differences")
    parser.add_argument("issue_id", help="Issue ID to test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    args = parser.parse_args()

    print("=" * 70)
    print("RECOMMENDATION DIAGNOSTICS")
    print("=" * 70)
    print(f"\nIssue ID: {args.issue_id}")
    print(f"API URL: {args.base_url}")
    print(f"LLM Enabled: {os.getenv('LLM_ENABLED', '0')}")
    print(f"OPENAI_API_KEY: {'Set' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
    print(f"RAG Semantic: {os.getenv('RAG_SEMANTIC', '0')}")

    headers = {}

    try:
        with httpx.Client() as client:
            # Get issue details
            resp = client.get(f"{args.base_url}/issues/{args.issue_id}", headers=headers)
            if resp.status_code != 200:
                print(f"\n❌ Failed to get issue: {resp.status_code}")
                return 1
            issue = resp.json()
            print(f"\nIssue Type: {issue.get('issue_type', 'N/A')}")
            print(f"Issue Domain: {issue.get('domain', 'N/A')}")

            # Check documents
            resp = client.get(
                f"{args.base_url}/documents/search?q={issue.get('domain', 'AE')}", headers=headers
            )
            if resp.status_code == 200:
                docs = resp.json()
                print(f"Documents available: {len(docs)}")
            else:
                print("⚠️  Could not check documents")

            # Run 1: Deterministic only (no LLM, keyword RAG)
            print("\n" + "=" * 70)
            print("RUN 1: Deterministic + Keyword RAG (no LLM)")
            print("=" * 70)
            resp = client.post(
                f"{args.base_url}/issues/{args.issue_id}/analyze",
                json={"use_llm": False, "use_semantic_rag": False},
                headers=headers,
            )
            if resp.status_code != 200:
                print(f"❌ Failed to analyze: {resp.status_code} - {resp.text}")
                return 1
            run1 = resp.json()

            # Run 2: With LLM (if enabled)
            if os.getenv("OPENAI_API_KEY"):
                print("\n" + "=" * 70)
                print("RUN 2: Deterministic + Keyword RAG + LLM")
                print("=" * 70)
                resp = client.post(
                    f"{args.base_url}/issues/{args.issue_id}/analyze",
                    json={"use_llm": True, "use_semantic_rag": False},
                    headers=headers,
                )
                if resp.status_code != 200:
                    print(f"❌ Failed to analyze: {resp.status_code} - {resp.text}")
                    return 1
                run2 = resp.json()

                compare_recommendations(run1, run2, "Without LLM", "With LLM")
            else:
                print("\n⚠️  OPENAI_API_KEY not set, skipping LLM comparison")

            # Run 3: Semantic RAG (if enabled)
            if os.getenv("RAG_SEMANTIC", "").strip().lower() in ("1", "true", "yes"):
                print("\n" + "=" * 70)
                print("RUN 3: Deterministic + Semantic RAG")
                print("=" * 70)
                resp = client.post(
                    f"{args.base_url}/issues/{args.issue_id}/analyze",
                    json={"use_llm": False, "use_semantic_rag": True},
                    headers=headers,
                )
                if resp.status_code != 200:
                    print(f"❌ Failed to analyze: {resp.status_code} - {resp.text}")
                    return 1
                run3 = resp.json()

                compare_recommendations(run1, run3, "Keyword RAG", "Semantic RAG")

        print("\n" + "=" * 70)
        print("DIAGNOSTICS COMPLETE")
        print("=" * 70)
        print("\nIf recommendations are identical:")
        print("1. Check OPENAI_API_KEY is set for LLM enhancement")
        print("2. Check documents are ingested: python scripts/ingest_mock_documents.py")
        print("3. Check LLM actually enhanced (look for 'llm_enhanced: true' in tool_results)")
        print("4. Check rationale and draft_message fields (not just action/severity)")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
