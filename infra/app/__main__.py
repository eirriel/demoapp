import pulumi
import pulumi_kubernetes as k
from app import KubernetesService,KubernetesServiceArgs

envName = pulumi.get_stack()
config = pulumi.Config()
# vpc_stack = pulumi.StackReference('organization/vpc/vpc-demo')
k8s_stack = pulumi.StackReference('organization/eks/eks-demo')
db_stack = pulumi.StackReference('organization/db/db-demo')
BASE_TAGS = {
    'Environment': envName
}

ns = k.core.v1.Namespace(
    f"{envName}-ns",
    metadata=k.meta.v1.ObjectMetaArgs(
        name='demoapp'
    )
)

default_secrets={
    'DB_USERNAME': db_stack.require_output('db_admin_username'),
    'DB_PASSWORD': db_stack.require_output('db_admin_password')
   # 'DB_USERNAME': db_stack.require_output('db_proxy_username'),
   # 'DB_PASSWORD': db_stack.require_output('db_proxy_password')
}

app = KubernetesService(
    f"{envName}-app",
    KubernetesServiceArgs(
        base_tags=BASE_TAGS,
        app_name='demoapp',
        container_ports=[3000],
        environment_variables=config.get_object('app_environment_variables'),
        hostname_list=config.get_object('app_hostnames'),
        image=config.require('app_image'),
        ingress_port=3000,
        kube_issuer=k8s_stack.require_output('cluster_issuer'),
        max_replicas=config.get_int('app_max_replicas'),
        min_replicas=config.get_int('app_min_replicas'),
        namespace=ns.metadata.name,
        openid_connector=k8s_stack.require_output('cluster_openid_connector'),
        public_load_balancer=k8s_stack.require_output('cluster_public_load_balancer'),
        secrets_data={
            **default_secrets,
            **config.get_object('app_secrets')
        },
        service_permissions=[]
    )
)

