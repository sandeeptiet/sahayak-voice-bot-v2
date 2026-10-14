# Sahayak coding instructions

Read `technical-requirements.md` completely before designing or implementing changes. It is the project handoff; distinguish selected technologies from proposed and open decisions. Later explicit user instructions take precedence.

Preserve the documented ticket lifecycle, PostgreSQL provider portability, trusted employee identity, authorized tool execution and configurable LLM fallback. Do not copy defects from the old reference implementation.

Inspect existing code and Git changes before editing. Preserve user work. Treat `RAG-docs/` as source reference documents; do not alter originals during ingestion. Never commit `.env`, credentials or private tokens.

Validate SDK/runtime compatibility before extending the starter. Keep implementation status and unresolved decisions documented. Test business invariants and failure recovery. Do not claim mocked integrations are live-tested.

Use this directory as the application repository. The separate ChatGPT project workspace contains planning artifacts, not the application source.
