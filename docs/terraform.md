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


---

## Day 2 — Azure Infrastructure Provisioning

### Objective

Day 2 used Terraform to provision the core Azure infrastructure for the
Production-Oriented Transaction Risk Analytics Platform.

The infrastructure is managed from:

`infra/terraform/`

Terraform uses the remote Azure Storage backend established on Day 1.

### Resources Provisioned

The following Project 4 resources were provisioned:

| Component            | Azure Resource                 | Purpose                             |
| -------------------- | ------------------------------ | ----------------------------------- |
| Resource Group       | `rg-transaction-risk-platform` | Isolates Project 4 infrastructure   |
| ADLS Gen2            | `sttransactionbello`           | Transaction data lake               |
| Event Hubs Namespace | `eh-transaction-bello`         | Streaming ingestion infrastructure  |
| Event Hub            | `transaction-events`           | Transaction event stream            |
| Data Factory         | `adf-transaction-bello`        | Batch ingestion and orchestration   |
| ADLS Filesystem      | `synapse`                      | Synapse workspace storage           |
| Synapse              | `syn-transaction-bello`        | Serverless analytical serving layer |

Terraform manages all seven resources above.

The Terraform state itself remains separate from the application data lake
and is stored in:

`sttfstatebello/tfstate/project4.tfstate`

### Infrastructure Design

The main Terraform resources are separated into purpose-specific files:

```text
infra/terraform/
├── backend.tf
├── data-factory.tf
├── event-hubs.tf
├── outputs.tf
├── resource-group.tf
├── storage.tf
├── synapse.tf
├── variables.tf
└── versions.tf
```

This keeps the infrastructure configuration organized by Azure service
while allowing Terraform to manage the platform as one deployment.

### Managed Identity

Azure Data Factory and Synapse were provisioned with
System Assigned Managed Identities.

The identities are created as part of the infrastructure deployment.

Their Azure RBAC permissions are intentionally configured separately on
Day 3 so that access can be reviewed and assigned according to least
privilege.

Therefore, Day 2 establishes the identities and resources; Day 3
establishes the identity-to-resource authorization model.

### Event Hubs Configuration

The Event Hubs namespace uses the Standard tier with one capacity unit.

The `transaction-events` Event Hub was provisioned with:

* 4 partitions
* 1-day message retention

The Event Hub provides the streaming ingestion path for transaction events.

### ADLS Gen2 Configuration

The project data lake storage account is:

`sttransactionbello`

It is configured as an Azure StorageV2 account with:

* Hierarchical namespace enabled
* Standard performance
* Locally redundant storage
* TLS 1.2 minimum
* Public blob access disabled

The storage account is separate from the Terraform remote-state storage
account.

### Synapse Configuration

The Synapse workspace is:

`syn-transaction-bello`

The workspace was provisioned for the serverless analytical serving layer.
No Dedicated SQL pool was provisioned as part of Day 2.

### Terraform Outputs

Terraform outputs were added for the primary Project 4 resources so that
resource names can be retrieved without inspecting the state manually.

Sensitive credentials, including the Synapse SQL administrator password,
are not exposed through Terraform outputs.

### Validation

After deployment, Terraform state contained seven managed resources.

The final validation command was:

```bash
terraform validate
terraform plan
```

Validation succeeded and the final plan reported:

```text
No changes. Your infrastructure matches the configuration.
```

This confirms that the deployed Azure infrastructure matches the current
Terraform configuration with no detected infrastructure drift at the time
of validation.

### Day 2 Status

Day 2 is complete.

The core Azure infrastructure is provisioned and tracked by the remote
Terraform backend.

Day 3 will focus on Azure RBAC, Managed Identity permissions, and the
least-privilege access model.

