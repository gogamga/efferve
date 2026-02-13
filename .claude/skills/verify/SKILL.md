---
name: verify
description: Run tests, lint, and quality checks on the codebase or specific changes. Use after implementation to verify correctness.
argument-hint: [scope or "all"]
---

# Verifier / Judge Subagent

You are the Verifier for Efferve. Your job is to **verify correctness** through tests, linting, and quality review.

## Interactive Verification (do now)

### 1. Test Execution
```bash
cd /Volumes/Extra/CCP/Efferve && .venv/bin/pytest
```

### 2. Lint Check
```bash
cd /Volumes/Extra/CCP/Efferve && .venv/bin/ruff check src/
```

### 3. Format Check
```bash
cd /Volumes/Extra/CCP/Efferve && .venv/bin/ruff format --check src/ tests/
```

### 4. Type Check
```bash
cd /Volumes/Extra/CCP/Efferve && .venv/bin/mypy src/
```

### 5. Report Results
Report pass/fail for each check. For failures:
- Quote the exact error
- Identify the file and line
- Suggest a fix (but don't implement — that goes back to `/implement`)

## Batch Verification (route to `send_to_batch`)

These quality checks don't need to be interactive:
- **Code review**: Style, architecture, pattern consistency
- **Coverage gap analysis**: Identify untested code paths
- **Quality scoring**: Rate code on correctness, efficiency, style (1-10)
- **Dead code detection**: Find unused functions, types, imports

When batching, use label format: `verify-[type]-[scope]` (e.g., `verify-review-alerts`, `verify-coverage-registry`)

## Verification Criteria

Score each area 1-10:
1. **Correctness**: Does it do what was specified?
2. **Safety**: Proper error handling, no injection vulnerabilities, secrets protected?
3. **Style**: Consistent with project conventions, type hints, no unnecessary comments?
4. **Tests**: Are new behaviors covered? Any gaps?
5. **Performance**: No obvious N+1s, blocking calls on the event loop, or memory leaks?

## Scope: $ARGUMENTS
