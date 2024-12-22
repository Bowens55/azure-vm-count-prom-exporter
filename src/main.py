from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from dotenv import load_dotenv
from prometheus_client.core import GaugeMetricFamily, CollectorRegistry
from prometheus_client import start_http_server
import os
import time
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set logging level for Azure packages to WARNING
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("msal").setLevel(logging.WARNING)

subscription_id = os.environ.get("subscription_id")
resource_group_name = os.environ.get("resource_group")
tenant_id = os.environ.get("tenant_id")
client_id = os.environ.get("client_id")
client_secret = os.environ.get("client_secret")
if os.getenv("port"):
    port = int(os.getenv("port"))
else:
    port = 8005

logger.info(f"Starting container using this information: SUB={subscription_id} and RG={resource_group_name}") 


if not all([subscription_id, resource_group_name, tenant_id, client_id, client_secret]):
    logger.error("One or more environment variables are missing.")
    exit(1)


credential = ClientSecretCredential(
    tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
)


def get_power_state(compute_client, vm_name, resource_group_name):
    logger.info("Attempting to gather power state for " + vm_name)
    vm_state = compute_client.virtual_machines.instance_view(resource_group_name, vm_name)
    power_state = vm_state.statuses[1].display_status
    return power_state


class vm_collector(object):
    """Collector for Azure VMs in a given RG."""

    def __init__(self):
        pass

    def collect(self):
        # Setting up prometheus gauge
        gauge = GaugeMetricFamily(
            "az_vm_info",
            "Node information for node counts etc.",
            labels=["vm_name", "vm_sku", "vm_location", "vm_power_state"],
        )

        # Create a Compute Management client
        logger.info("Pulling VM metrics from Azure")
        compute_client = ComputeManagementClient(credential, subscription_id)
        vm_list = list(compute_client.virtual_machines.list(resource_group_name))

        if not vm_list:
            logger.warning(
                "No VMs found in the resource group. Did you specify the correct resource group?"
            )

        logger.info("Refreshing VM metrics")
        logger.info(f"Found {len(vm_list)} VMs in the resource group this time around.")
        for vm in vm_list:
            vm_name = vm.name
            vm_sku = vm.hardware_profile.vm_size
            vm_location = vm.location
            vm_power_state = get_power_state(compute_client, vm_name, resource_group_name)

            metric_labels = [vm_name, vm_sku, vm_location, vm_power_state]

            unix_timestamp = int(time.time())
            gauge.add_metric(metric_labels, unix_timestamp)
        yield gauge


if __name__ == "__main__":
    try:
        vm_registry = CollectorRegistry()
        vm_registry.register(vm_collector())
        logger.info(f"Starting HTTP server on port {port}")
        start_http_server(port, registry=vm_registry)
        logger.info(f"HTTP server started on port {port}")
        # Keep the program running to maintain http servers
        while True:
            time.sleep(600)
    except Exception as e:
        logger.error(f"Failed to start the HTTP server with error: {e}")
        exit(1)
