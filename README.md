# n8n-automation

CLI toolkit for building and managing n8n workflows entirely from Claude Code — no UI required.

## What this is

A Python CLI (`n8n_cli.py`) + Claude Code skills that wrap the n8n Public API v1. Every API interaction is a visible, re-runnable terminal command. Combined with the `n8n-skills` knowledge base (542 node docs), Claude Code can autonomously create, test, debug, and fix n8n workflows.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An n8n instance with API access enabled

## Setup

```bash
git clone <repo>
cd n8n-automation
cp .env.example .env   # fill in N8N_HOST and N8N_API_KEY
uv sync
```

## Quick start

```bash
# List workflows on your instance
uv run n8n_cli.py workflows list

# Create a workflow from JSON
uv run n8n_cli.py workflows create workflows/my-workflow.json

# Register the webhook (activate→deactivate→activate cycle)
uv run n8n_cli.py workflows webhook-activate <id>

# Trigger the webhook
curl -X POST "https://your-instance/webhook/path" \
  -H "Content-Type: application/json" -d '{"key": "value"}'

# Inspect the execution
uv run n8n_cli.py executions report <exec-id>
```

## CLI reference

| Resource | Actions | Notes |
|----------|---------|-------|
| `workflows` | list, get, create, update, delete, activate, deactivate, webhook-activate, transfer, tags, set-tags, version | `version <id> <version-id>` restores a previous version |
| `executions` | list, get, report, delete, retry, stop, stop-many, tags, set-tags | `report` = human-readable summary; `get --include-data` = full JSON |
| `credentials` | list, create, update, delete, schema, transfer | `schema <type>` shows required fields for a credential type |
| `tags` | list, get, create, update, delete | |
| `users` | list, get, delete, change-role | |
| `variables` | list, create, update, delete | Requires paid n8n license |
| `projects` | list, create, update, delete, users, add-users, remove-user, change-role | Requires paid n8n license |
| `tables` | list, get, create, update, delete, rows, insert-rows, update-rows, upsert-row, delete-rows | |
| `source-control` | pull | `--force` to overwrite local changes |
| `audit` | generate | `--categories credentials database nodes filesystem instance` |

### User observability features

- **Auto-backup**: `workflows update` and `workflows delete` automatically save the current server state to `workflows/.backups/` before making changes
- **Auto-webhookId**: `workflows create` and `workflows update` auto-generate UUIDs for webhook nodes that lack `webhookId`
- **Execution report**: `executions report <id>` shows a human-readable per-node summary instead of raw JSON
- **Workflow files**: JSON files are saved in `workflows/` for inspection and git diffing

## Claude Code skills

11 skills, one per resource group:

`/n8n-workflows`, `/n8n-executions`, `/n8n-credentials`, `/n8n-tags`, `/n8n-users`, `/n8n-variables`, `/n8n-projects`, `/n8n-tables`, `/n8n-audit`, `/n8n-source-control`

Plus `/n8n-skills` — a knowledge base with 542 node docs, workflow templates, and a compatibility matrix for building workflow JSON.

See `CLAUDE.md` for the complete reference (webhook lifecycle, execution observability, workflow JSON format, expression syntax).

## Known limitations

- **Webhook registration** requires the `webhook-activate` command (activate→deactivate→activate cycle). A single activate may not register the webhook.
- **`respondToWebhook` nodes** crash when the workflow is triggered manually from the n8n editor. Use `responseMode: "onReceived"` instead.
- **Variables and projects** API endpoints require a paid n8n license (return 403 on community edition).
