variable "kubeconfig_path" {
  type        = string
  description = "Operator-local kubeconfig path; no credential bytes in Terraform variables."
  default     = "~/.kube/config"
}
variable "kube_context" {
  type        = string
  description = "REQUIRED explicit context. Never silently deploy to the current context."
  validation {
    condition     = length(trimspace(var.kube_context)) > 0
    error_message = "Specify an explicit kube_context."
  }
}
variable "namespace" {
  type    = string
  default = "devpilot"
}
variable "values_file" {
  type        = string
  description = "Reviewed YAML values with BOTH immutable image digests and model configuration."
}
