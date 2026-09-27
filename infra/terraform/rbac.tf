# Day 4 — Azure RBAC assignments

resource "azurerm_role_assignment" "adf_storage_blob_contributor" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.adf_principal_id
}
