# Changelog

## 0.3.0 - DevOps delivery edition

Adds actual application metrics and bounded OTLP spans; JSON operational logs;
separate metrics auth; startup/liveness/readiness probes; drain/resume; singleton
serving lease; validated downward Pod IP for authenticated scraping; a Kubernetes
Job test runner with immutable bounded snapshots, token-free test pods, scoped
RBAC, deadlines and cleanup; offline verified backups and restore-to-new-path.

Adds app/runner images, local monitoring Compose overlay, protected Helm chart,
kind/Calico lab with positive-control network check, GitOps promotion files, CI,
registry publication, scan gates, optional Terraform existing-cluster installer,
maintenance helpers and detailed operating/security/evidence documentation.

Preserves the explicit demo-vs-model boundary, five stdio MCP server groups,
protected original repositories, exact approval design and known fixture replay.
No multi-replica support, cloud account provisioning or measured real-LLM success
rate is introduced by this release. Consult docs/VALIDATION.md for checks actually run.

## 0.2.0 - local portfolio workbench

Original single-user debugging workbench with scripted fixture replay,
OpenAI-compatible model adapter, stdio MCP subset, approval and test evidence,
FastAPI/UI, restricted local Docker runner and initial CI/tests. Historical output
is retained in outputs-previous-0.2.0/ and is not current-version validation.
