# Azure Kubernetes Service (AKS) - Node Fleet
# Final pillar of the Sovereign Omniverse, expanding orchestration to Microsoft Azure.

provider "azurerm" {
  features {}
  # Authentication is assumed via az login / service principal env vars
  # ARM_CLIENT_ID, ARM_CLIENT_SECRET, ARM_SUBSCRIPTION_ID, ARM_TENANT_ID
}

# 1. Azure Resource Group
resource "azurerm_resource_group" "alti_rg" {
  name     = "alti-analytics-${var.environment}-rg"
  location = var.azure_region
}

# 2. Underlying Virtual Network (VNet)
resource "azurerm_virtual_network" "alti_vnet" {
  name                = "alti-azure-vnet-${var.environment}"
  location            = azurerm_resource_group.alti_rg.location
  resource_group_name = azurerm_resource_group.alti_rg.name
  address_space       = ["10.2.0.0/16"]
}

resource "azurerm_subnet" "aks_subnet" {
  name                 = "aks-subnet"
  resource_group_name  = azurerm_resource_group.alti_rg.name
  virtual_network_name = azurerm_virtual_network.alti_vnet.name
  address_prefixes     = ["10.2.1.0/24"]
}

# 3. AKS Cluster Definition
resource "azurerm_kubernetes_cluster" "primary" {
  name                = "alti-analytics-${var.environment}-aks"
  location            = azurerm_resource_group.alti_rg.location
  resource_group_name = azurerm_resource_group.alti_rg.name
  dns_prefix          = "alti-${var.environment}"

  # Default System Node Pool
  default_node_pool {
    name           = "systempool"
    node_count     = 1
    vm_size        = "Standard_D4s_v5"
    vnet_subnet_id = azurerm_subnet.aks_subnet.id
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
  }
}

# 4. Swarm Specific Node Pool (Equivalent to GKE App Pool)
resource "azurerm_kubernetes_cluster_node_pool" "swarm_nodes" {
  name                  = "swarmnodes"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.primary.id
  vm_size               = "Standard_D8s_v5" # Equivalent to 8 vCPU
  node_count            = 2
  enable_auto_scaling   = true
  min_count             = 1
  max_count             = 10
  vnet_subnet_id        = azurerm_subnet.aks_subnet.id

  # node_taints = ["confidential-enclave=true:NoSchedule"] # Apply Azure Confidential VMs if required
}
