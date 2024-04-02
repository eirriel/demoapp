import pulumi
from certs import Certs, CertArgs
from eks import EKS,EksArgs

envName = pulumi.get_stack()
config = pulumi.Config()
vpc_stack = pulumi.StackReference('organization/vpc/vpc-demo')
BASE_TAGS = {
    'Environment': envName
}

certificate = Certs(
    f"{envName}-certs",
    CertArgs(
        alt_names=[],
        base_tags=BASE_TAGS,
        domain_name=config.require('cert_domain_name'),
    )
)

eks_images = config.require_object('eks_images')
cluster = EKS(
    f"{envName}-k",
    EksArgs(
        base_tags=BASE_TAGS,
        default_certificate_arn=certificate.cert.arn,
        eks_version=config.require('eks_version'),
        #on_demand_base_capacity=config.get('eks_on_demand_base_capacity'),
        #on_demand_percentage_above_base_capacity=config.get(
        #    'eks_on_demand_percentage_above_base_capacity'),
        private_subnet_ids=vpc_stack.require_output('private_subnet_ids').apply(lambda ps: ps),
        public_endpoint=True,
        public_subnet_ids=vpc_stack.require_output('public_subnet_ids').apply(lambda ps: ps),
        vpc_id=vpc_stack.require_output('vpc_id').apply(lambda v: v),
        worker_image_id=eks_images.get(config.get('eks_version', '1.27')),
        worker_instance_type=config.require('eks_worker_instance_type'),
        worker_key_name=config.require('eks_key_pair'),
        worker_max_size=config.get('eks_worker_max_size'),
        worker_min_size=config.get('eks_worker_min_size'),
    )
)

pulumi.export("cluster_public_load_balancer", cluster.eks_alb.dns_name)
pulumi.export("cluster_name", cluster.name)
pulumi.export("cluster_worker_role", cluster.ec2_role.arn)
pulumi.export("cluster_issuer", cluster.eks_cluster.identities[0].oidcs[0].issuer)
pulumi.export("cluster_openid_connector", cluster.openid_connector.arn)
