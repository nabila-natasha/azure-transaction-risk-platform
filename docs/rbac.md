# Azure RBAC

## Day 3 — Role-Based Access Control

### Objective

Day 3 establishes the authorization model for the Project 4 Azure
platform.

The goal is to give Azure services only the permissions they require to
perform their workload, rather than using broad subscription-level
permissions.

The first RBAC assignment was configured for Azure Data Factory access to
the Project 4 ADLS Gen2 storage account.

---

## ADF RBAC Assignment

The assignment is:

| Item            | Configuration                                            |
| --------------- | -------------------------------------------------------- |
| Identity        | `adf-transaction-bello` System Assigned Managed Identity |
| Target resource | `sttransactionbello`                                     |
| Scope           | Storage account                                          |
| Role            | `Storage Blob Data Contributor`                          |
| Purpose         | Allow ADF to read/write transaction data in ADLS Gen2    |

### Why This Identity?

The ADF System Assigned Managed Identity represents the Data Factory
workload itself.

Using this identity means the ADF pipeline can authenticate to Azure
resources without storing a storage account key, client secret, or personal
Azure credentials in the pipeline configuration.

The identity is also lifecycle-bound to the Data Factory resource.

---

### Why This Resource?

The target resource is:

`sttransactionbello`

This is the Project 4 ADLS Gen2 data lake where transaction data will be
ingested and processed.

ADF therefore needs data-plane access to this storage account for the batch
ingestion workload.

---

### Why This Scope?

The role assignment is scoped to the storage account rather than the
subscription or entire resource group.

This follows the principle of least privilege:

```text
Subscription
    │
    ├── Other Azure resources
    │
    └── sttransactionbello
            ↑
            │
      ADF permission
```

ADF receives access to the storage resource it needs without automatically
receiving the same permission across unrelated Project 4 resources.

A narrower container-level scope could be considered later if the workload
can be constrained to specific containers without affecting required
operations.

---

### Why This Role?

The selected role is:

`Storage Blob Data Contributor`

This is a data-plane role intended for working with data stored in Azure
Blob Storage / ADLS Gen2.

ADF requires the ability to perform storage data operations as part of the
batch ingestion workload.

The role was selected instead of a broad Azure management role because the
ADF workload does not need general control over the Azure subscription or
resource configuration.

---

## Why Not Owner or Contributor?

`Owner` and `Contributor` are broad Azure management roles.

Granting one of these roles to an ingestion workload would give it
permissions substantially beyond the requirement of reading and writing
data in the data lake.

The Project 4 design therefore separates:

```text
Authentication
       │
       ▼
Managed Identity
       │
       ▼
Authorization
       │
       ▼
Azure RBAC
       │
       ▼
Specific data resource
```

The identity receives only the access required for its workload.

---

## Management Plane vs Data Plane

Azure permissions can be thought about in two broad categories.

### Management Plane

Controls Azure resources themselves.

Examples include:

* Creating resources
* Deleting resources
* Changing resource configuration
* Managing networking or resource settings

### Data Plane

Controls access to the data inside a resource.

For this workload, ADF needs data-plane access to the ADLS storage account.

The RBAC assignment therefore uses a storage data role rather than granting
ADF broad resource-management permissions.

---

## Authentication vs Authorization

These concepts are deliberately separated.

### Authentication

**Who are you?**

ADF authenticates using its System Assigned Managed Identity.

### Authorization

**What are you allowed to do?**

Azure RBAC determines the operations permitted for that identity.

Therefore:

```text
ADF
 │
 │ System Assigned Managed Identity
 ▼
Authentication
 │
 ▼
Azure RBAC
 │
 │ Storage Blob Data Contributor
 ▼
sttransactionbello
```

---

## Day 3 Evidence

The RBAC assignment was verified in the Azure Portal IAM blade.

Evidence:

`docs/evidence/day03-adf-rbac.PNG`

The evidence shows the ADF managed identity receiving the
`Storage Blob Data Contributor` role at the Project 4 storage-account
scope.

---

## Day 3 Status

The first Project 4 workload identity has been connected to its required
Azure data resource using Azure RBAC.

The next step is to codify this authorization model in Terraform so that
the permission is reproducible rather than remaining a manually configured
Portal setting.

---

## Day 4 — Terraform-Managed RBAC

### Objective

Convert the Day 3 manually configured RBAC assignment into Terraform-managed infrastructure.

### Existing Day 3 Configuration

The ADF system-assigned managed identity was manually granted:

* **Resource:** `sttransactionbello`
* **Scope:** Storage account
* **Role:** `Storage Blob Data Contributor`
* **Identity:** `adf-transaction-bello`

This proved the RBAC configuration through the Azure Portal before introducing Infrastructure as Code.

### Terraform Configuration

The RBAC assignment is defined in:

```text
infra/terraform/rbac.tf
```

Terraform references the ADF system-assigned managed identity through its principal ID and assigns the required data-plane role to the ADLS Gen2 storage account.

The managed identity references are defined in:

```text
infra/terraform/managed-identities.tf
```

### Importing Existing Infrastructure

Because the RBAC assignment already existed in Azure from Day 3, Terraform did not automatically recognize it as a managed resource.

The existing Azure role assignment was therefore imported into Terraform state rather than creating a second assignment.

After import:

```text
terraform plan
```

returned:

```text
No changes. Your infrastructure matches the configuration.
```

This confirms that the existing Azure RBAC assignment and Terraform configuration are aligned.

### Why Import Was Required

Terraform does not automatically adopt manually created Azure resources simply because equivalent configuration exists in a `.tf` file.

Terraform management requires:

```text
Terraform configuration
        +
Terraform state
        ↓
Managed infrastructure
```

The import operation connected the existing Azure RBAC resource to Terraform state.

### Day 4 Result

The ADF managed identity's access to the transaction data lake is now represented and managed by Terraform.

This establishes the intended Project 4 progression:

```text
Day 3
Portal-first RBAC configuration
        ↓
Day 4
Terraform import + codification
        ↓
Future changes
Terraform plan → review → apply
```

### Validation

Terraform validation completed successfully:

```text
terraform validate
Success! The configuration is valid.
```

Terraform plan after importing the existing role assignment:

```text
No changes. Your infrastructure matches the configuration.
```

### Evidence

Recommended evidence:

```text
docs/evidence/day03-adf-rbac.PNG
```

The screenshot shows the Azure Portal RBAC assignment created during Day 3.


