import pulumi
from db import RdsDb,RdsDbArgs

envName = pulumi.get_stack()
config = pulumi.Config()
vpc_stack = pulumi.StackReference('organization/vpc/vpc-demo')
k8s_stack = pulumi.StackReference('organization/eks/eks-demo')
BASE_TAGS = {
    'Environment': envName
}

db = RdsDb(
    f"{envName}-db",
    RdsDbArgs(
        base_tags=BASE_TAGS,
        cidr_blocks=config.get_object('cidr_blocks'),
        major_version=config.require('db_major_version'),
        private_subnets=vpc_stack.require_output('private_subnet_ids'),
        storage_size=config.get('db_storage_size'),
        vpc_id=vpc_stack.require_output('vpc_id'),
        zone_name='cloudlan.net'
    )
)

pulumi.export('db_admin_username', db.serverless_db.master_username)
pulumi.export('db_admin_password', db.db_password.result)

