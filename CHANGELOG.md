## [unreleased]

### Added

- Complete multiple P1/P2 features (Sprint 3-6)
- *(tools)* Integrate OWASP Top 10 security rules for PR review
- *(cli)* Enhance CLI with colorful output and better UX
- *(ci)* Add CI workflow and wechat contextToken auto-renewal
- *(agents)* Create GiaAgentBase as shared base class for all agents
- *(workflows)* Add AgentPipeline with AgentScope SequentialPipeline orchestration
- *(core)* Add DashScopeWrapper for synchronous LLM calls
- *(api)* Add GIA_DASHSCOPE_API_KEY for isolated model key from Claude Code
- *(security)* Add secret scan script for CI pipeline (scans tracked files for hardcoded secrets)
- *(config)* Add .env.sample as configuration template with placeholders

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
