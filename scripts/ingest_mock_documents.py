"""
Ingest mock guidance documents for RAG testing.

This script creates sample documents that align with common issue types:
- AE date checks
- Missing field guidance
- Out of range value handling
- Duplicate record procedures
- Query writing best practices

Usage:
    python scripts/ingest_mock_documents.py [--base-url URL] [--api-key KEY]

If auth is enabled, pass --api-key. Otherwise, documents are ingested without auth.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

# Add repo root to path so we can import agent modules
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MOCK_DOCUMENTS = [
    {
        "title": "AE Date Consistency Checks - Data Review Plan",
        "source": "DRP",
        "tags": ["AE", "date", "consistency", "edit_check", "timeline"],
        "content": """Adverse Event Date Consistency Guidelines

All adverse events must have valid start and end dates. The following checks apply:

1. AESTDTC (AE Start Date) must be present for all adverse events.
2. AEENDTC (AE End Date) should be present if the event has resolved or ended.
3. AEENDTC must be on or after AESTDTC. If AEENDTC is before AESTDTC, this is a critical data quality issue that requires site query.
4. Timeline conflicts: If AE dates conflict with other records (e.g., hospitalization dates, medication start dates), reconciliation is required.

Query Template (date inconsistency):
"Subject [SUBJECT_ID]: The adverse event [AETERM] shows an end date ([AEENDTC]) that is before the start date ([AESTDTC]). Please review and provide corrected dates or confirm if this is a data entry error."

Query Template (timeline conflict):
"Subject [SUBJECT_ID]: The adverse event [AETERM] start date ([AESTDTC]) conflicts with [CONFLICTING_RECORD] ([CONFLICT_DATE]). Please review and reconcile the dates or provide clarification on the timeline."

Severity: HIGH
Action: QUERY_SITE
Confidence: High when dates are clearly inconsistent or conflict with other records.""",
    },
    {
        "title": "Missing Critical Fields - SDTM Compliance",
        "source": "SDTM_Guide",
        "tags": ["missing", "required", "SDTM", "compliance"],
        "content": """SDTM Required Fields for Adverse Events

Per SDTM Implementation Guide, the following fields are REQUIRED for all adverse events in the AE domain:

- AETERM: Adverse event term (verbatim or MedDRA preferred term)
- AESTDTC: Start date/time
- AESER: Seriousness indicator (Y/N) - REQUIRED for all serious AEs
- AEOUT: Outcome (RECOVERED/RECOVERING/RECOVERED WITH SEQUELAE/FATAL/UNKNOWN) - REQUIRED for resolved events

If AESER is missing for a serious adverse event, or AEOUT is missing for a resolved event, this is a compliance issue.

Query Template:
"Subject [SUBJECT_ID]: The adverse event [AETERM] is missing required field(s): [FIELD_LIST]. Please provide the missing information per SDTM requirements."

Severity: MEDIUM
Action: DATA_FIX or QUERY_SITE depending on whether the information is available in source documents.""",
    },
    {
        "title": "Out of Range Laboratory Values - Clinical Significance",
        "source": "Lab_Review_SOP",
        "tags": ["LB", "out_of_range", "laboratory", "clinical"],
        "content": """Laboratory Value Out of Range Handling

When laboratory values fall outside normal reference ranges:

1. Flag for medical review if:
   - Values are significantly outside range (e.g., >3x upper limit or <0.3x lower limit)
   - Values are critical (e.g., hemoglobin <7 g/dL, platelets <50,000)
   - Pattern suggests clinical concern (e.g., trending upward/downward)

2. Query site if:
   - Value seems implausible (e.g., temperature >45°C)
   - Unit conversion error suspected
   - Value conflicts with other clinical data

3. Accept as-is if:
   - Value is slightly outside range and clinically insignificant
   - Medical review confirms no action needed

Query Template:
"Subject [SUBJECT_ID]: Laboratory value [LBORRES] for [LBTESTCD] is outside the normal range ([LBORNRLO] - [LBORNRHI]). Please confirm this value is correct and provide clinical context if available."

