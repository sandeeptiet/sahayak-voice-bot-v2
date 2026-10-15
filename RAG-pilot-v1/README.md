# Sahayak RAG pilot - synthetic draft v1.0

Three focused sample articles, one per PDF. No employee data or real company policy is included. Originals in RAG-docs are unchanged. This folder is a proposed ingestion set, not an already configured Bedrock data source.

## Scope
- SAH-NET-001: safe network triage.
- SAH-M365-001: distinguish Outlook desktop failure from a webmail workaround.
- SAH-VPN-001: evidence collection and handoff; no invented VPN error-code fixes.

Do not ingest the original ten volumes alongside these files: duplicates and generic sample policies would weaken the pilot. HR, company policies, account recovery, software installation and hardware repair are outside this initial set. They can be added later as reviewed articles.

Only the three PDF files belong in the pilot ingestion prefix. Keep this README, manifest and retrieval checks outside that prefix. Stable IDs, versions and categories are recorded in manifest.json; access controls must be implemented by the retrieval service, not inferred from PDF labels.

## Acceptance and limits
Review the PDF content before using it as demo knowledge. Synthetic material is not production-approved guidance. Retrieved text remains data, never an instruction that overrides the agent's authorization or safety rules. Completion requires employee confirmation; a temporary workaround is not automatically a completed ticket. Handoff mutations still require the authoritative ticket state and allowed lifecycle transition.

retrieval-checks.json contains candidate English/Hindi/Hinglish checks and negative cases. They have not been executed. Evaluate retrieval and answer behavior separately; do not claim multilingual accuracy or autonomous resolution from these documents alone.

## Next infrastructure work
Verify region, embeddings, S3 Vectors support and costs before provisioning. Configure a dedicated S3 PDF prefix, explicit ingestion, retrieval filtering and provenance. No upload, Knowledge Base, vector index or paid request was created by preparing these files.
