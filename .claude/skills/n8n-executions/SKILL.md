---
name: n8n-executions
description: Manage n8n executions — list, get, delete, retry, stop
argument-hint: action, e.g. list --status error
---

Interact with n8n executions via CLI. Run commands with `uv run n8n_cli.py executions <action>`.

## Commands

```
executions list [--status canceled|error|running|success|waiting] [--workflow-id ID] [--include-data]
executions get <id> [--include-data]
executions report <id>                   # human-readable execution summary with per-node table
executions delete <id>
executions retry <id> [--load-workflow]
executions stop <id>
executions stop-many <status1> [status2 ...] [--workflow-id ID]
executions tags <id>
executions set-tags <id> <tag-id-1> <tag-id-2> ...
```

Present results in a clean readable format. $ARGUMENTS
