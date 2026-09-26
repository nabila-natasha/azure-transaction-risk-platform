terraform {
  backend "azurerm" {
    resource_group_name  = "rg-transaction-risk-platform"
    storage_account_name = "sttfstatebello"
    container_name       = "tfstate"
    key                  = "project4.tfstate"

    use_azuread_auth = true
  }
}
