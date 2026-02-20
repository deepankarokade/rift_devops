# CI/CD Healer Pipeline Flow

## Overview
The autonomous CI/CD pipeline healer automatically detects, diagnoses, and fixes test failures in your repository.

## Complete Workflow

### 1. Clone Repository
- Clones the target repository to a local temp directory
- **NEW**: Automatically creates a default GitHub Actions workflow if none exists
- This ensures CI monitoring will work even for repos without existing workflows

### 2. Run Tests Locally
- Executes pytest in a Docker sandbox
- Parses test output for failures
- Routes based on results:
  - **Tests Pass (iteration 0)**: → Monitor CI
  - **Tests Pass (iteration > 0)**: → Commit & Push (fix was applied)
  - **Tests Fail**: → Classify Failures

### 3. Failure Classification (if tests fail)
- Uses AI (Groq) to classify failures into categories:
  - LINTING
  - SYNTAX
  - LOGIC
  - TYPE_ERROR
  - IMPORT
  - INDENTATION

### 4. Fix Generation
- AI generates code fixes based on classified failures
- Reads the actual file content
- Generates corrected version
- Writes fix back to the file

### 5. Fix Validation
- Performs AST syntax validation on generated fixes
- Ensures fixes are syntactically correct before committing

### 6. Git Commit
- Commits fixes with `[AI-AGENT]` prefix
- Auto-creates feature branch if on protected branch (main/master)
- Branch naming: `TEAM_NAME_LEADER_NAME_AI_Fix`

### 7. Push to Remote
- Pushes the feature branch to GitHub
- Triggers CI workflow run

### 8. Monitor CI
- **NEW**: Checks if `.github/workflows` exists
- **NEW**: Skips monitoring if no workflows or no GitHub token
- Polls GitHub Actions API for workflow status
- Routes based on CI result:
  - **CI Passes**: → END (success!)
  - **CI Fails**: → Retry Decision

### 9. Retry Decision
- **NEW**: If no local failures but CI failed:
  - Fetches CI logs from GitHub Actions API
  - Parses logs to extract failures
  - Creates synthetic failure entries
- Checks retry limit (default: 3 attempts)
- Routes based on decision:
  - **Should Retry**: → Run Tests (loop back)
  - **Max Retries Exceeded**: → END (failed)

## Key Improvements

### 1. Workflow File Auto-Creation
```yaml
# Automatically created if missing
.github/workflows/ci.yml
```
- Supports Python projects
- Runs pytest on push to AI_Fix branches
- Installs dependencies from requirements.txt

### 2. CI Log Fetching
When local tests pass but CI fails:
- Fetches complete logs from all CI jobs
- Parses for error patterns: `file:line: error`
- Creates actionable failure entries

### 3. Graceful Degradation
- No workflows? → Marks as passed, continues
- No GitHub token? → Marks as passed, continues
- Can't fetch CI logs? → Reports failure, doesn't crash

## Environment Variables Required

```bash
GITHUB_TOKEN=ghp_xxxxx  # For CI monitoring and log fetching
GROQ_API_KEY=gsk_xxxxx  # For AI classification and fix generation
```

## Example Run

```
1. Clone repo → ✓
2. Run tests → ✓ (pass locally)
3. Monitor CI → ✗ (fail on GitHub)
4. Retry decision → Fetch CI logs
5. Parse failures → Found 2 errors
6. Classify → SYNTAX, IMPORT
7. Generate fixes → 2 fixes created
8. Validate → All valid
9. Commit → [AI-AGENT] Auto-fix iteration 1
10. Push → Branch: TEAM_PADY_PARTH_SARODE_AI_Fix
11. Monitor CI → ✓ (pass!)
12. END → Success!
```

## Troubleshooting

### "No local reproducible failures"
- **Fixed**: System now fetches CI logs when this happens
- Parses CI output to find actual failures
- Creates synthetic failures for fix generation

### "Pipeline stops after cloning"
- **Fixed**: Added workflow auto-creation
- Added graceful handling when no CI configured
- System continues even without GitHub Actions

### "Tests pass locally but fail in CI"
- **Expected**: Different environments (Docker vs GitHub Actions)
- **Solution**: CI log fetching captures environment-specific failures
- System generates fixes based on actual CI errors
