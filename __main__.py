# Copyright 2016-2021, Pulumi Corporation.  All rights reserved.

import base64
import pulumi
import pulumi_azure_native as azure_native
import pulumi_tls as tls
from pulumi_kubernetes import Provider,yaml


config = pulumi.Config()


# Create new resource group
resource_group = azure_native.resources.ResourceGroup("resourceGroup",
    location="eastus",
    resource_group_name="pulumi")

# Generate an SSH key
ssh_key = tls.PrivateKey("ssh-key", algorithm="RSA", rsa_bits=4096)

# Create cluster
managed_cluster_name = config.get("managedClusterName")
if managed_cluster_name is None:
    managed_cluster_name = "azure-native-aksgm"

managed_cluster = azure_native.containerservice.ManagedCluster("managedCluster",
    resource_group_name=resource_group.name,
    agent_pool_profiles=[{
        "count": 2,
        "max_pods": 110,
        "mode": "System",
        "name": "agentpool",
        "node_labels": {},
        "os_disk_size_gb": 30,
        "os_type": "Linux",
        "type": "VirtualMachineScaleSets",
        "vm_size": "Standard_D2s_v3",
    }],
    enable_rbac=True,
    identity=azure_native.containerservice.ManagedClusterIdentityArgs(
        type="SystemAssigned",
    ),
    kubernetes_version="1.22.6",
    linux_profile={
        "admin_username": "testuser",
        "ssh": {
            "public_keys": [{
                "key_data": ssh_key.public_key_openssh,
            }],
        },
    },
    dns_prefix=resource_group.name,
    node_resource_group=f"MC_azure-native-go_{managed_cluster_name}_westus",
    )

kube_creds = pulumi.Output.all(resource_group.name, managed_cluster.name).apply(
    lambda args:
    azure_native.containerservice.list_managed_cluster_user_credentials(
        resource_group_name=args[0],
        resource_name=args[1]))

kube_config = kube_creds.kubeconfigs[0].value.apply(
    lambda enc: base64.b64decode(enc).decode())

custom_provider = Provider(
    "inflation_provider", kubeconfig=kube_config
)

pulumi.export("kubeconfig", kube_config)




registry = azure_native.containerregistry.Registry("registry",
    admin_user_enabled=True,
    registry_name=f"gmacr1891westus",
    location=resource_group.location,
    resource_group_name=resource_group.name,
    sku=azure_native.containerregistry.SkuArgs(
        name="Basic",
    ),
    tags={
        "pulumi": "true",
    })


#Remove the .status field from CRDs, needed for macbook M1
def remove_status(obj, opts):
    if obj["kind"] == "CustomResourceDefinition":
        del obj["status"]


keda = yaml.ConfigFile(
    "keda",
    'https://github.com/kedacore/keda/releases/download/v2.6.1/keda-2.6.1.yaml',
    transformations=[remove_status],
    opts=pulumi.ResourceOptions(depends_on=[managed_cluster],provider=custom_provider),
)

GITURL="https://github.com/gabrielmccoll/AzureDevopsContainerAgent.git#:ado_image"

task = azure_native.containerregistry.Task("task",
    is_system_task=False,
    platform=azure_native.containerregistry.PlatformPropertiesArgs(
        os="Linux",
    ),
    step=azure_native.containerregistry.DockerBuildStepArgs(
        context_path=GITURL,
        docker_file_path="Dockerfile",
        image_names=["gmtest/adoagent:{{.Run.ID}}"],
        is_push_enabled=True,
        no_cache=False,
        type="Docker",
    ),
    registry_name=registry.name,
    resource_group_name=resource_group.name,
    status="Enabled",

    tags={
        "testkey": "test",
    },
    task_name="GMTask",
    # trigger=azure_native.containerregistry.TriggerPropertiesArgs(
    #     source_triggers=[azure_native.containerregistry.SourceTriggerArgs(
    #         name="mySourceTrigger",
    #         source_repository=azure_native.containerregistry.SourcePropertiesArgs(
    #             branch="main",
    #             repository_url="https://github.com/gabrielmccoll/AzureDevopsContainerAgent",
    #             source_control_type="Github",
    #         ),
    #         source_trigger_events=["commit"],
    #     )],
    # )
)

task_run = azure_native.containerregistry.TaskRun("taskRunbuild",
    force_update_tag="test1",
    location=resource_group.location,
    registry_name=registry.name,
    resource_group_name=resource_group.name,
    run_request=azure_native.containerregistry.TaskRunRequestArgs(
        task_id=task.id,
        type="FileTaskRunRequest"
    ),
    task_run_name="myRunbuildtask",   
)


# # Export the private cluster IP address of the frontend.
# frontend = keda.get_resource('v1/Service', 'frontend')
# pulumi.export('private_ip', frontend.spec['cluster_ip'])

# pulumi.export('namespace_name', namespace.metadata.apply(lambda m: m.name))
# pulumi.export('deployment_name', deployment.metadata.apply(lambda m: m.name))
# pulumi.export('service_name', service.metadata.apply(lambda m: m.name))
# pulumi.export('service_public_endpoint', service.status.apply(lambda status: status.load_balancer.ingress[0].ip))