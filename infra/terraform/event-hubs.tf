resource "azurerm_eventhub_namespace" "main" {
  name                = var.event_hubs_namespace_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  sku      = "Standard"
  capacity = 1

  tags = {
    project = "transaction-risk-platform"
    layer   = "streaming"
  }
}

resource "azurerm_eventhub" "transactions" {
  name              = var.event_hub_name
  namespace_id      = azurerm_eventhub_namespace.main.id
  partition_count   = 4
  message_retention = 1
}
