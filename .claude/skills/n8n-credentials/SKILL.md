---
name: n8n-credentials
description: Manage n8n credentials — list, create, update, delete, schema, transfer
argument-hint: action, e.g. list or schema githubApi
---

Interact with n8n credentials via CLI. Run commands with `uv run n8n_cli.py credentials <action>`.

## Commands

```
credentials list
credentials create <json>     # {"name": "...", "type": "...", "data": {...}}
credentials update <id> <json>
credentials delete <id>
credentials schema <type-name>
credentials transfer <id> <project-id>
```

For create/update JSON schema, read `docs/n8n_openapi.yml` and look for `credential` under `components/schemas`.

Present results in a clean readable format. $ARGUMENTS