Severity: MEDIUM to HIGH depending on magnitude
Action: MEDICAL_REVIEW or QUERY_SITE""",
    },
    {
        "title": "Duplicate Record Detection and Resolution",
        "source": "Data_Quality_SOP",
        "tags": ["duplicate", "deduplication", "data_quality"],
        "content": """Duplicate Record Handling Procedures

Duplicate records can occur due to:
- Multiple data entry attempts
- System synchronization issues
- Manual corrections creating duplicates

Detection Criteria:
- Same subject ID
- Same domain
- Same date/time (or within 24 hours)
- Same or very similar values

Resolution Steps:
1. Identify which record is the "source of truth" (most complete, most recent, or from primary source)
2. Mark duplicate records for deletion or flag as "duplicate of [RECORD_ID]"
3. Document resolution in audit trail

Query Template (if site confirmation needed):
"Subject [SUBJECT_ID]: Potential duplicate records detected in [DOMAIN] domain for date [DATE]. Please confirm if these are duplicates or separate events and provide clarification."

Severity: LOW to MEDIUM
Action: DATA_FIX (if clearly duplicate) or QUERY_SITE (if confirmation needed)""",
    },
    {
        "title": "Vital Signs Out of Range - Protocol Deviation",
        "source": "VS_Review_Guide",
        "tags": ["VS", "vital_signs", "out_of_range", "protocol"],
        "content": """Vital Signs Out of Range Assessment

Vital signs that fall outside expected ranges require assessment:

Normal Ranges (adults):
- Systolic BP: 90-140 mmHg
- Diastolic BP: 60-90 mmHg
- Heart Rate: 60-100 bpm
- Temperature: 36.1-37.2°C (97-99°F)
- Respiratory Rate: 12-20 breaths/min

Actions:
- Values significantly outside range: Query site for confirmation and clinical context
- Values slightly outside range: May be acceptable with medical review
- Implausible values (e.g., HR >220, temp >43°C): Query site immediately

Query Template:
"Subject [SUBJECT_ID]: Vital sign [VSTESTCD] value [VSORRES] recorded on [VSDTC] is outside the expected range. Please confirm this value is correct and provide any relevant clinical context."

Severity: MEDIUM
Action: QUERY_SITE or MEDICAL_REVIEW""",
    },
    {
        "title": "Query Writing Best Practices",
        "source": "Query_SOP",
        "tags": ["query", "communication", "site", "best_practices"],
        "content": """Site Query Writing Guidelines

Effective site queries should be:
1. Clear and specific: State exactly what needs clarification
2. Professional and courteous: Maintain collaborative tone
3. Actionable: Request specific information or correction
4. Contextual: Include relevant subject/visit/domain information

Query Structure:
- Subject ID and visit/date context
- Specific field(s) or value(s) in question
- What information is needed or what correction is requested
- Deadline if applicable

Example:
"Subject 1001, Visit 3 (2024-03-15): The adverse event 'Headache' shows an end date (2024-03-10) that is before the start date (2024-03-12). Please review and provide corrected dates or confirm if this is a data entry error. Response requested by [DATE]."

Avoid:
- Vague requests ("Please review")
- Accusatory language
- Requests for information not available to site
- Multiple unrelated issues in one query""",
    },
    {
        "title": "Incomplete Date Handling",
        "source": "Date_Standards",
        "tags": ["date", "incomplete", "partial", "SDTM"],
        "content": """Incomplete or Partial Date Handling

SDTM allows partial dates (e.g., YYYY-MM for month/year only, YYYY for year only) when:
- Exact date is unknown
- Date is estimated
- Source document only provides partial information

However, for critical dates (e.g., AE start/end, visit dates), complete dates are preferred.

If a partial date is provided:
- Accept if documented as "unknown" or "estimated" in source
- Query if complete date should be available from source documents
- Flag for medical review if partial date impacts analysis

Query Template:
"Subject [SUBJECT_ID]: The date field [FIELD] contains a partial date ([VALUE]). Please confirm if a complete date is available in source documents or if this partial date is appropriate per protocol."

Severity: LOW to MEDIUM
Action: QUERY_SITE or ACCEPT if documented appropriately""",
    },
    {
        "title": "Unit Conversion and Consistency",
        "source": "Units_SOP",
        "tags": ["units", "conversion", "consistency", "measurement"],
        "content": """Unit Conversion and Consistency Guidelines

