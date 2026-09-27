# Day 4 — Managed Identity references
#
# ADF and Synapse already use system-assigned managed identities.
# Their identities are created and lifecycle-managed by Azure.
# Terraform references those identities for RBAC assignments.

locals {
  adf_principal_id     = azurerm_data_factory.main.identity[0].principal_id
  synapse_principal_id = azurerm_synapse_workspace.main.identity[0].principal_id
}
