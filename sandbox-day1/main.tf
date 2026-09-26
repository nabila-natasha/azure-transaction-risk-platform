resource "azurerm_resource_group" "sandbox" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_storage_account" "sandbox" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.sandbox.name
  location                 = azurerm_resource_group.sandbox.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}