All measurements must use consistent units throughout a study:
- Weight: kg (preferred) or lb (must be consistent)
- Temperature: Celsius (preferred) or Fahrenheit (must be consistent)
- Blood pressure: mmHg
- Laboratory values: Per protocol-specified units

Common Issues:
- Mixed units (e.g., some weights in kg, others in lb)
- Missing unit specification
- Incorrect unit conversion

Resolution:
- Standardize to protocol-specified units
- Query site if unit conversion is needed
- Document unit conversion in audit trail

Query Template:
"Subject [SUBJECT_ID]: Inconsistent units detected for [FIELD]. Values appear to be in both [UNIT1] and [UNIT2]. Please confirm and standardize to [PROTOCOL_UNIT] per protocol requirements."

Severity: MEDIUM
Action: DATA_FIX or QUERY_SITE""",
    },
    {
        "title": "Visit Date Protocol Window Validation",
        "source": "Protocol_Compliance",
        "tags": ["DM", "visit", "date", "protocol", "window", "compliance", "schedule"],
        "content": """Visit Date Protocol Window Validation Guidelines

All visit dates must fall within protocol-defined windows to ensure proper study conduct and data integrity.

Protocol Window Requirements:
- Each visit has a defined window (e.g., Visit 2: Day 14 ± 3 days)
- Visit dates outside the protocol window may indicate:
  * Scheduling errors
  * Protocol deviations
  * Data entry errors
  * Unplanned visits

Assessment Criteria:
1. Check if visit date falls within protocol-defined window
2. Determine if deviation is acceptable (e.g., documented reason, minor deviation)
3. Flag for medical review if:
   - Deviation is significant (>50% of window)
   - No documented reason provided
   - Pattern suggests systematic issue
4. Query site if:
   - Date appears incorrect (e.g., future date, before previous visit)
   - No documentation explaining deviation
   - Deviation impacts protocol compliance

Query Template:
"Subject [SUBJECT_ID]: Visit [VISIT] date [VISIT_DATE] falls outside the protocol-defined window ([WINDOW_START] to [WINDOW_END]). Please confirm this date is correct and provide documentation for the protocol deviation if applicable."

Severity: LOW to MEDIUM
Action: MEDICAL_REVIEW or QUERY_SITE depending on magnitude and documentation
Confidence: Low when insufficient context about protocol window or deviation reason""",
    },
    {
        "title": "Laboratory Value Discrepancy - EDC vs Central Lab",
        "source": "Lab_Reconciliation_SOP",
        "tags": ["LB", "discrepancy", "central_lab", "EDC", "reconciliation", "clinical"],
        "content": """Laboratory Value Discrepancy Handling: EDC vs Central Lab

When EDC (Electronic Data Capture) values differ from central lab results:

1. Assess the magnitude of discrepancy:
   - Small differences (<5-10%) may be due to rounding or timing
   - Larger differences require investigation
   - Critical values require immediate attention

2. Consider clinical significance:
   - If LBCLSIG=Y (clinically significant), medical review is required
   - If discrepancy changes interpretation, query site
   - If both values are within normal range, may be acceptable

3. Common causes:
   - Different collection times
   - Unit conversion errors
   - Data entry errors
   - Sample handling differences

4. Resolution steps:
   - Query site for clarification if discrepancy is significant
   - Request source documentation (lab reports)
   - Flag for medical review if clinical significance unclear
   - Document reconciliation in audit trail

Query Template:
"Subject [SUBJECT_ID]: Laboratory value [LBORRES] for [LBTESTCD] recorded in EDC ([EDC_VALUE]) differs from central lab result ([CENTRAL_LAB_VALUE]). The discrepancy is [MAGNITUDE] and marked as clinically significant (LBCLSIG=Y). Please review source documentation and provide clarification on which value should be used, or confirm if both values are valid from different collection times."

Severity: MEDIUM to HIGH depending on magnitude and clinical significance
Action: MEDICAL_REVIEW or QUERY_SITE""",
    },
    {
        "title": "Complex Adverse Events - Multiple Related Conditions",
        "source": "AE_Medical_Review_Guide",
        "tags": ["AE", "complex", "multiple", "related", "medical_review", "grouping"],
        "content": """Complex Adverse Events: Handling Multiple Related Conditions

