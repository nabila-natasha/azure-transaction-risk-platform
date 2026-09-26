output "resource_group_name" {
  description = "Name of the Terraform-managed resource group"
  value       = azurerm_resource_group.sandbox.name
}

output "storage_account_name" {
  description = "Name of the Terraform-managed storage account"
  value       = azurerm_storage_account.sandbox.name
}
