variable "location" {
  description = "Azure region for the disposable Terraform sandbox"
  type        = string
  default     = "Southeast Asia"
}

variable "resource_group_name" {
  description = "Name of the disposable resource group"
  type        = string
  default     = "rg-tfday1-sandbox"
}

variable "storage_account_name" {
  description = "Globally unique storage account name"
  type        = string
  default     = "tfsandboxbello01"
}
