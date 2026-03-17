---
name: n8n-audit
description: Run a security audit on the n8n instance
argument-hint: optional categories, e.g. credentials database
---

Run an n8n security audit via CLI.

## Command

```
uv run n8n_cli.py audit generate [--categories credentials database nodes filesystem instance]
```

Present results in a clean readable format. $ARGUMENTS
