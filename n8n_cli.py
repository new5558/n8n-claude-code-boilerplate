#!/usr/bin/env python3
"""Thin CLI for the n8n Public API v1.

Usage:
    uv run n8n_cli.py <resource> <action> [args] [--options]

Examples:
    uv run n8n_cli.py workflows list
    uv run n8n_cli.py workflows get GohwbPszWL3ikd9l
    uv run n8n_cli.py executions list --status error
    uv run n8n_cli.py tags create "my-tag"
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("N8N_HOST", "").rstrip("/") + "/api/v1"
API_KEY = os.environ.get("N8N_API_KEY", "")


def client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"},
        timeout=30,
    )


def out(data):
    print(json.dumps(data, indent=2, default=str))


def err(resp: httpx.Response):
    print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
    sys.exit(1)


def paginate(c: httpx.Client, path: str, params: dict | None = None) -> list:
    """Follow nextCursor to collect all pages."""
    params = dict(params or {})
    results = []
    while True:
        resp = c.get(path, params=params)
        if resp.status_code >= 400:
            err(resp)
        body = resp.json()
        results.extend(body.get("data", []))
        cursor = body.get("nextCursor")
        if not cursor:
            break
        params["cursor"] = cursor
    return results


def _substitute_env_vars(text: str) -> str:
    """Replace $ENV_VAR_NAME placeholders with values from the environment."""
    import re
    def _replacer(match):
        var_name = match.group(1)
        value = os.environ.get(var_name)
        if value is None:
            print(f"Warning: env var ${var_name} not set, leaving placeholder", file=sys.stderr)
            return match.group(0)
        return value
    return re.sub(r'\$([A-Z_][A-Z0-9_]*)', _replacer, text)


def load_json_arg(path_or_json: str) -> dict:
    """Load JSON from a file path or inline string, substituting $ENV_VAR placeholders."""
    try:
        if os.path.isfile(path_or_json):
            with open(path_or_json) as f:
                text = f.read()
            text = _substitute_env_vars(text)
            return json.loads(text)
        text = _substitute_env_vars(path_or_json)
        return json.loads(text)
    except json.JSONDecodeError as exc:
        source = path_or_json if os.path.isfile(path_or_json) else "inline JSON"
        print(f"Error: invalid JSON in {source}: {exc}", file=sys.stderr)
        sys.exit(1)


BACKUPS_DIR = Path("workflows/.backups")


def _backup_workflow(c: httpx.Client, workflow_id: str) -> str | None:
    """Fetch current workflow from server and save to .backups/. Returns backup path."""
    resp = c.get(f"/workflows/{workflow_id}")
    if resp.status_code >= 400:
        return None
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = BACKUPS_DIR / f"{workflow_id}_{ts}.json"
    path.write_text(json.dumps(resp.json(), indent=2, default=str))
    print(f"Backed up to {path}", file=sys.stderr)
    return str(path)


def _ensure_webhook_ids(data: dict) -> None:
    """Auto-generate webhookId for webhook nodes that lack one."""
    for node in data.get("nodes", []):
        node_type = node.get("type", "")
        if "webhook" in node_type.lower() and not node.get("webhookId"):
            generated = str(uuid.uuid4())
            print(f"Auto-generated webhookId for '{node.get('name')}': {generated}", file=sys.stderr)
            node["webhookId"] = generated


# ── Workflows ────────────────────────────────────────────────────────────────

def workflows_list(args):
    params = {}
    if args.active is not None:
        params["active"] = args.active
    if args.name:
        params["name"] = args.name
    if args.tags:
        params["tags"] = args.tags
    with client() as c:
        out(paginate(c, "/workflows", params))


def workflows_get(args):
    with client() as c:
        resp = c.get(f"/workflows/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_create(args):
    data = load_json_arg(args.json)
    _ensure_webhook_ids(data)
    with client() as c:
        resp = c.post("/workflows", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_update(args):
    data = load_json_arg(args.json)
    _ensure_webhook_ids(data)
    with client() as c:
        _backup_workflow(c, args.id)
        resp = c.put(f"/workflows/{args.id}", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_delete(args):
    with client() as c:
        _backup_workflow(c, args.id)
        resp = c.delete(f"/workflows/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_activate(args):
    with client() as c:
        resp = c.post(f"/workflows/{args.id}/activate")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_deactivate(args):
    with client() as c:
        resp = c.post(f"/workflows/{args.id}/deactivate")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_webhook_activate(args):
    """Activate→deactivate→activate cycle to register webhooks."""
    with client() as c:
        resp = c.post(f"/workflows/{args.id}/activate")
        if resp.status_code >= 400:
            err(resp)
        print("Activated (1/3)", file=sys.stderr)

        resp = c.post(f"/workflows/{args.id}/deactivate")
        if resp.status_code >= 400:
            err(resp)
        print("Deactivated (2/3)", file=sys.stderr)

        resp = c.post(f"/workflows/{args.id}/activate")
        if resp.status_code >= 400:
            err(resp)
        print("Reactivated (3/3) — webhook registered", file=sys.stderr)
        out(resp.json())


def workflows_transfer(args):
    with client() as c:
        resp = c.put(
            f"/workflows/{args.id}/transfer",
            json={"destinationProjectId": args.project_id},
        )
        if resp.status_code >= 400:
            err(resp)
        print("Transferred.")


def workflows_tags(args):
    with client() as c:
        resp = c.get(f"/workflows/{args.id}/tags")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_set_tags(args):
    tag_ids = [{"id": tid} for tid in args.tag_ids]
    with client() as c:
        resp = c.put(f"/workflows/{args.id}/tags", json=tag_ids)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def workflows_version(args):
    with client() as c:
        resp = c.get(f"/workflows/{args.id}/{args.version_id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


# ── Executions ───────────────────────────────────────────────────────────────

def executions_list(args):
    params = {}
    if args.status:
        params["status"] = args.status
    if args.workflow_id:
        params["workflowId"] = args.workflow_id
    if args.include_data:
        params["includeData"] = "true"
    with client() as c:
        out(paginate(c, "/executions", params))


def executions_get(args):
    params = {}
    if args.include_data:
        params["includeData"] = "true"
    with client() as c:
        resp = c.get(f"/executions/{args.id}", params=params)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def executions_delete(args):
    with client() as c:
        resp = c.delete(f"/executions/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def executions_retry(args):
    body = {}
    if args.load_workflow:
        body["loadWorkflow"] = True
    with client() as c:
        resp = c.post(f"/executions/{args.id}/retry", json=body)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def executions_stop(args):
    with client() as c:
        resp = c.post(f"/executions/{args.id}/stop")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def executions_stop_many(args):
    body = {"status": args.statuses}
    if args.workflow_id:
        body["workflowId"] = args.workflow_id
    with client() as c:
        resp = c.post("/executions/stop", json=body)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def executions_report(args):
    """Human-readable execution summary."""
    with client() as c:
        resp = c.get(f"/executions/{args.id}", params={"includeData": "true"})
        if resp.status_code >= 400:
            err(resp)
        d = resp.json()

    status = d.get("status", "?")
    mode = d.get("mode", "?")
    wf_name = d.get("workflowData", {}).get("name", "?")
    wf_id = d.get("workflowId", "?")
    started = d.get("startedAt", "?")
    stopped = d.get("stoppedAt", "?")

    print(f"=== Execution #{d.get('id', '?')} ===")
    print(f"Workflow: {wf_name} ({wf_id})")
    print(f"Status:   {status}")
    print(f"Mode:     {mode}")
    print(f"Time:     {started} → {stopped}")
    print()

    rd = d.get("data", {}).get("resultData", {})
    top_error = rd.get("error")
    if top_error:
        print(f"ERROR: {top_error.get('message', top_error)}")
        last_node = rd.get("lastNodeExecuted", "?")
        print(f"Last node: {last_node}")
        print()

    run_data = rd.get("runData", {})
    if not run_data:
        print("(no node execution data)")
        return

    print(f"{'Node':<25} {'Status':<10} {'Time':>6}  Output")
    print("\u2500" * 75)

    for name, runs in run_data.items():
        for run in runs:
            st = run.get("executionStatus", "?")
            ms = run.get("executionTime", 0)
            sym = "\u2713" if st == "success" else "\u2717"
            node_err = run.get("error")

            key_out = ""
            if node_err:
                key_out = f"ERROR: {node_err.get('message', '?')[:60]}"
            else:
                outputs = run.get("data", {}).get("main", [[]])
                for bi, branch in enumerate(outputs):
                    if not branch:
                        continue
                    fj = branch[0].get("json", {})
                    items = len(branch)
                    # Summarize based on common patterns
                    if "body" in fj and "webhookUrl" in fj:
                        body = fj.get("body", {})
                        key_out = f"body={json.dumps(body, default=str)[:50]}"
                    elif "message" in fj:
                        key_out = f"message[:{min(50, len(str(fj['message'])))}]"
                    elif "success" in fj:
                        key_out = f"success={fj['success']}"
                    elif "severity" in fj:
                        key_out = f"severity={fj['severity']}"
                    else:
                        keys = list(fj.keys())[:4]
                        key_out = ", ".join(f"{k}={str(fj[k])[:20]}" for k in keys)
                    if items > 1:
                        key_out = f"[{items} items] {key_out}"
                    # For IF nodes, show branch direction
                    if len(outputs) > 1:
                        key_out = f"\u2192 Output[{bi}] ({'TRUE' if bi == 0 else 'FALSE'})"
                        break

            print(f"{sym} {name:<23} {st:<10} {ms:>5}ms  {key_out}")


def executions_tags(args):
    with client() as c:
        resp = c.get(f"/executions/{args.id}/tags")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def executions_set_tags(args):
    tag_ids = [{"id": tid} for tid in args.tag_ids]
    with client() as c:
        resp = c.put(f"/executions/{args.id}/tags", json=tag_ids)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


# ── Credentials ──────────────────────────────────────────────────────────────

def credentials_list(args):
    with client() as c:
        out(paginate(c, "/credentials"))


def credentials_create(args):
    data = load_json_arg(args.json)
    with client() as c:
        resp = c.post("/credentials", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def credentials_update(args):
    data = load_json_arg(args.json)
    with client() as c:
        resp = c.patch(f"/credentials/{args.id}", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def credentials_delete(args):
    with client() as c:
        resp = c.delete(f"/credentials/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def credentials_schema(args):
    with client() as c:
        resp = c.get(f"/credentials/schema/{args.type_name}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def credentials_transfer(args):
    with client() as c:
        resp = c.put(
            f"/credentials/{args.id}/transfer",
            json={"destinationProjectId": args.project_id},
        )
        if resp.status_code >= 400:
            err(resp)
        print("Transferred.")


# ── Tags ─────────────────────────────────────────────────────────────────────

def tags_list(args):
    with client() as c:
        out(paginate(c, "/tags"))


def tags_get(args):
    with client() as c:
        resp = c.get(f"/tags/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tags_create(args):
    with client() as c:
        resp = c.post("/tags", json={"name": args.name})
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tags_update(args):
    with client() as c:
        resp = c.put(f"/tags/{args.id}", json={"name": args.name})
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tags_delete(args):
    with client() as c:
        resp = c.delete(f"/tags/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


# ── Users ────────────────────────────────────────────────────────────────────

def users_list(args):
    params = {}
    if args.include_role:
        params["includeRole"] = "true"
    with client() as c:
        out(paginate(c, "/users", params))


def users_get(args):
    params = {}
    if args.include_role:
        params["includeRole"] = "true"
    with client() as c:
        resp = c.get(f"/users/{args.id}", params=params)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def users_delete(args):
    with client() as c:
        resp = c.delete(f"/users/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        print("Deleted.")


def users_change_role(args):
    with client() as c:
        resp = c.patch(
            f"/users/{args.id}/role", json={"newRoleName": args.role}
        )
        if resp.status_code >= 400:
            err(resp)
        print("Role updated.")


# ── Variables ────────────────────────────────────────────────────────────────

def variables_list(args):
    with client() as c:
        out(paginate(c, "/variables"))


def variables_create(args):
    body = {"key": args.key, "value": args.value}
    with client() as c:
        resp = c.post("/variables", json=body)
        if resp.status_code >= 400:
            err(resp)
        print("Created.")


def variables_update(args):
    body = {"key": args.key, "value": args.value}
    with client() as c:
        resp = c.put(f"/variables/{args.id}", json=body)
        if resp.status_code >= 400:
            err(resp)
        print("Updated.")


def variables_delete(args):
    with client() as c:
        resp = c.delete(f"/variables/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        print("Deleted.")


# ── Projects ─────────────────────────────────────────────────────────────────

def projects_list(args):
    with client() as c:
        out(paginate(c, "/projects"))


def projects_create(args):
    with client() as c:
        resp = c.post("/projects", json={"name": args.name})
        if resp.status_code >= 400:
            err(resp)
        print("Created.")


def projects_update(args):
    with client() as c:
        resp = c.put(f"/projects/{args.id}", json={"name": args.name})
        if resp.status_code >= 400:
            err(resp)
        print("Updated.")


def projects_delete(args):
    with client() as c:
        resp = c.delete(f"/projects/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        print("Deleted.")


def projects_users(args):
    with client() as c:
        out(paginate(c, f"/projects/{args.id}/users"))


def projects_add_users(args):
    data = load_json_arg(args.json)
    with client() as c:
        resp = c.post(f"/projects/{args.id}/users", json=data)
        if resp.status_code >= 400:
            err(resp)
        print("Added.")


def projects_remove_user(args):
    with client() as c:
        resp = c.delete(f"/projects/{args.id}/users/{args.user_id}")
        if resp.status_code >= 400:
            err(resp)
        print("Removed.")


def projects_change_role(args):
    with client() as c:
        resp = c.patch(
            f"/projects/{args.id}/users/{args.user_id}",
            json={"role": args.role},
        )
        if resp.status_code >= 400:
            err(resp)
        print("Role updated.")


# ── Data Tables ──────────────────────────────────────────────────────────────

def tables_list(args):
    with client() as c:
        out(paginate(c, "/data-tables"))


def tables_get(args):
    with client() as c:
        resp = c.get(f"/data-tables/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tables_create(args):
    data = load_json_arg(args.json)
    with client() as c:
        resp = c.post("/data-tables", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tables_update(args):
    with client() as c:
        resp = c.patch(f"/data-tables/{args.id}", json={"name": args.name})
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tables_delete(args):
    with client() as c:
        resp = c.delete(f"/data-tables/{args.id}")
        if resp.status_code >= 400:
            err(resp)
        print("Deleted.")


def tables_rows(args):
    params = {}
    if args.filter:
        params["filter"] = args.filter
    if args.sort_by:
        params["sortBy"] = args.sort_by
    if args.search:
        params["search"] = args.search
    with client() as c:
        out(paginate(c, f"/data-tables/{args.id}/rows", params))


def tables_insert_rows(args):
    data = load_json_arg(args.json)
    with client() as c:
        resp = c.post(f"/data-tables/{args.id}/rows", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tables_update_rows(args):
    data = load_json_arg(args.json)
    with client() as c:
        resp = c.patch(f"/data-tables/{args.id}/rows/update", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tables_upsert_row(args):
    data = load_json_arg(args.json)
    with client() as c:
        resp = c.post(f"/data-tables/{args.id}/rows/upsert", json=data)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


def tables_delete_rows(args):
    params = {"filter": args.filter}
    with client() as c:
        resp = c.delete(f"/data-tables/{args.id}/rows/delete", params=params)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


# ── Source Control ───────────────────────────────────────────────────────────

def source_control_pull(args):
    body = {}
    if args.force:
        body["force"] = True
    with client() as c:
        resp = c.post("/source-control/pull", json=body)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


# ── Audit ────────────────────────────────────────────────────────────────────

def audit_generate(args):
    body = {}
    if args.categories:
        body["additionalOptions"] = {"categories": args.categories}
    with client() as c:
        resp = c.post("/audit", json=body)
        if resp.status_code >= 400:
            err(resp)
        out(resp.json())


# ── CLI Parser ───────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="n8n_cli", description="n8n Public API v1 CLI"
    )
    sub = parser.add_subparsers(dest="resource", required=True)

    # ── workflows ──
    wf = sub.add_parser("workflows")
    wf_sub = wf.add_subparsers(dest="action", required=True)

    p = wf_sub.add_parser("list")
    p.add_argument("--active", default=None, choices=["true", "false"])
    p.add_argument("--name", default=None)
    p.add_argument("--tags", default=None)
    p.set_defaults(func=workflows_list)

    p = wf_sub.add_parser("get")
    p.add_argument("id")
    p.set_defaults(func=workflows_get)

    p = wf_sub.add_parser("create")
    p.add_argument("json", help="JSON file path or inline JSON string")
    p.set_defaults(func=workflows_create)

    p = wf_sub.add_parser("update")
    p.add_argument("id")
    p.add_argument("json", help="JSON file path or inline JSON string")
    p.set_defaults(func=workflows_update)

    p = wf_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=workflows_delete)

    p = wf_sub.add_parser("activate")
    p.add_argument("id")
    p.set_defaults(func=workflows_activate)

    p = wf_sub.add_parser("deactivate")
    p.add_argument("id")
    p.set_defaults(func=workflows_deactivate)

    p = wf_sub.add_parser("webhook-activate", help="Activate→deactivate→activate to register webhooks")
    p.add_argument("id")
    p.set_defaults(func=workflows_webhook_activate)

    p = wf_sub.add_parser("transfer")
    p.add_argument("id")
    p.add_argument("project_id")
    p.set_defaults(func=workflows_transfer)

    p = wf_sub.add_parser("tags")
    p.add_argument("id")
    p.set_defaults(func=workflows_tags)

    p = wf_sub.add_parser("set-tags")
    p.add_argument("id")
    p.add_argument("tag_ids", nargs="+")
    p.set_defaults(func=workflows_set_tags)

    p = wf_sub.add_parser("version")
    p.add_argument("id")
    p.add_argument("version_id")
    p.set_defaults(func=workflows_version)

    # ── executions ──
    ex = sub.add_parser("executions")
    ex_sub = ex.add_subparsers(dest="action", required=True)

    p = ex_sub.add_parser("list")
    p.add_argument("--status", choices=["canceled", "error", "running", "success", "waiting"])
    p.add_argument("--workflow-id", default=None)
    p.add_argument("--include-data", action="store_true")
    p.set_defaults(func=executions_list)

    p = ex_sub.add_parser("get")
    p.add_argument("id")
    p.add_argument("--include-data", action="store_true")
    p.set_defaults(func=executions_get)

    p = ex_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=executions_delete)

    p = ex_sub.add_parser("retry")
    p.add_argument("id")
    p.add_argument("--load-workflow", action="store_true")
    p.set_defaults(func=executions_retry)

    p = ex_sub.add_parser("stop")
    p.add_argument("id")
    p.set_defaults(func=executions_stop)

    p = ex_sub.add_parser("report", help="Human-readable execution summary")
    p.add_argument("id")
    p.set_defaults(func=executions_report)

    p = ex_sub.add_parser("stop-many")
    p.add_argument("statuses", nargs="+", choices=["queued", "running", "waiting"])
    p.add_argument("--workflow-id", default=None)
    p.set_defaults(func=executions_stop_many)

    p = ex_sub.add_parser("tags")
    p.add_argument("id")
    p.set_defaults(func=executions_tags)

    p = ex_sub.add_parser("set-tags")
    p.add_argument("id")
    p.add_argument("tag_ids", nargs="+")
    p.set_defaults(func=executions_set_tags)

    # ── credentials ──
    cr = sub.add_parser("credentials")
    cr_sub = cr.add_subparsers(dest="action", required=True)

    p = cr_sub.add_parser("list")
    p.set_defaults(func=credentials_list)

    p = cr_sub.add_parser("create")
    p.add_argument("json", help="JSON file or inline JSON with name, type, data")
    p.set_defaults(func=credentials_create)

    p = cr_sub.add_parser("update")
    p.add_argument("id")
    p.add_argument("json", help="JSON file or inline JSON")
    p.set_defaults(func=credentials_update)

    p = cr_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=credentials_delete)

    p = cr_sub.add_parser("schema")
    p.add_argument("type_name")
    p.set_defaults(func=credentials_schema)

    p = cr_sub.add_parser("transfer")
    p.add_argument("id")
    p.add_argument("project_id")
    p.set_defaults(func=credentials_transfer)

    # ── tags ──
    tg = sub.add_parser("tags")
    tg_sub = tg.add_subparsers(dest="action", required=True)

    p = tg_sub.add_parser("list")
    p.set_defaults(func=tags_list)

    p = tg_sub.add_parser("get")
    p.add_argument("id")
    p.set_defaults(func=tags_get)

    p = tg_sub.add_parser("create")
    p.add_argument("name")
    p.set_defaults(func=tags_create)

    p = tg_sub.add_parser("update")
    p.add_argument("id")
    p.add_argument("name")
    p.set_defaults(func=tags_update)

    p = tg_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=tags_delete)

    # ── users ──
    us = sub.add_parser("users")
    us_sub = us.add_subparsers(dest="action", required=True)

    p = us_sub.add_parser("list")
    p.add_argument("--include-role", action="store_true")
    p.set_defaults(func=users_list)

    p = us_sub.add_parser("get")
    p.add_argument("id")
    p.add_argument("--include-role", action="store_true")
    p.set_defaults(func=users_get)

    p = us_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=users_delete)

    p = us_sub.add_parser("change-role")
    p.add_argument("id")
    p.add_argument("role")
    p.set_defaults(func=users_change_role)

    # ── variables ──
    vr = sub.add_parser("variables")
    vr_sub = vr.add_subparsers(dest="action", required=True)

    p = vr_sub.add_parser("list")
    p.set_defaults(func=variables_list)

    p = vr_sub.add_parser("create")
    p.add_argument("key")
    p.add_argument("value")
    p.set_defaults(func=variables_create)

    p = vr_sub.add_parser("update")
    p.add_argument("id")
    p.add_argument("key")
    p.add_argument("value")
    p.set_defaults(func=variables_update)

    p = vr_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=variables_delete)

    # ── projects ──
    pj = sub.add_parser("projects")
    pj_sub = pj.add_subparsers(dest="action", required=True)

    p = pj_sub.add_parser("list")
    p.set_defaults(func=projects_list)

    p = pj_sub.add_parser("create")
    p.add_argument("name")
    p.set_defaults(func=projects_create)

    p = pj_sub.add_parser("update")
    p.add_argument("id")
    p.add_argument("name")
    p.set_defaults(func=projects_update)

    p = pj_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=projects_delete)

    p = pj_sub.add_parser("users")
    p.add_argument("id")
    p.set_defaults(func=projects_users)

    p = pj_sub.add_parser("add-users")
    p.add_argument("id")
    p.add_argument("json", help='JSON: {"relations": [{"userId": "...", "role": "..."}]}')
    p.set_defaults(func=projects_add_users)

    p = pj_sub.add_parser("remove-user")
    p.add_argument("id")
    p.add_argument("user_id")
    p.set_defaults(func=projects_remove_user)

    p = pj_sub.add_parser("change-role")
    p.add_argument("id")
    p.add_argument("user_id")
    p.add_argument("role")
    p.set_defaults(func=projects_change_role)

    # ── data-tables ──
    dt = sub.add_parser("tables")
    dt_sub = dt.add_subparsers(dest="action", required=True)

    p = dt_sub.add_parser("list")
    p.set_defaults(func=tables_list)

    p = dt_sub.add_parser("get")
    p.add_argument("id")
    p.set_defaults(func=tables_get)

    p = dt_sub.add_parser("create")
    p.add_argument("json", help='JSON: {"name": "...", "columns": [...]}')
    p.set_defaults(func=tables_create)

    p = dt_sub.add_parser("update")
    p.add_argument("id")
    p.add_argument("name")
    p.set_defaults(func=tables_update)

    p = dt_sub.add_parser("delete")
    p.add_argument("id")
    p.set_defaults(func=tables_delete)

    p = dt_sub.add_parser("rows")
    p.add_argument("id")
    p.add_argument("--filter", default=None)
    p.add_argument("--sort-by", default=None)
    p.add_argument("--search", default=None)
    p.set_defaults(func=tables_rows)

    p = dt_sub.add_parser("insert-rows")
    p.add_argument("id")
    p.add_argument("json", help='JSON: {"data": [...], "returnType": "all"}')
    p.set_defaults(func=tables_insert_rows)

    p = dt_sub.add_parser("update-rows")
    p.add_argument("id")
    p.add_argument("json", help="JSON with filter + data")
    p.set_defaults(func=tables_update_rows)

    p = dt_sub.add_parser("upsert-row")
    p.add_argument("id")
    p.add_argument("json", help="JSON with filter + data")
    p.set_defaults(func=tables_upsert_row)

    p = dt_sub.add_parser("delete-rows")
    p.add_argument("id")
    p.add_argument("filter", help="JSON filter string (required)")
    p.set_defaults(func=tables_delete_rows)

    # ── source-control ──
    sc = sub.add_parser("source-control")
    sc_sub = sc.add_subparsers(dest="action", required=True)

    p = sc_sub.add_parser("pull")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=source_control_pull)

    # ── audit ──
    au = sub.add_parser("audit")
    au_sub = au.add_subparsers(dest="action", required=True)

    p = au_sub.add_parser("generate")
    p.add_argument(
        "--categories",
        nargs="*",
        choices=["credentials", "database", "nodes", "filesystem", "instance"],
    )
    p.set_defaults(func=audit_generate)

    return parser


def main():
    if not API_KEY:
        print("Error: N8N_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    if not BASE_URL or BASE_URL == "/api/v1":
        print("Error: N8N_HOST not set in .env", file=sys.stderr)
        sys.exit(1)

    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