When an adverse event involves multiple symptoms or conditions, determine if they represent:
- A single adverse event (grouped)
- Multiple separate adverse events (ungrouped)

Assessment Criteria:
1. Temporal relationship: Do symptoms occur at the same time or sequentially?
2. Causal relationship: Are symptoms likely related to the same underlying cause?
3. Severity: Does grouping affect severity assessment?
4. Reporting requirements: Does protocol require separate reporting?

Common Scenarios:
- Headache, Nausea, Dizziness: Often grouped as single event if occurring together
- Sequential symptoms: May be separate events if they develop over time
- Related to same intervention: Usually grouped
- Different body systems: May be separate events

Resolution:
1. Medical review required to determine appropriate grouping
2. Query site if source documentation is unclear
3. Follow MedDRA grouping guidelines
4. Document decision in audit trail

Query Template:
"Subject [SUBJECT_ID]: Multiple symptoms/conditions reported for adverse event: [SYMPTOM_LIST]. Please clarify if these represent a single adverse event or multiple separate events. If grouped, please provide a single preferred term. If separate, please provide individual preferred terms for each."

Severity: MEDIUM
Action: MEDICAL_REVIEW (required for proper classification)""",
    },
    {
        "title": "Uncommon Data Quality Issue - No Standard Guidance",
        "source": "General_Data_Quality",
        "tags": ["general", "uncommon", "case_by_case"],
        "content": """This document is intentionally minimal to test system behavior when no specific guidance is available.

For uncommon or novel data quality issues without specific guidance:
- Manual review is required
- Case-by-case assessment
- Document decision rationale

This document should NOT match most issues to test the "no guidance found" scenario.""",
    },
]


def ingest_documents(base_url: str = "http://localhost:8000", api_key: str | None = None) -> None:
    """Ingest all mock documents via the API."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    client = httpx.Client(base_url=base_url, headers=headers, timeout=30.0)

    print(f"Ingesting {len(MOCK_DOCUMENTS)} mock documents to {base_url}...")
    print()

    created = []
    errors = []

    for i, doc_create in enumerate(MOCK_DOCUMENTS, 1):
        try:
            resp = client.post("/documents", json=doc_create)
            if resp.status_code == 200:
                doc = resp.json()
                created.append(doc["doc_id"])
                print(f"✓ [{i}/{len(MOCK_DOCUMENTS)}] {doc_create['title']}")
            elif resp.status_code == 401:
                print(
                    f"✗ [{i}/{len(MOCK_DOCUMENTS)}] Authentication required. Set --api-key or disable auth."
                )
                errors.append(f"{doc_create['title']}: Auth required")
                break
            else:
                error_msg = resp.text
                try:
                    error_json = resp.json()
                    if "detail" in error_json:
                        error_msg = error_json["detail"]
                except Exception:
                    pass
                print(
                    f"✗ [{i}/{len(MOCK_DOCUMENTS)}] {doc_create['title']}: {resp.status_code} - {error_msg}"
                )
                errors.append(f"{doc_create['title']}: {error_msg}")
        except Exception as e:
            print(f"✗ [{i}/{len(MOCK_DOCUMENTS)}] {doc_create['title']}: {e}")
            errors.append(f"{doc_create['title']}: {e}")

    print()
    print(f"Created: {len(created)}")
    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors:
            print(f"  - {err}")

    if created:
        print()
        print("Document IDs created:")
        for doc_id in created:
            print(f"  - {doc_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest mock guidance documents for RAG testing")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument("--api-key", help="API key (required if AUTH_ENABLED=1)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print documents that would be ingested without POSTing",
    )

    args = parser.parse_args()

    if args.dry_run:
        print(f"Would ingest {len(MOCK_DOCUMENTS)} documents:")
        print()
        for i, doc in enumerate(MOCK_DOCUMENTS, 1):
            print(f"{i}. {doc['title']}")
            print(f"   Source: {doc['source']}")
            print(f"   Tags: {', '.join(doc['tags'])}")
            print(f"   Content: {doc['content'][:100]}...")
            print()
        return

    ingest_documents(base_url=args.base_url, api_key=args.api_key)


if __name__ == "__main__":
    main()
