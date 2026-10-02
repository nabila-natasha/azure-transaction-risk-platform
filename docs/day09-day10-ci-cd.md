# Day 9–10: Azure DevOps CI/CD with Terraform

## Overview

Days 9–10 implement a CI/CD workflow for the Azure Transaction Risk Platform using:

* GitHub for source control
* Azure DevOps Pipelines for CI/CD orchestration
* Terraform for Infrastructure as Code
* Azure Resource Manager service connection using Workload Identity Federation (WIF)
* Azure Storage as the Terraform remote state backend
* Azure DevOps Pipeline Artifacts to transfer the Terraform plan between deployment jobs
* Azure DevOps Environments and approval checks for controlled deployment
* A self-hosted Azure DevOps agent running in Azure Cloud Shell

The implementation separates **Continuous Integration (CI)** from **Continuous Deployment (CD)** into two Azure DevOps pipelines.

---

# 1. CI/CD Architecture

```text
                         GitHub
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
  azure-pipelines-ci.yml      azure-pipelines-cd.yml
             │                           │
             ▼                           ▼
           CI Pipeline                CD Pipeline
             │                           │
     ┌───────┴────────┐          ┌──────┴───────┐
     │                │          │              │
     ▼                ▼          ▼              ▼
 Python validation   Terraform   Terraform     Approval
                     Plan        Plan            │
     │                │          │               ▼
     │                │          │          Terraform Apply
     │                │          │               │
     └────────────────┘          └───────────────┘
                                             │
                                             ▼
                                      Azure infrastructure
```

The current implementation uses **two separate Azure DevOps pipelines**.

The CI pipeline does not automatically trigger the CD pipeline. The CD pipeline is run separately after CI validation has succeeded.

---

# 2. Day 9 — Continuous Integration

## CI pipeline

File:

```text
azure-pipelines-ci.yml
```

The CI pipeline performs automated validation before infrastructure deployment.

### CI workflow

```text
GitHub source code
       │
       ▼
Checkout repository
       │
       ▼
Verify build environment
       │
       ▼
Install Python dependencies
       │
       ▼
Compile Python code
       │
       ▼
Run tests if test files exist
       │
       ▼
Authenticate to Azure
       │
       ▼
Terraform init
       │
       ▼
Terraform validate
       │
       ▼
Terraform plan
```

## Python validation

The pipeline installs project dependencies and validates Python syntax with:

```bash
python -m compileall .
```

Pytest is installed and executed when actual Python test files exist.

The pipeline does not fabricate test results when the repository does not contain tests. If no test files are present, the pipeline reports that the test suite is not yet implemented and continues.

## Azure authentication

The pipeline uses the Azure DevOps service connection:

```text
sc-transaction-risk-platform
```

The service connection uses:

* Azure Resource Manager
* Workload Identity Federation
* an automatically managed Microsoft Entra application/service principal
* subscription-level scope

No Azure client secret is stored in the repository.

## Terraform backend

Terraform uses Azure Storage as its remote backend:

```text
Resource Group:    rg-transaction-risk-platform
Storage Account:   sttfstatebello
Container:         tfstate
State Key:         project4.tfstate
```

The backend uses Azure AD authentication:

```hcl
backend "azurerm" {
  resource_group_name  = "rg-transaction-risk-platform"
  storage_account_name = "sttfstatebello"
  container_name       = "tfstate"
  key                  = "project4.tfstate"

  use_azuread_auth = true
}
```

The WIF service principal was granted:

```text
Storage Blob Data Contributor
```

on the Terraform state storage account.

This allows the pipeline identity to access Terraform state without storing a storage account key.

## Terraform validation

The CI pipeline executes:

```bash
terraform init
terraform validate
terraform plan -out=tfplan
```

`terraform plan` calculates the infrastructure changes without applying them.

The `-out=tfplan` option saves the execution plan to a file.

---

# 3. Day 10 — Continuous Deployment

## CD pipeline

File:

```text
azure-pipelines-cd.yml
```

