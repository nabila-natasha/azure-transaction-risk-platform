# Managed Identity

## Day 3 — Azure Managed Identity

### What Is a Managed Identity?

An Azure Managed Identity provides an Azure resource with an identity that
can be used to authenticate to other Azure services.

Instead of storing credentials such as:

* storage account keys
* client secrets
* application passwords

the Azure workload uses its managed identity.

---

## Project 4 Managed Identities

Project 4 currently provisions System Assigned Managed Identities for:

| Azure Resource          | Identity                         |
| ----------------------- | -------------------------------- |
| `adf-transaction-bello` | System Assigned Managed Identity |
| `syn-transaction-bello` | System Assigned Managed Identity |

These identities were created as part of the Terraform-managed Azure
resources.

---

## System Assigned Managed Identity

A System Assigned Managed Identity is tied to the lifecycle of its Azure
resource.

For example:

```text
adf-transaction-bello
        │
        └── System Assigned Managed Identity
```

If the Azure resource is deleted, its system-assigned identity is also
removed.

This makes the identity suitable for workload-specific authentication.

---

## Managed Identity and RBAC

Managed Identity and RBAC solve different problems.

### Managed Identity

Provides the workload identity used for authentication.

### Azure RBAC

Determines what that identity is authorized to access.

For Project 4:

```text
ADF
 │
 │ System Assigned Managed Identity
 ▼
Azure authentication
 │
 ▼
Azure RBAC
 │
 │ Storage Blob Data Contributor
 ▼
sttransactionbello
```

The managed identity alone does not automatically grant access to the
storage account.

The appropriate RBAC role assignment is also required.

---

## Why Managed Identity?

The Project 4 platform avoids embedding long-lived Azure credentials in
application or orchestration configuration wherever Azure Managed Identity
is supported.

This reduces credential-management overhead and supports the project's
secretless authentication objective.

It also allows Azure RBAC to control access independently of the identity
itself.

---

## Day 3 Example

For the ADF batch ingestion workload:

```text
ADF Pipeline
     │
     ▼
ADF Managed Identity
     │
     ▼
Azure RBAC
     │
     ▼
Storage Blob Data Contributor
     │
     ▼
sttransactionbello
```

ADF can therefore access the transaction data lake using its workload
identity rather than a storage account key.

---

## Relationship to Terraform

Day 3 intentionally begins with a Portal-first implementation.

This makes the Azure concepts visible before they are codified as
Infrastructure as Code.

Day 4 will move the RBAC configuration into Terraform so that the
authorization model becomes reproducible and reviewable through source
control.

---

## Day 3 Status

Managed Identity and RBAC have been demonstrated for the ADF workload.

The ADF System Assigned Managed Identity was inspected through Azure Portal,
and its access to the Project 4 ADLS Gen2 storage account was configured
using Azure RBAC.
