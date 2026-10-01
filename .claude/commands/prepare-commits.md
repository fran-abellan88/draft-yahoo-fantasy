# Prepare Commits

Analyze changed files and prepare structured commits following repository guidelines.

## Workflow

1. **Analyze Changes**
   - Run `git status` to identify all changed files
   - Ask user: "Any files to exclude from commits?" (wait for response)
   - Analyze remaining files to understand nature of changes

2. **Group Changes Logically**
   - Group files by feature, purpose, or logical relationship
   - Consider whether changes should be 1 commit or multiple commits
   - Read `CLAUDE.md` to understand commit message format requirements

3. **Propose Commit Structure**
   - For each proposed commit group:
     - List files to be included
     - Draft commit message following CLAUDE.md guidelines:
       - Start with infinitive verb and uppercase (e.g., "Add", "Update", "Fix")
       - NO prefixes like `feat:`, `docs:`, `bug:`
       - NO mentions of co-authored-by or tools used
       - Clear, actionable description
   - Present all proposed commits to user

4. **Get User Approval**
   - Show complete proposed structure
   - Ask: "Do you approve this commit structure? (yes/adjust/cancel)"
   - If "adjust": ask what changes are needed
   - If "cancel": stop workflow

5. **Execute Commits**
   - For each approved commit:
     - Show files to be staged
     - Ask: "Proceed with this commit? (yes/skip)"
     - If yes:
       - Stage files with `git add`
       - Create commit with prepared message
       - Confirm commit was created successfully
     - If skip: move to next commit

## Important Rules

- Always read and follow CLAUDE.md commit message guidelines
- Be flexible: sometimes all changes belong in 1 commit
- Ask for confirmation before staging/committing
- Never commit files user explicitly excluded
- Handle both simple (1 commit) and complex (multiple commits) scenarios

## Output Format

For each commit, provide:
1. List of files
2. Commit message (following CLAUDE.md)
3. Brief explanation of what this commit accomplishes
