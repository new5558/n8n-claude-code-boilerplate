---
name: n8n-variables
description: Manage n8n variables — list, create, update, delete
argument-hint: action, e.g. list or create MY_KEY my_value
---

Interact with n8n variables via CLI. Run commands with `uv run n8n_cli.py variables <action>`.

## Commands

```
variables list
variables create <key> <value>
variables update <id> <key> <value>
variables delete <id>
```

Present results in a clean readable format. $ARGUMENTS
