---
description: Document significant work, features, or issues for future reference
---

# Document Work Command

You are being asked to document recent work in the project.

## Instructions

1. **Parse the user's description** from the command arguments to understand what needs to be documented.

2. **Check for related documents**: Look in `.claude/sessions/` for any existing documentation that might be related to this work. Consider:
   - Similar feature names
   - Same module/component
   - Related technical area

3. **Propose action**: Tell the user:
   - The proposed filename: `YYYY-MM-DD-HHMM-<title>.md` (generate from description)
   - Any related existing documents found
   - Whether you recommend creating new or updating existing

4. **Wait for confirmation**: Ask the user:
   - If they want to proceed with the proposed filename
   - If they want to update an existing document instead
   - Any adjustments to scope or focus

5. **Create/update the document** in `.claude/sessions/` using this template:

```markdown
# [Title]

**Date**: YYYY-MM-DD HH:MM

## Context

[Why this work was needed - the problem or requirement]

## Implementation

[High-level description of what was done - key changes, approaches, technologies]

## Issues & Solutions

[Problems encountered during implementation and how they were resolved]

## Key Decisions

[Important architectural or design decisions made]

## Notes for Future Sessions

[Additional context, gotchas, or considerations for future work]
```

## Documentation Guidelines

- **Be concise but complete**: Provide enough information for you to continue work in future sessions
- **Focus on high-level**: Don't document every line of code, focus on architecture and decisions
- **Include context**: Explain WHY decisions were made, not just WHAT was done
- **Document failures**: Include approaches that didn't work and why
- **Be specific**: Include file paths, function names, or key identifiers when relevant

## Important

- Only document significant work (features, refactors, bug fixes, architectural changes)
- Do NOT document minor changes or trivial updates
- Always confirm with the user before creating or modifying documents
