---
name: n8n-tables
description: Manage n8n data tables — list, create, delete, query/insert/update/delete rows
argument-hint: action, e.g. list or rows TABLE_ID --search text
---

Interact with n8n data tables via CLI. Run commands with `uv run n8n_cli.py tables <action>`.

## Commands

```
tables list
tables get <id>
tables create <json>   # {"name": "...", "columns": [{"name": "...", "type": "string|number|boolean|date"}]}
tables update <id> <name>
tables delete <id>
tables rows <id> [--filter JSON] [--sort-by "col:asc"] [--search "text"]
tables insert-rows <id> <json>   # {"data": [...], "returnType": "all|count|id"}
tables update-rows <id> <json>   # {"filter": {...}, "data": {...}}
tables upsert-row <id> <json>    # {"filter": {...}, "data": {...}}
tables delete-rows <id> <filter-json>
```

For JSON schemas, read `docs/n8n_openapi.yml` and look for `createDataTableRequest`, `insertRowsRequest`, etc.

Present results in a clean readable format. $ARGUMENTS
