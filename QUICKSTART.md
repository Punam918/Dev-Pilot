# Dev-Pilot Quickstart

Dev-Pilot is a local, approval-gated debugging workbench. It investigates a repository copy, proposes changes, asks before edits or test runs, records evidence, and exports a patch/report/trace.

## Run Locally

From this folder:

```bash
./setup.sh
./run.sh
```

Open the URL printed by `run.sh`, usually:

```text
http://127.0.0.1:8091
```

The script also prints the access token. Paste it into the UI and click **Connect**.

## Demo Flow

1. Select `demo-redis`, `demo-pagination`, or `demo-normalize`.
2. Use the prefilled task or write your own.
3. Click **Investigate**.
4. Approve or deny each requested action.
5. Review the execution trace and run summary.
6. Download the patch, report, or trace when the run finishes.

## Stop The App

If the server is running in the current terminal, press `Ctrl+C`.

From another terminal:

```bash
./stop.sh
```

## Ports And Data

Default script values:

```text
Port:     8091
Data dir: .devpilot-local
```

Override them like this:

```bash
DP_PORT=8092 DP_DATA_DIR=.devpilot-demo ./run.sh
```

## Docker Note

The project supports Docker Compose:

```bash
docker compose up -d --build
```

On this machine, Docker built the image but failed to run the container with:

```text
operation not permitted
```

That points to a local Docker/security/runtime restriction, not a DevPilot application bug. The Python run path above avoids that issue.

To test Docker separately:

```bash
docker run --rm hello-world
docker run --rm python:3.12-slim-bookworm python --version
```
