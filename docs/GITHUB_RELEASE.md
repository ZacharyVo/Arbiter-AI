# GitHub repository presentation — PluralForge AI v0.4

**Repository name:** `pluralforge-ai`

**About description:**
> Open-source cost-aware collective intelligence for AI agents: generate new ideas, preserve dissent, and optimize when to think, retrieve, or stop.

**Topics:**
`multi-agent` `ai-agents` `collective-intelligence` `brainstorming` `decision-optimization` `llm` `mcp` `value-of-information` `python` `benchmarking`

**Tag suggestion:** `v0.4.0` — Research MVP, not production software.

## Migration from Arbiter AI Collaborative v0.3

1. Replace the root README and copy the new `pluralforge/` directory and modified `arbiter_plugin/` files.
2. Replace `pyproject.toml` and keep your old `arbiter_plugin` imports if desired. New examples use `from pluralforge import ...`.
3. Replace/update `docs/` and `benchmarks/`, then run `python -m pytest` and `python -m benchmarks.compare_policies`.
4. The PyPI/distribution project name is now `pluralforge-ai`, but no publication to PyPI is claimed.
5. GitHub Pages can publish the static page from `/docs`. Do not expose the unauthenticated FastAPI demo to the Internet.
6. If renaming an existing GitHub repository, check links/automation and update any external imports in consumer code.

## Release summary

- Next-action choices: `consult_agent`, `discuss_all`, `retrieve`, `stop`
- Input-grounded net information value with explicit USD cap and agent reservations
- External retrieval observations and durable dissent / idea lineage
- Surface-form similarity flags without deleting candidate ideas
- Synthetic cross-domain comparative harness + real benchmark protocol
- Backwards-compatible Python imports, local HTTP endpoint and optional MCP tool

**Known limits:** No trained VoI predictor; no proof of real-model improvement; no live MCP/paid LLM verification; no hosted plugin publication. API USD cost reservations are not a provider hard cap.
