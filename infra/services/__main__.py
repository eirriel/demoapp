import pulumi
from svcs import ServicesResources, ServicesArgs

envName = pulumi.get_stack()
config = pulumi.Config()
vpc_stack = pulumi.StackReference('organization/vpc/vpc-demo')
k8s_stack = pulumi.StackReference('organization/eks/eks-demo')
BASE_TAGS = {
    'Environment': envName
}

svcs = ServicesResources(
    f"{envName}-svcs",
    ServicesArgs(
        base_tags=BASE_TAGS,
        ebs_csi_chart_version=config.require('eks_ebs_csi_chart_version'),
        kube_users=config.get_object('kube_users'),
        public_alb=k8s_stack.require_output('cluster_public_load_balancer'),
        private_subnets=vpc_stack.require_output('private_subnet_ids'),
        worker_role_arn=k8s_stack.require_output('cluster_worker_role'),
        vpc_id=vpc_stack.require_output('vpc_id')
    )
)


#pulumi.export("cluster-public-load-balancer", cluster.eks_alb.dns_name)
#pulumi.export("cluster-internal-load-balancer",
#              cluster.eks_private_alb.dns_name)
