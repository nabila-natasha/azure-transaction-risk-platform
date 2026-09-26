# Terraform

## Day 1 — Terraform Fundamentals and Remote State

### Day 1A: Disposable Local-State Sandbox

A disposable Terraform sandbox was used to learn the Terraform lifecycle
before managing the actual Project 4 infrastructure.

The sandbox demonstrated:

- Terraform provider configuration
- Variables and outputs
- `terraform init`
- `terraform validate`
- `terraform plan`
- `terraform apply`
- Terraform local state
- Azure resource inspection
- State drift
- `terraform destroy`

The sandbox resource group and storage account were deliberately destroyed
after the exercise.

### Day 1B: Remote State

The actual Project 4 infrastructure uses an Azure Storage backend for
Terraform state.

Resources created for the backend:

- Resource group: `rg-transaction-risk-platform`
- Storage account: `sttfstatebello`
- Blob container: `tfstate`
- Terraform state key: `project4.tfstate`

The backend is configured in:

`infra/terraform/backend.tf`

### Why Remote State?

Local state is suitable for an individual disposable Terraform exercise,
but the Project 4 infrastructure is intended to be operated through both
local development and Azure DevOps.

Remote state provides a shared state location so these execution
environments use the same Terraform state.

### Backend Bootstrap

The remote backend has a bootstrap dependency: Terraform cannot use an
Azure Storage backend before that storage account exists.

Therefore, the backend storage was created first. Terraform was then
configured to use the existing Azure Storage account and `tfstate`
container as its remote backend.

### Authentication

Terraform backend access uses Azure AD / Entra ID authentication:

`use_azuread_auth = true`

The signed-in Azure identity was granted the required Storage Blob Data
Contributor role on the state storage account.

No storage account access key was stored in the Terraform configuration.

### Project 4 Resource Isolation

Project 4 uses a dedicated resource group:

`rg-transaction-risk-platform`

Project 3 infrastructure in `rg-lakehouse-portfolio` is not reused or
managed by this Terraform configuration.

### Current Status

Day 1A and Day 1B are complete.

The Terraform remote backend is initialized successfully and ready for
the Project 4 infrastructure build beginning on Day 2.