The CD pipeline contains two stages:

```text
Plan
  │
  ▼
Approval
  │
  ▼
Apply
```

Azure DevOps stages provide logical boundaries between groups of jobs, and deployment jobs can target an Azure DevOps Environment.

---

# 4. CD Plan Stage

The CD Plan stage checks out the repository and initializes Terraform:

```bash
terraform init
terraform validate
terraform plan -out=tfplan
```

This creates:

```text
infra/terraform/tfplan
```

The `tfplan` file is a saved Terraform execution plan.

It represents the infrastructure changes Terraform intends to make.

The Plan stage does **not** apply the infrastructure.

Terraform documentation describes this two-step workflow as useful for automation because a saved plan can later be passed directly to `terraform apply`.

---

# 5. Pipeline Artifact

The CD Plan stage publishes the saved plan:

```yaml
- publish: infra/terraform/tfplan
  artifact: terraform-plan
```

An Azure DevOps Pipeline Artifact is a file or collection of files stored by Azure DevOps so that another job or stage can consume them later.

The flow is:

```text
Plan job

infra/terraform/tfplan
        │
        ▼
Publish
        │
        ▼
Azure DevOps Pipeline Artifact
        │
        ▼
terraform-plan
    └── tfplan
```

The artifact is **not another Terraform plan**.

It is simply the saved `tfplan` file being transferred between pipeline execution boundaries.

---

# 6. Agent Selection and Execution Environment

## Microsoft-hosted Agent — Initial Attempt

The initial Day 9 configuration attempted to use a Microsoft-hosted Linux x64 agent:

```yaml
pool:
  vmImage: ubuntu-latest
```

The pipeline configuration itself was valid, but Azure DevOps reported that the organization had:

```text
max concurrent = 0
```

for Microsoft-hosted parallel jobs.

This meant Azure DevOps could not allocate a Microsoft-hosted worker to execute the pipeline.

This was an **agent availability/capacity limitation**, not a failure in the Python code, Terraform configuration, GitHub integration, or Azure authentication.

---

## Self-hosted Agent — Final Implementation

The project was then configured to use a self-hosted Linux x64 Azure DevOps agent hosted in Azure Cloud Shell.

The pipeline uses:

```yaml
pool:
  name: Default
```

The registered agent is:

```text
bello-cloudshell
```

The execution path is:

```text
GitHub
   │
   ▼
Azure DevOps
   │
   ▼
Default Agent Pool
   │
   ▼
bello-cloudshell
   │
   ▼
Azure Cloud Shell
(Linux x64)
   │
   ├── Python / pytest
   ├── Terraform
   └── Azure CLI
```

### Microsoft-hosted vs. Self-hosted

Both approaches can use Linux x64. The important difference is **who provides and manages the execution machine**.

|                        | Microsoft-hosted                            | Self-hosted                  |
| ---------------------- | ------------------------------------------- | ---------------------------- |
| Worker                 | Microsoft-provided temporary VM             | User-managed environment     |
| Example                | `ubuntu-latest`                             | `bello-cloudshell`           |
| Pipeline configuration | `vmImage`                                   | `name: Default`              |
| Operating system       | Linux x64                                   | Linux x64                    |
| Tool environment       | Microsoft-managed image                     | User-managed                 |
| Capacity               | Depends on hosted parallel-job availability | Uses the registered agent    |
| Lifecycle              | Temporary execution environment             | Registered agent environment |

For this portfolio, the self-hosted agent was selected because the Microsoft-hosted option had no available concurrent job capacity.

---

## Final CI Trigger Validation

The final GitHub-to-Azure DevOps integration was validated by pushing directly from the terminal:

```bash
git push origin main
```

The verified execution path was:

```text
GitHub Push
     │
     ▼
Azure DevOps CI
     │
     ▼
Default Agent Pool
     │
     ▼
bello-cloudshell
     │
     ▼
Python Tests
     │
     ▼
Terraform Plan
     │
     ▼
CI Successful
```

