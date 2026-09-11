# Optional Terraform delivery

Use this **instead of Argo CD**, never alongside it for the same release. It
installs the local Helm chart on an **existing** Kubernetes cluster. There is no
cloud account, VPC, GPU provisioning, automatic secret creation or cloud cost.

Prerequisites: Terraform >=1.10, explicit kubeconfig context, prepared app/runner
namespaces, enforcing CNI, existing Secret, registry access, reviewed values.
Follow `../docs/KUBERNETES.md` for those prerequisites. Then:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Review and edit terraform.tfvars. Keep it out of Git.
terraform init
terraform fmt -check
terraform validate
terraform plan -out=change.tfplan
# Drain and finish any active run before an update. Read the complete plan.
terraform apply change.tfplan
```

The provider is pinned. Commit `.terraform.lock.hcl` after a trusted `init`; no
provider checksum lock is fabricated in this archive. Protect Terraform state
with encrypted, access-controlled remote storage and locking for shared use.
State and plan files can be sensitive even though this module never reads Secret
contents. The default backend is local for the lab. `prevent_destroy` blocks
accidental removal through Terraform, not administrator actions or disk loss.
Terraform CLI/provider operations were not executable in the packaging sandbox.
