---
name: n8n-projects
description: Manage n8n projects — list, create, update, delete, manage users
argument-hint: action, e.g. list or create my-project
---

Interact with n8n projects via CLI. Run commands with `uv run n8n_cli.py projects <action>`.

## Commands

```
projects list
projects create <name>
projects update <id> <name>
projects delete <id>
projects users <id>
projects add-users <id> <json>    # {"relations": [{"userId": "...", "role": "..."}]}
projects remove-user <id> <user-id>
projects change-role <id> <user-id> <role>
```

Present results in a clean readable format. $ARGUMENTS
