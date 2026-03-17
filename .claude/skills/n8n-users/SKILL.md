---
name: n8n-users
description: Manage n8n users — list, get, delete, change role
argument-hint: action, e.g. list --include-role
---

Interact with n8n users via CLI. Run commands with `uv run n8n_cli.py users <action>`.

## Commands

```
users list [--include-role]
users get <id> [--include-role]
users delete <id>
users change-role <id> <role>
```

Present results in a clean readable format. $ARGUMENTS
