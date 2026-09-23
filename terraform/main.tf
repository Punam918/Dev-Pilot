# OPTIONAL alternative to Argo CD, NOT an additional owner of the same release.
# Existing cluster only. This does not create cloud VMs, GPUs, a VPC or a database.
terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "3.3.0"
    }
  }
}
provider "helm" {
  kubernetes = {
    config_path    = pathexpand(var.kubeconfig_path)
    config_context = var.kube_context
  }
}
resource "helm_release" "devpilot" {
  name             = "devpilot"
  namespace        = var.namespace
  chart            = "${path.module}/../helm/devpilot"
  create_namespace = false
  wait             = true
  atomic           = true
  timeout          = 300
  values           = [file(var.values_file)]
  # Secrets, runner namespace, CNI and RBAC bootstrap are explicit prerequisites.
  # Drain the existing agent and verify no active run BEFORE terraform apply.
  lifecycle {
    prevent_destroy = true
  }
}
