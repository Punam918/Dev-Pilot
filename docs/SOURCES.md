# Official references and version decisions

Reviewed for this 0.3.0 package on 2026-09-16. These are vendor specifications/documentation, not evidence that a deployment or GPU benchmark was executed here. Lab version pins are reviewable candidates, **not vulnerability-free certifications or a promise of latest versions**.

## Application, protocol and models

- [MCP 2025-06-18 lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle): the included bespoke stdio subset targets this dated contract, not full/latest MCP certification.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk): optional interoperability acceptance test, not the shipped protocol implementation.
- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility): local HTTP adapter configuration.
- [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507): the distinct non-thinking instruct checkpoint in the vLLM path.
- [vLLM tool calling](https://docs.vllm.ai/en/latest/features/tool_calling/): automatic tool choice, supported model parsers and version-dependent requirements.
- [vLLM metrics](https://docs.vllm.ai/en/v0.18.2/design/metrics/): separate inference monitoring; these model metrics are not fabricated by the application dashboard.

## Delivery and orchestration

- [GitHub container publishing](https://docs.github.com/actions/publishing-packages/publishing-docker-images): registry workflow permissions and publishing patterns.
- [GitHub artifact attestations](https://docs.github.com/actions/how-tos/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds): distinguish signed GitHub attestations from the BuildKit SBOM/provenance attachments used here.
- [checkout v5 commit](https://github.com/actions/checkout/commit/08c6903cd8c0fde910a37f88322edcfb5dd907a8), [setup-python v6 commit](https://github.com/actions/setup-python/commit/e797f83bcb11b83ae66e0230d6156d7c80228e7c), and [upload-artifact v5 commit](https://github.com/actions/upload-artifact/commit/330a01c490aca151604b8cf639adc76d48f6c5d4): reviewed Node 24 action pins, not mutable tags. Hosted runner compatibility remains a CI check.
- [Kubernetes probe semantics](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/): separate liveness, readiness and startup responsibilities.
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/): job deadlines, completed pod status, cleanup and retry controls.
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/): restricted admission requirements; not a substitute for a hostile-code sandbox.
- [Network policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/): policies require an enforcing network plugin.
- [Calico with kind](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind): disable kind's default CNI and install Calico; the lab selects manifest v3.32.2.
- [Helm values](https://helm.sh/docs/chart_template_guide/values_files/) and [Helm v3.19.0 release](https://github.com/helm/helm/releases/tag/v3.19.0): chart composition and official Linux-amd64 download checksum used by install-helm.sh. Helm itself could not be downloaded/executed in the packaging environment.
- [Argo CD auto-sync](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/): automatic sync deliberately disabled for the single-writer, in-process-approval application.
- [Terraform Helm provider](https://registry.terraform.io/providers/hashicorp/helm/latest/docs) and [Helm release resource](https://registry.terraform.io/providers/hashicorp/helm/latest/docs/resources/release): provider v3.3.0 existing-cluster installation; lock/provider initialization not executed here.

## Observability

- [Prometheus alert rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/) and [rule unit tests](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/): shipped rule tests are run with real promtool by CI, not interpreted as passed merely because YAML parses.
- [OpenTelemetry Python exporters](https://opentelemetry.io/docs/languages/python/exporters/): actual optional OTLP HTTP integration, tested locally against a capture receiver. This is not a claim that the Collector/Tempo stack ran here.

Container images (Prometheus, Grafana, Alertmanager, Collector, Tempo, vLLM), Python package constraints and base-image tags must be re-reviewed before publication. The repository includes update mechanisms and scan gates; it does not bundle model weights, vendor binaries, cloud credentials or current vulnerability scan results.