Azure DevOps run:

```text
#20261001.11
```

was created from the repository push and completed successfully.

This confirms that a push to `main` automatically triggers the CI pipeline.

The CD pipeline remains a separate controlled release workflow and is **not automatically triggered by CI**. CD is run manually after CI validation and uses the approval-controlled `terraform-production` environment before Terraform Apply.

---

# 7. Apply Stage

The Apply stage uses a deployment job targeting:

```text
terraform-production
```

The environment provides a controlled deployment boundary and approval mechanism.

The Apply job first downloads the artifact:

```yaml
- download: current
  artifact: terraform-plan
```

Azure DevOps places the downloaded artifact in the pipeline workspace.

The Terraform plan is therefore available at:

```text
$(Pipeline.Workspace)/terraform-plan/tfplan
```

The Apply stage then runs:

```bash
terraform apply -auto-approve "$(Pipeline.Workspace)/terraform-plan/tfplan"
```

Terraform reads the saved plan and executes the operations contained in it.

Terraform does **not** download the plan. Azure DevOps performs the artifact download; Terraform consumes the resulting file.

---

# 8. Approval Gate

The deployment job targets:

```text
terraform-production
```

A manual approval check is configured on this Azure DevOps Environment.

The deployment therefore follows:

```text
Terraform Plan
      │
      ▼
Publish tfplan
      │
      ▼
Approval required
      │
      ▼
Approved
      │
      ▼
Download tfplan
      │
      ▼
Terraform Apply
```

Azure DevOps supports approval checks on environments to control when a deployment stage can proceed.

---

# 9. Why the Apply Stage Uses the Saved Plan

A saved Terraform plan provides a clear separation between:

### Planning

```bash
terraform plan -out=tfplan
```

and:

### Execution

```bash
terraform apply tfplan
```

The Plan stage determines what Terraform intends to change.

The approval happens after the plan is generated.

The Apply stage then executes that saved plan.

This is different from simply running:

```bash
terraform apply
```

because `terraform apply` without a saved plan can generate a new plan and request approval itself. When a saved plan is supplied, Terraform executes the operations contained in that plan.

---

# 10. CI Plan vs CD Plan

The current portfolio implementation has both CI and CD performing Terraform planning, but they serve different purposes.

### CI

The CI plan is a **validation step**.

Its purpose is to determine whether the Terraform configuration can initialize, validate, authenticate, and produce a plan successfully.

### CD

The CD plan is the **deployment plan** used by the subsequent Apply stage.

The CD Plan stage creates:

```text
tfplan
```

publishes it as an artifact, and the Apply stage consumes that artifact after approval.

Therefore:

```text
CI
└── Validate infrastructure changes

CD
├── Generate deployment plan
├── Publish plan artifact
├── Obtain approval
└── Apply saved plan
```

The current implementation intentionally keeps CI and CD as separate Azure DevOps pipelines so that infrastructure validation and controlled infrastructure deployment remain distinct lifecycle stages.

---

# 11. Roles of the Main Components

## GitHub

GitHub is the source-control system.

It stores:

* Python code
* Terraform configuration
* documentation
* CI YAML
* CD YAML

GitHub does not directly create the Azure infrastructure in this workflow.

---

## Azure DevOps

Azure DevOps is the **pipeline orchestrator**.

It:

* checks out the GitHub repository
* runs CI/CD jobs
* executes commands on the self-hosted agent
* stores pipeline artifacts
* manages the deployment environment
* enforces approval checks
* records pipeline and deployment history

Azure DevOps is therefore coordinating the workflow rather than being the tool that defines the Azure infrastructure.

---

## Terraform

Terraform is the **Infrastructure as Code engine**.

It:

* reads the `.tf` configuration
* compares desired configuration with current infrastructure state
* creates an execution plan
* manages Terraform state
* communicates with Azure through the AzureRM provider
* applies the approved infrastructure changes

Terraform is the component that actually determines and executes the Azure infrastructure changes.

---

## Azure

