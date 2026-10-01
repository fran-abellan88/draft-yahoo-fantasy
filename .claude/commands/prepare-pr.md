# Prepare Pull Request Description

Generate a concise PR title and description based on recent commits in the current branch.

## Workflow

1. **Detect Branch Information**
   - Get current branch name: `git rev-parse --abbrev-ref HEAD`
   - Detect base branch (where current branch diverged from):
     - Try `main` first
     - If not, try `develop`, `beta`, `master`
     - Use `git merge-base` to find divergence point
   - Get list of commits since divergence: `git log base-branch..current-branch --oneline`

2. **Analyze Commits**
   - Read all commit messages from the divergence point
   - Use `git diff base-branch..current-branch --stat` to see file changes
   - Understand the overall scope and purpose of changes
   - Identify key features, fixes, or improvements

3. **Generate PR Title**
   - Create a clear, concise title (one line)
   - Follow same format as commit messages (infinitive verb, uppercase)
   - Example: "Add model availability monitoring and startup validation"
   - NO prefixes like `feat:`, `fix:`

4. **Generate PR Description**
   - Use **concise format** (not detailed/verbose)
   - Structure:
     ```markdown
     ## [Title from step 3]

     ### Summary
     [1-2 sentences explaining what this PR does]

     ### Problem
     [Brief description of problem being solved]

     ### Solution
     [Key changes/features - use bullet points]

     ### Key Changes
     [Bulleted list of important changes]

     ### Configuration Required (if applicable)
     [Any required config changes]

     ### Breaking Changes
     [None, or list them]

     ### Related Issues (OPTIONAL - only if user mentioned)
     [Only include if user explicitly mentions issue number]
     ```

5. **Output**
   - Show both title and description
   - Format for easy copy-paste
   - DO NOT include issue numbers unless user explicitly mentioned them
   - Keep it concise (aim for ~20-30 lines total)

## Important Rules

- Always use concise format (not verbose)
- NO issue numbers unless user explicitly provided one
- Follow CLAUDE.md guidelines (no tool mentions, no co-authored-by)
- Title should be action-oriented (Add, Update, Fix, Implement, etc.)
- Description should be scannable and actionable

## Example Output Format

```markdown
## Add model availability monitoring and startup validation

### Summary
Implement monitoring and validation to prevent production failures when Google deprecates Gemini models.

### Problem
When Google deprecates a model:
- No proactive detection until users encounter failures
- No alerts to the team
- Developers could deploy with invalid models

### Solution
**Runtime Monitoring**
- Background health checker every 2 hours
- Slack alerts when models become unavailable

**Startup Validation**
- Validates pricing exists for configured model
- Validates model exists in Google's API

### Key Changes
- Add health_check_interval_minutes and monitored_models to config
- Add model_pricing section for cost calculations
- Comprehensive test coverage

### Configuration Required
Add to .env (optional):
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

### Breaking Changes
None - all changes are additive.
```
