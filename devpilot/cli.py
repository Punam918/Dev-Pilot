"""Command-line setup, server, deterministic replay, and live evaluation."""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import shutil
from pathlib import Path

from .api import create_app, ensure_token
from .config import Settings
from .lease import InstanceLease
from .telemetry import configure_logging
from .demo import CASES, seed
from .evaluation import evaluate, run_case


def main():
    parser = argparse.ArgumentParser(prog="devpilot", description="Local MCP debugging with explicit approvals")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Copy trusted fixtures and create a private .env when absent")
    init.add_argument("--demo", action="store_true", help="Explicitly enable host execution of the bundled scripted fixtures")
    serve = sub.add_parser("serve", help="Start the local web UI and API")
    serve.add_argument("--seed", action="store_true", help="Seed missing fixtures (used by the container demo)")
    sub.add_parser("token", help="Print the local API access token")
    sub.add_parser("doctor", help="Print non-secret local configuration checks")
    replay = sub.add_parser("replay", help="Run one scripted fixture with automatic fixture-scoped approvals; no LLM")
    replay.add_argument("--case", choices=list(CASES), default="redis")
    replay.add_argument("--out", type=Path, default=Path("outputs/local-replay"))
    evaluation = sub.add_parser("evaluate", help="Run all three synthetic tasks; script mode is not model evaluation")
    evaluation.add_argument("--live", action="store_true", help="Use configured live model; requires the Docker runner")
    evaluation.add_argument("--out", type=Path, default=Path("outputs/local-evaluation"))
    evaluation.add_argument("--label", default="local")
    args = parser.parse_args()
    if args.command == "init":
        path = Path(".env")
        if not path.exists():
            value = "\n".join(["# Local configuration; never commit this file.",
                "DP_PROVIDER=demo", "DP_MODEL=qwen3:4b", "DP_BASE_URL=http://127.0.0.1:11434/v1",
                f"DP_API_TOKEN={secrets.token_urlsafe(32)}", "DP_WORKSPACE_DIR=workspace", "DP_DATA_DIR=.devpilot",
                "DP_RUNNER=" + ("host-trusted" if args.demo else "disabled"),
                "DP_TRUST_LOCAL_CODE=" + ("true" if args.demo else "false"), "DP_DOCKER_TOOLS=false", ""])
            path.write_text(value)
            path.chmod(0o600)
            print("Created private .env (not tracked by Git).")
        else:
            print("Existing .env preserved. Review its runner settings; --demo does not overwrite it.")
        settings = Settings()
        print("Seeded repositories:", ", ".join(seed(settings.workspace_dir)) or "already present")
        print("Next: python -m devpilot token\nThen: python -m devpilot serve")
        if args.demo:
            print("Demo note: host-trusted runs bundled code on this computer. Use Docker for other repositories.")
    elif args.command == "token":
        print(ensure_token(Settings()))
    elif args.command == "serve":
        import uvicorn
        settings = Settings()
        if args.seed:
            seed(settings.workspace_dir)
        if settings.log_json:
            configure_logging()
        app = create_app(settings)
        print(f"Dev-Pilot UI: http://127.0.0.1:{settings.port}", flush=True)
        print("Get the access token in another terminal: python -m devpilot token", flush=True)
        uvicorn.run(app, host=settings.host, port=settings.port, workers=1, proxy_headers=False, access_log=False, timeout_graceful_shutdown=20)
    elif args.command == "doctor":
        settings = Settings()
        print(json.dumps({"python": __import__("platform").python_version(), "git": shutil.which("git"),
            "docker": shutil.which("docker"), "provider": settings.provider, "runner": settings.runner,
            "workspace": str(settings.workspace_dir), "model": settings.model,
            "note": "No network or model inference was performed; tokens are intentionally omitted"}, indent=2))
    elif args.command == "replay":
        print("SCRIPTED DEMO: executing trusted bundled fixture code. No LLM. Fixture-scoped approvals are automatic.")
        result = asyncio.run(run_case(args.case, args.out))
        print(json.dumps(result, indent=2))
        print(f"Artifacts: {args.out.resolve()}")
        if not result["resolved"]:
            raise SystemExit(1)
    elif args.command == "evaluate":
        settings = Settings() if args.live else None
        if args.live and (settings.provider != "openai" or settings.runner not in {"docker", "kubernetes"}):
            parser.error("--live requires DP_PROVIDER=openai and DP_RUNNER=docker or kubernetes")
        summary = asyncio.run(evaluate(args.out, settings, args.label))
        print(f"Resolved {summary['resolved']}/{summary['case_count']}; kind={summary['kind']}")
        print(f"Artifacts: {args.out.resolve()}")
        if summary["resolved"] != summary["case_count"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
