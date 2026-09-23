# Portfolio narrative without inflated claims

**Product problem:** developers need a traceable path from repository evidence to
a reviewed, tested repair—not merely a convincing chatbot answer.

**Engineering contribution:** connect an open model to restricted MCP tools,
maintain exact approvals and independent test verification, operate that API with
container/cluster isolation, explicit release gates and observability.

Use claims that match your evidence. The packaged scripts and unit tests do not
prove that Qwen solved a benchmark, that a Kubernetes cluster was operated, or
that a company used this system. Record those exercises yourself before adding
them to a CV. Do not promise that this project guarantees a job.

Useful discussion topics: why MCP stdio rather than six unnecessary network
services; why SQLite means one replica; why shell allowlists alone are weak; why a
real exit status matters; how invalid native tool calls are handled; how a Job's
permissions differ from the control plane's; how readiness differs from liveness;
why GitOps auto-sync is paused for in-memory approvals; how restore is tested;
and why script replay must be separated from model quality.

Next evidence to add: live Qwen tool smoke, held-out debugging tasks, Docker image
scan, a real kind/Calico fixture run, a backup/restore drill, a short observed load
experiment, and a 2-minute demo showing the actual trace and failure cases.
