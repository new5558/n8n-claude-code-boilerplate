# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI toolkit + Claude Code skills for building and managing n8n workflows entirely from the terminal — no UI required. Python 3.11 is required (pinned via `.python-version`).

## Commands

```bash
# Install dependencies
uv sync

# Add a dependency
uv add <package>

# n8n CLI — interact with n8n instance
uv run n8n_cli.py <resource> <action> [args] [--options]
# Examples:
uv run n8n_cli.py workflows list
uv run n8n_cli.py executions list --status error
uv run n8n_cli.py tags create "my-tag"
```

## n8n Integration

- **CLI**: `n8n_cli.py` — thin wrapper over the n8n Public API v1. Every API call is a visible terminal command.
- **API spec**: `docs/n8n_openapi.yml` — downloaded OpenAPI spec from the live instance. Only read when needed for schema details.
- **Skills**: One per resource group — `/n8n-workflows`, `/n8n-executions`, `/n8n-credentials`, `/n8n-tags`, `/n8n-users`, `/n8n-variables`, `/n8n-projects`, `/n8n-tables`, `/n8n-audit`, `/n8n-source-control`. Each loads only its own docs to save tokens.
- **Node knowledge**: `/n8n-skills` — 542 node docs, templates, compatibility matrix. Use for building/editing workflow JSON.
- **Config**: `N8N_API_KEY` and `N8N_HOST` are loaded from `.env`.
- **Host**: `https://n8n.norapat.com/` — custom domain fronted by Cloudflare, backed by Railway.

## Webhook Workflow Lifecycle (Critical)

Creating and triggering webhook-based workflows from CLI requires a specific sequence:

### 1. Include `webhookId` on webhook nodes

When building workflow JSON, **always generate a UUID for the `webhookId` field** on the Webhook trigger node. Without it, n8n won't register the production webhook endpoint.

```json
{
  "parameters": { "path": "my-path", "httpMethod": "GET", ... },
  "type": "n8n-nodes-base.webhook",
  "typeVersion": 1.1,
  "webhookId": "generate-a-uuid-here",
  "name": "Webhook"
}
```

The Discord node also needs a `webhookId` if using webhook authentication.

### 2. Activation sequence

After creating the workflow via `workflows create`:

```bash
# One command does the full cycle (activate → deactivate → reactivate):
uv run n8n_cli.py workflows webhook-activate <id>
```

A single `activate` call may NOT register the webhook. The `webhook-activate` command forces n8n to re-register webhook listeners via a deactivate→reactivate cycle.

### 3. Triggering

```bash
curl -X POST "https://n8n.norapat.com/webhook/<path>" \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

- Production URL: `https://n8n.norapat.com/webhook/<path>`
- Test URL: `https://n8n.norapat.com/webhook-test/<path>` (only works when UI is listening)
- Use GET with query params: `?city=Bangkok`
- Use POST with JSON body: `{"city": "Bangkok"}`
- For GET: data is in `$json.query`, for POST: data is in `$json.body`

### 4. Do NOT use `respondToWebhook` nodes

The `n8n-nodes-base.respondToWebhook` node crashes when the workflow is triggered manually from the n8n editor (error: "No Webhook node found in the workflow"). Use `responseMode: "onReceived"` on the webhook and rely on the execution API for observability.

## Execution Observability

The execution API provides full per-node debugging data:

```bash
# List executions for a workflow
uv run n8n_cli.py executions list --workflow-id <id>

# Get full execution data (every node's input/output/error/timing)
uv run n8n_cli.py executions get <exec-id> --include-data
```

### What the execution API provides per node:
- `executionStatus`: success/error
- `executionTime`: milliseconds
- `data.main[branch][item].json`: full output data
- `error.message`: error details if failed
- Branch index: `Output[0]` = true/first branch, `Output[1]` = false/second branch (for IF nodes)

### Automated testing pattern:
1. Save workflow JSON to `workflows/<name>.json`
2. `workflows create workflows/<name>.json` → get workflow ID
3. `workflows webhook-activate <id>` → registers webhook
4. `curl` the webhook → fires and forgets (HTTP 200)
5. `sleep 3` then `executions list --workflow-id <id>` → get latest execution ID
6. `executions report <exec-id>` → human-readable per-node summary
7. If error: `executions get <exec-id> --include-data` for full JSON details
8. Fix workflow JSON, `workflows update <id> workflows/<name>.json`, repeat from step 3

## n8n Workflow JSON Tips

- Always set `"settings": {"executionOrder": "v1"}`
- Webhook node: use `typeVersion: 1.1`, always include `webhookId` (UUID)
- HTTP Request: `typeVersion: 4.2`
- Code node: `typeVersion: 2`, use `jsCode` or `pythonCode`
- IF node: `typeVersion: 2.2`, conditions use `version: 2` format
- Merge node: `typeVersion: 3`
- Set node: `typeVersion: 3.4`
- Discord webhook: `typeVersion: 2`, `authentication: "webhook"`, needs credential ID `$N8N_DISCORD_CREDENTIAL_ID` (from `.env`)
- Node positions: space nodes ~220px apart horizontally, branches ~160px apart vertically
- To handle errors per-item without crashing the workflow, set `"onError": "continueRegularOutput"` at the node level (not inside `parameters`)