Azure is the **target infrastructure platform**.

Terraform communicates with Azure and creates or updates resources such as:

* Resource Groups
* Storage Accounts
* Azure Data Factory
* Event Hubs
* Synapse resources
* Managed Identities
* RBAC assignments
* other resources defined in the Terraform configuration

Azure therefore contains the infrastructure that Terraform manages.

---

# 12. Overall Responsibility Model

A useful way to remember the architecture is:

```text
GitHub
"What code should we use?"
        │
        ▼
Azure DevOps
"When and in what order should the workflow run?"
        │
        ▼
Terraform
"What Azure infrastructure should exist,
and what changes are required?"
        │
        ▼
Azure
"Actually host and operate those resources."
```

For deployment:

```text
GitHub
   ↓
Azure DevOps
   ↓
Terraform Plan
   ↓
Approval
   ↓
Terraform Apply
   ↓
Azure infrastructure
```

---

# 13. Security

The pipeline avoids storing Azure credentials in GitHub.

Authentication is based on:

```text
Azure DevOps
      │
      ▼
Workload Identity Federation
      │
      ▼
Microsoft Entra service principal
      │
      ▼
Azure RBAC
```

Terraform state is stored remotely in Azure Storage using Azure AD authentication.

The Synapse SQL administrator password is supplied through an Azure DevOps secret variable:

```text
SYNAPSE_SQL_ADMIN_PASSWORD
```

The password is not committed to GitHub.

---

# 14. Day 9 Evidence

The completed CI pipeline demonstrates:

* successful Python environment validation
* successful dependency installation
* Python syntax validation
* conditional test execution
* Azure authentication
* Terraform backend initialization
* Terraform validation
* Terraform plan
* secure WIF authentication
* remote Terraform state
* Azure RBAC for Terraform state access

---

# 15. Day 10 Evidence

The completed CD pipeline demonstrates:

* separate deployment pipeline
* Terraform Plan stage
* saved Terraform plan
* Azure DevOps Pipeline Artifact
* artifact download between jobs
* Azure DevOps deployment environment
* manual approval gate
* Terraform Apply stage
* successful infrastructure deployment
* troubleshooting of artifact path handling

---

# 16. Troubleshooting Evidence

During implementation, the CD Apply stage initially failed because Terraform searched for:

```text
infra/terraform/tfplan
```

after the artifact had been downloaded to the Azure DevOps pipeline workspace.

The Apply command was corrected to reference:

```text
$(Pipeline.Workspace)/terraform-plan/tfplan
```

This demonstrated the distinction between:

1. a file created inside a pipeline job,
2. a published Azure DevOps artifact,
3. downloading that artifact into another job, and
4. Terraform consuming the downloaded saved plan.

---

# 17. Final CI/CD Flow

```text
                         GITHUB
                           │
                           │
             ┌─────────────┴─────────────┐
             │                           │
             ▼                           ▼
   azure-pipelines-ci.yml      azure-pipelines-cd.yml
             │                           │
             ▼                           ▼
        CI PIPELINE                 CD PIPELINE
             │                           │
             ▼                           ▼
   Python validation               PLAN STAGE
             │                           │
             ▼                           ▼
    Terraform init/validate        terraform plan
             │                           │
             ▼                           ▼
      Terraform plan              saved tfplan
             │                           │
             │                           ▼
             │                   publish artifact
             │                           │
             │                           ▼
             │                  terraform-production
             │                           │
             │                           ▼
             │                      APPROVAL
             │                           │
             │                           ▼
             │                  download tfplan
             │                           │
             │                           ▼
             │                  terraform apply
             │                           │
             │                           ▼
             │                   AZURE RESOURCES
             │
             ▼
        CI SUCCESS
```

## Outcome

Day 9 establishes automated infrastructure validation through Azure DevOps CI.

Day 10 establishes controlled infrastructure deployment through a separate Azure DevOps CD pipeline using a saved Terraform plan, pipeline artifacts, an approval-controlled deployment environment, and Terraform Apply.
