output "resource_group_name" {
  description = "Project 4 resource group"
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  description = "Project 4 ADLS Gen2 storage account"
  value       = azurerm_storage_account.lake.name
}

output "event_hubs_namespace_name" {
  description = "Project 4 Event Hubs namespace"
  value       = azurerm_eventhub_namespace.main.name
}

output "event_hub_name" {
  description = "Project 4 Event Hub"
  value       = azurerm_eventhub.transactions.name
}

output "data_factory_name" {
  description = "Project 4 Data Factory"
  value       = azurerm_data_factory.main.name
}

output "synapse_workspace_name" {
  description = "Project 4 Synapse workspace"
  value       = azurerm_synapse_workspace.main.name
}
