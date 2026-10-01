# Terraform Infrastructure

This directory contains the Infrastructure as Code (IaC) for the Azure Transaction Risk Platform.

Terraform is used to provision and manage the Azure resources required by Project 4.

---

## Purpose

The Terraform configuration provides a repeatable definition of the Azure infrastructure rather than requiring resources to be created manually through the Azure Portal.

The deployment workflow is:

```text
Terraform configuration
        ↓
terraform init
        ↓
terraform validate
        ↓
terraform plan
        ↓
Production approval
        ↓
terraform apply
```

---

## State Backend

Terraform state is stored remotely in Azure Storage.

The project uses:

```text
Storage account:
sttfstatebello

Container:
tfstate

State:
project4.tfstate
```

The remote backend keeps Terraform state separate from the Git repository.

---

## Authentication

Azure authentication is performed through Azure DevOps service connections and workload identity federation.

The pipeline service connection is:

```text
sc-transaction-risk-platform
```

This avoids storing long-lived Azure client secrets in the repository.

---

## CI/CD Integration

The CI pipeline runs:

```text
terraform init
terraform validate
terraform plan
```

The CD pipeline follows this workflow:

```text
Terraform Plan
      ↓
Saved tfplan
      ↓
Azure DevOps Pipeline Artifact
      ↓
terraform-production approval
      ↓
Terraform Apply
      ↓
Post-deployment smoke validation
```

The Apply stage uses the downloaded plan artifact:

```text
$(Pipeline.Workspace)/terraform-plan/tfplan
```

rather than relying on a plan file remaining in the Plan job's local working directory.

---

## Infrastructure Responsibilities

Terraform manages the Azure infrastructure required by the project, including the resources defined by the configuration under this directory.

Examples include:

```text
Resource groups
Storage
Event Hubs
Data Factory
Synapse
Managed identities
RBAC assignments
```

The exact resource configuration should be treated as the source of truth in the `.tf` files.

---

## Production Safety

The CD workflow uses the Azure DevOps environment:

```text
terraform-production
```

A production approval occurs before Terraform Apply.

After deployment, the pipeline performs smoke validation against:

```text
rg-transaction-risk-platform
```

---

## Rollback

Rollback procedures are documented in:

```text
docs/rollback.md
```

The project uses controlled Git/Terraform rollback rather than claiming automated infrastructure rollback.

---

## Important Files

```text
*.tf
    Terraform infrastructure definitions

*.tfvars.example
    Example variable structure where applicable

Backend configuration
    Remote Terraform state configuration

Outputs
    Useful deployment outputs where defined
```

Do not commit:

```text
Terraform state files
Secrets
Passwords
Service-principal credentials
Generated deployment artifacts
```

