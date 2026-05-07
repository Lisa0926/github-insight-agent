## [unreleased]

### Added

- Complete P0/P1/P2 improvements from ADLC 2.0 assessment
- *(core)* BaseTool ABC — unified tool protocol with get_name/get_description/execute/validate_input
- *(core)* Token utilities — count_tokens, truncate_to_tokens, estimate_messages_tokens using tiktoken
- *(core)* Half-open circuit breaker for HTTP and Agent circuit breakers
- *(core)* Cross-session memory — CLI startup auto-loads recent conversation summary
- *(core)* Feedback→prompt injection — extract positive feedback patterns for system prompt personalization
- *(mcp)* MCP connection robustness — get_available_tools(), connect_with_retry(), result caching
- *(tools)* Orphan tool registration — evaluate_code_quality, scan_security_code, review_code_changes
- *(tools)* Pydantic-to-AgentScope ToolResponse adaptation layer
- *(agents)* Dynamic intent prompt from toolkit schemas instead of hardcoded INTENT_TOOLS
- *(agents)* LLM-based conversation summarization with rule-based fallback
- *(agents)* Token budget management — _build_messages_with_token_budget() integrated into researcher agent
- *(cli)* Cross-session memory display at startup

### CI/CD

- Add test diagnostics for debugging CI failures

### Changed

- *(mcp)* Rename src/mcp to src/github_mcp to avoid package conflict
- Upgrade to AgentScope multi-agent system and translate comments

### Chore

- Remove .env.sample from repo
- Add .env.sample to .gitignore and add missing files
- Update commit-msg hook to English
- Add report/ to .gitignore for internal docs
- Remove redundant CHANGELOG_AUTO.md documentation
- Add hermes files to gitignore
- Remove wechat token renewal script references
- Update .gitignore for Hermes task files
- Remove redundant start_cli.sh script

### Documentation

- Update README with cleaner structure
- Add meta-analysis report for github-insight-agent project
- Remove internal reports from repository
- *(githooks)* Update commit-msg hook to enforce English messages
- *(githooks)* Add README with hook documentation
- Add architecture documentation and fix cross-project references
- Remove local path exposure and cross-project references
- Add pre-commit hooks usage guide
- Add pre-commit hooks link to README
- Remove redundant documentation
- Reorganize documentation structure
- Update user guide with natural language interaction
- Add virtual environment usage guide

### Fixed

- Parse natural language queries to GitHub Search syntax
- Parse natural language queries with time range support
- *(ci)* Resolve flake8 lint errors for CI pipeline
- Correct ReportGenerator import path
- Add fastapi dependency for test requirements
- Add pytest-asyncio dependency for async tests
- Syntax error in OWASP security rules A07_AUTH_FAILURE enum
- Resolve CI test failures and reorganize internal docs
- Remove unnecessary global declaration in get_persistent_memory
- Resolve P0+P1 issues from Hermes ADLC 2.0 assessment
- Add missing markdown dependency to requirements.txt
- Resolve CI pipeline failures

### Security

- Remove sensitive paths, add secret scan, create .env.sample
- Use DASHSCOPE_MODEL env var, remove hardcoded model names

### Testing

- Add mission supplement test file

### Hooks

- Add local path exposure detection to pre-commit
