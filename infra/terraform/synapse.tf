resource "azurerm_storage_data_lake_gen2_filesystem" "synapse" {
  name               = "synapse"
  storage_account_id = azurerm_storage_account.lake.id
}

resource "azurerm_synapse_workspace" "main" {
  name                                 = var.synapse_workspace_name
  resource_group_name                  = azurerm_resource_group.main.name
  location                             = azurerm_resource_group.main.location
  storage_data_lake_gen2_filesystem_id = azurerm_storage_data_lake_gen2_filesystem.synapse.id
  sql_administrator_login              = "synadmin"
  sql_administrator_login_password     = var.synapse_sql_admin_password

  identity {
    type = "SystemAssigned"
  }

  tags = {
    project = "transaction-risk-platform"
    layer   = "serving"
  }
}
