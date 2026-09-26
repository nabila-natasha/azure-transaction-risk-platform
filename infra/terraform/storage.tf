resource "azurerm_storage_account" "lake" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  account_kind = "StorageV2"

  is_hns_enabled = true

  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  tags = {
    project = "transaction-risk-platform"
    layer   = "data-lake"
  }
}
