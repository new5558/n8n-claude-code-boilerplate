---
name: n8n-workflows
description: Manage n8n workflows — list, get, create, update, delete, activate, deactivate, transfer, tags
argument-hint: action and args, e.g. list or get ID
---

Interact with n8n workflows via CLI. Run commands with `uv run n8n_cli.py workflows <action>`.

## Commands

```
workflows list [--active true/false] [--name "filter"] [--tags "tag1,tag2"]
workflows get <id>
workflows create <json-file-or-string>
workflows update <id> <json-file-or-string>
workflows delete <id>
workflows activate <id>
workflows deactivate <id>
workflows webhook-activate <id>          # activate→deactivate→activate cycle for webhook registration
workflows transfer <id> <project-id>
workflows tags <id>
workflows set-tags <id> <tag-id-1> <tag-id-2> ...
workflows version <id> <version-id>
```

When creating or editing workflow JSON, use the `/n8n-skills` knowledge base for node types, parameters, and connection patterns. Start with `.claude/skills/n8n-skills/resources/INDEX.md` to find the right node docs.
For the API envelope schema, read `docs/n8n_openapi.yml` under `components/schemas/workflow`.

**IMPORTANT**: Read the "Webhook Workflow Lifecycle" and "Execution Observability" sections in `CLAUDE.md` before creating or testing webhook workflows. Key rules:
- Always include `webhookId` (UUID) on Webhook nodes
- Use activate → deactivate → activate cycle to register webhooks
- Use `executions get <id> --include-data` to inspect per-node outputs
- Do NOT use `respondToWebhook` nodes (breaks manual testing)

**See also**: Use `/n8n-skills` for node docs when building workflow JSON. Use `/n8n-executions` to inspect execution results after triggering.

Present results in a clean readable format. $ARGUMENTS
