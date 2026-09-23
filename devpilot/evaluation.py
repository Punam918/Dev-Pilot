"""Reproducible synthetic acceptance checks; demo and live results never mix."""
from __future__ import annotations

import asyncio
import json
import platform
import shutil
import tempfile
from pathlib import Path

from . import __version__
from .config import Settings
from .demo import CASES, seed
from .runtime import RunManager
from .safety import Workspace, copy_workspace
from .tools.runner import run_tests


async def run_case(case_id: str, out_dir: Path, live_settings: Settings | None = None) -> dict:
    """Auto-approve only known fixture paths in this dedicated evaluation harness."""
    case = CASES[case_id]
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="devpilot-eval-") as directory:
        base = Path(directory)
        if live_settings:
            if live_settings.provider != "openai" or live_settings.runner not in {"docker", "kubernetes"}:
                raise ValueError("Live evaluation requires DP_PROVIDER=openai and DP_RUNNER=docker or kubernetes")
            parameters = live_settings.model_dump()
            parameters.update(workspace_dir=base / "workspace", data_dir=base / "state")
            config = Settings(_env_file=None, **parameters)
        else:
            config = Settings(_env_file=None, provider="demo", runner="host-trusted", trust_local_code=True,
                              workspace_dir=base / "workspace", data_dir=base / "state")
        seed(config.workspace_dir)
        manager = RunManager(config)
        run_id = manager.create(case["repo"], case["task"], "repair")
        try:
            while manager.active and not manager.active.done():
                run = manager.store.get(run_id)
                pending = run.get("pending_approval")
                if pending:
                    allowed = (pending["tool"] == "terminal__run_tests" or
                              (pending["tool"] == "files__replace_text" and pending["arguments"].get("path") == case["path"]))
                    try:
                        manager.decide(run_id, pending["id"], allowed)
                    except KeyError:
                        pass
                await asyncio.sleep(0.05)
            if manager.active:
                await manager.active
            run = manager.store.get(run_id)
            artifact_dir = config.data_dir / "runs" / run_id
            for name in ("changes.patch", "trace.json", "report.md"):
                if (artifact_dir / name).exists():
                    shutil.copy2(artifact_dir / name, out_dir / name)
            # Hidden from the model during the run, though intentionally public in source.
            grade = {"exit_code": None, "output": "Final workspace unavailable", "timed_out": False}
            if (artifact_dir / "workspace").exists():
                grading_root = base / "grading"
                copy_workspace(artifact_dir / "workspace", grading_root)
                reference = Path(__file__).parent / "graders" / f"{case_id}.py"
                (grading_root / "tests" / "test_hidden_evaluation.py").write_text(reference.read_text())
                grade = await asyncio.to_thread(run_tests, Workspace(grading_root), {
                    "runner": config.runner, "trust_local_code": config.trust_local_code,
                    "runner_image": config.runner_image, "tool_timeout": config.tool_timeout,
                    **{key: str(getattr(config, key)) for key in ("kube_api_url", "kube_namespace", "kube_token_file", "kube_ca_file", "kube_runtime_class", "kube_image_pull_secret")},
                    "kube_job_timeout": config.kube_job_timeout})
            (out_dir / "heldout-tests.json").write_text(json.dumps(grade, indent=2) + "\n")
            result = {"case": case_id, "status": run["status"], "provider": run["provider"], "model": run["model"],
                      "runner": run["runner"], "resolved": bool(run["status"] == "completed" and
                        run["verification"].get("verified") and grade["exit_code"] == 0
                        and not grade.get("timed_out") and not grade.get("output_limited")),
                      "verification": run["verification"], "heldout_exit_code": grade["exit_code"],
                      "metrics": run["metrics"], "run_id": run_id}
            (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            return result
        finally:
            await manager.shutdown()
            manager.telemetry.close()


async def evaluate(out_dir: Path, live_settings: Settings | None = None, label: str = "local") -> dict:
    results = []
    for case_id in CASES:
        print(f"Running {case_id} ({'live model' if live_settings else 'scripted replay'})...", flush=True)
        results.append(await run_case(case_id, out_dir / case_id, live_settings))
    successes = sum(r["resolved"] for r in results)
    summary = {"schema_version": 1, "project_version": __version__, "label": label,
               "kind": "live-model-synthetic-evaluation" if live_settings else "scripted-integration-replay",
               "python": platform.python_version(), "case_count": len(results), "resolved": successes,
               "resolution_rate": successes / len(results),
               "not_a_model_benchmark": live_settings is None,
               "limitations": ["Three small synthetic Python tasks; not representative of real GitHub issues",
                               "Demo actions are predefined; demo resolution rate is not model accuracy",
                               "Timing includes process startup and evaluation approvals",
                               "Public fixture/reference code may create training or inspection contamination"],
               "settings": None if live_settings is None else {k: getattr(live_settings, k) for k in
                   ("model", "runner", "temperature", "max_steps", "max_output_tokens", "runner_image")},
               "results": results}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# " + ("Live-model synthetic evaluation" if live_settings else "Scripted integration replay"), "",
             "**This is not a broad capability benchmark. Demo runs do not call a language model.**", "",
             "| Case | Provider | Held-out test exit | Resolved | Tool calls | Wall time (s) |",
             "|---|---|---:|---|---:|---:|"]
    for result in results:
        lines.append(f"| {result['case']} | {result['provider']} | {result['heldout_exit_code']} | {result['resolved']} | {result['metrics']['tool_calls']} | {result['metrics']['wall_ms']/1000:.2f} |")
    lines += ["", "See each case's trace, patch, test output, and report for evidence.", "",
              "## Limitations", "", *[f"- {item}" for item in summary["limitations"]], ""]
    (out_dir / "summary.md").write_text("\n".join(lines))
    return summary
