variable "location" {
  description = "Azure region for Project 4 resources"
  type        = string
  default     = "Southeast Asia"
}

variable "resource_group_name" {
  description = "Resource group for Project 4"
  type        = string
  default     = "rg-transaction-risk-platform"
}

variable "storage_account_name" {
  description = "ADLS Gen2 storage account for transaction data"
  type        = string
  default     = "sttransactionbello"
}

variable "event_hubs_namespace_name" {
  description = "Event Hubs namespace"
  type        = string
  default     = "eh-transaction-bello"
}

variable "event_hub_name" {
  description = "Event Hub for transaction streaming"
  type        = string
  default     = "transaction-events"
}

variable "data_factory_name" {
  description = "Azure Data Factory instance"
  type        = string
  default     = "adf-transaction-bello"
}

variable "synapse_workspace_name" {
  description = "Azure Synapse workspace"
  type        = string
  default     = "syn-transaction-bello"
}

variable "synapse_sql_admin_password" {
  description = "SQL administrator password for Synapse workspace"
  type        = string
  sensitive   = true
}