### Multi-item flow and data replacement (Critical)

**HTTP Request (and other action nodes) replace all input fields** with the response body. If you pass `{url, notify}` through an HTTP Request node, those fields are gone — replaced by the HTTP response data.

To preserve upstream data in a downstream Code node, use **cross-node references**:
```js
const origItems = $('UpstreamNodeName').all();
const items = $input.all();
items.map((item, idx) => {
  const orig = origItems[idx]?.json || {};
  // orig.url, orig.notify are preserved
  // item.json has the HTTP response / current node output
});
```

**Error handling with `continueOnFail`/`continueRegularOutput`**:
- Successful HTTP requests: output = response body only (no `statusCode` field)
- Failed HTTP requests: output = `{error: {message: "...", name: "...", stack: "..."}}`
- Check `item.json.error` to distinguish success from failure

### Code node jsCode string escaping (Critical)

In workflow JSON, `jsCode` is a JSON string value. **All `\n` in the JSON become literal newlines in the JS code.** This means:
- Template literals (backticks) handle embedded newlines fine
- **Single/double quoted strings CANNOT contain `\n`** — it becomes a literal newline inside quotes = SyntaxError
- To insert a newline character in JS code, use `String.fromCharCode(10)` or build arrays and `.join()`
- To build multi-line strings, use array `.join()` pattern instead of string concatenation with `'\n'`

## Workflow JSON Reference

### Connection object structure

```json
"connections": {
  "SourceNodeName": {
    "main": [
      [{"node": "TargetOnBranch0", "type": "main", "index": 0}],
      [{"node": "TargetOnBranch1", "type": "main", "index": 0}]
    ]
  }
}
```

- Outer key = source node's `name` (exact string match)
- `"main"` is always `"main"` for standard data flow
- Value is an **array of arrays** — each inner array is one output branch
- **IF nodes**: `main[0]` = true branch, `main[1]` = false branch
- **Switch nodes**: one branch per case, indexed 0, 1, 2, ...
- Single-output nodes still wrap in `[[...]]`
- Multiple targets on same branch: `[{"node": "A", ...}, {"node": "B", ...}]`
- `index` on each target = which input slot (usually `0`)

### Credential reference format

```json
"credentials": {
  "credentialTypeName": {
    "id": "existingCredentialId",
    "name": "Human-readable name"
  }
}
```

- `credentialTypeName` varies by node (e.g., `discordWebhookApi`, `gmailOAuth2`, `googleCalendarOAuth2Api`)
- Find existing credentials: `uv run n8n_cli.py credentials list`
- Get schema for a type: `uv run n8n_cli.py credentials schema <type-name>`
- Credentials must already exist on the n8n instance — the API does not inline secrets
- Available on this instance (IDs in `.env`): Discord Webhook (`$N8N_DISCORD_CREDENTIAL_ID`), Gmail OAuth2 (`$N8N_GMAIL_CREDENTIAL_ID`), Google Calendar OAuth2 (`$N8N_CALENDAR_CREDENTIAL_ID`)

### Expression syntax

- Expressions in parameter values use `"={{ ... }}"` (note the `=` prefix)
- Reference previous node output: `={{ $json.fieldName }}`
- Reference specific node: `={{ $('NodeName').item.json.field }}`
- Webhook POST body: `{{ $json.body.fieldName }}`
- Webhook GET query: `{{ $json.query.fieldName }}`
- Ternary: `={{ $json.x ? 'yes' : 'no' }}`
- Luxon dates: `{{ $now }}`, `{{ $today }}`, `{{ $now.plus(1, 'day') }}`

### Code node built-in variables (JS)

- `$input.first()` / `$input.last()` / `$input.all()` — access input items
- `$input.first().json` — the JSON data of first item
- `$('NodeName').first().json` — reference output of a specific node by name
- `$('NodeName').all()` — get all items from a specific node (useful after branches merge)
- `$execution.id` — current execution ID
- `$now` — Luxon DateTime for now
- `$today` — Luxon DateTime for today
- Return format (runOnceForAllItems): `return [{json: {key: value}}, ...]`
- Return format (runOnceForEachItem): `return {json: {key: value}}`

## Workflow File Convention

When creating or editing workflow JSON:

1. Save to `workflows/<kebab-name>.json` (e.g., `workflows/url-health-checker.json`)
2. After successful create/update, the file stays — do NOT delete it
3. User can inspect, diff (`git diff workflows/`), or manually re-deploy from these files
4. The CLI auto-backs up the server state to `workflows/.backups/` before any update or delete