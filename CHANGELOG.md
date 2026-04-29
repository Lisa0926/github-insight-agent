## [unreleased]

### Added

- Complete multiple P1/P2 features (Sprint 3-6)
- *(tools)* Integrate OWASP Top 10 security rules for PR review
- *(cli)* Enhance CLI with colorful output and better UX
- *(agents)* Add LLM intent understanding to ResearcherAgent (5 tool types: search/get_repo/analyze/compare/chat)
- *(agents)* Add `INTENT_TOOLS` function calling definitions and `INTENT_SYSTEM_PROMPT` for LLM-based intent routing
- *(agents)* Add `_execute_search()`, `_execute_get_repo_info()`, `_execute_analyze_project()`, `_execute_compare()` methods
- *(core)* Add `studio_integration.py` — AgentScope official Studio integration via `agent.print()` hook
- *(cli)* Add `_setup_studio()` using `agentscope.init()` for official Studio hooks and tracing
- *(cli)* Add `_push_to_studio()` for unified CLI→Studio message push (ensures content consistency)
- *(workflows)* Add intent routing in `ReportGenerator._answer_followup()` for tool-augmented followup handling
- *(core)* Add per-db_path singleton cache for `PersistentMemory` (fixes connection contention)
- *(tools)* Add null-content guard in `GitHubTool._clean_content()`
- *(test)* Add `test_mission_part3.py` with 18 tests for intent tools, execution methods, Studio integration
- *(test)* Add `test_mission_part2.py` for additional test coverage
- *(ci)* Add CI workflow and wechat contextToken auto-renewal
- *(agents)* Create GiaAgentBase as shared base class for all agents
- *(workflows)* Add AgentPipeline with AgentScope SequentialPipeline orchestration
- *(core)* Add DashScopeWrapper for synchronous LLM calls
- *(api)* Add GIA_DASHSCOPE_API_KEY for isolated model key from Claude Code
- *(security)* Add secret scan script for CI pipeline (scans tracked files for hardcoded secrets)
- *(config)* Add .env.sample as configuration template with placeholders
- *(security)* Add hardcoded model name detection to secret scanner

### Changed

- *(mcp)* Rename src/mcp to src/github_mcp to avoid package conflict
- *(agents)* Migrate ResearcherAgent and AnalystAgent from plain classes to AgentScope AgentBase
- *(llm)* Unify LLM calls from direct dashscope.Generation.call() to DashScopeWrapper
- *(docs)* Update architecture diagram with AgentPipeline and DashScopeWrapper
- *(docs)* Translate all developer comments and docstrings to English
- *(docs)* Move internal docs (migration plan, pre-commit hooks, mission) to internal/ directory
- *(fix)* Handle ChatResponse as dict subclass in _extract_response_text()
- *(security)* Remove hardcoded local paths from tracked files (githooks/README.md, MISSION.md, start_cli.sh, ci.yml)
- *(fix)* Update test assertions for English-translated compressed summary header
- *(test)* Fix agent integration test to avoid async reply() method (AgentScope hooks)
- *(security)* Replace all hardcoded model names with DASHSCOPE_MODEL env var
- *(docs)* Remove Web UI references from architecture diagram (no web UI implemented yet)
- *(cli)* Refactor Studio integration: use `agentscope.init()` + official `pre_print` hook
- *(cli)* Unify Studio message push at CLI layer via `_push_to_studio()`
- *(agents)* Remove `_forward_to_studio()` from `GiaAgentBase`
- *(cli)* Fix `CommandCompleter` NameError when `prompt_toolkit` is not installed
- *(workflows)* `ReportGenerator._answer_followup()` routes through LLM intent understanding
- *(core)* `PersistentMemory` now caches per `db_path`
- *(fix)* Remove duplicate `import os` in dashscope_wrapper.py
- *(fix)* Use `DASHSCOPE_MODEL` env var fallback in DashScopeProvider

### Removed

- *(cli)* Remove start_cli.sh (redundant with run_cli.py and gia entry point)
- *(docs)* Remove Web UI from architecture diagrams
- *(security)* Remove hardcoded API key from .claude/settings.local.json

### Chore

- Add .env.sample as config template and remove from .gitignore
- Add .hermes/ to .gitignore (entire directory)
- Remove .hermes/archive/ from git tracking
- Remove .env.sample from repo
- Add .env.sample to .gitignore and add missing files
- Update commit-msg hook to English
- Add report/ to .gitignore for internal docs

### Documentation

- Update README with cleaner structure
- Add meta-analysis report for github-insight-agent project
- Remove internal reports from repository
- *(githooks)* Update commit-msg hook to enforce English messages
- *(githooks)* Add README with hook documentation
