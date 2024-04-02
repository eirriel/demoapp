"""
Contains a Pulumi ComponentResource for creating the infra resources for Databases.
"""
import json
from typing import Mapping, Sequence

import pulumi
import pulumi_aws as aws
import pulumi_random as random


class RdsDbArgs:
    """
    The arguments necessary to construct `RdsDB` resource.
    """

    def __init__(self,
                 base_tags: Mapping[str, str],
                 cidr_blocks: Sequence[pulumi.Input[str]],
                 major_version: pulumi.Input[str],
                 private_subnets: Sequence[pulumi.Input[str]],
                 vpc_id: pulumi.Input[str],
                 zone_name: pulumi.Input[str],
                 is_prod_database: pulumi.Input[bool] = False,
                 serverless_max_capacity: pulumi.Input[int] = 3,
                 storage_size: pulumi.Input[int] = 20):
        """
        Constructs a RdsDbArgs.

        :param base_tags: Tags which are applied to all taggable resources.
        :param cidr_blocks: ip range to grant access in security group
        :param is_prod_database: True is database needs redundancy and other best practices
        :param major_version: The engine major version
        :param private_subnets: the private subnets where the subnet group will be deployed
        :param serverless_max_capacity: The serverless upper scaling limit
        :param storage_size: database disk size in GB
        :param vpc_id: Vpc Id to create the security group
        :param zone_id: Route53 hosted zone id to create the CNAME records
        """

        self.base_tags = base_tags
        self.cidr_blocks = cidr_blocks
        self.is_prod_database = is_prod_database
        self.major_version = major_version
        self.private_subnets = private_subnets
        self.serverless_max_capacity = serverless_max_capacity
        self.storage_size = storage_size
        self.vpc_id = vpc_id
        self.zone_name = zone_name

class RdsDb(pulumi.ComponentResource):
    """
    Creates the infra resources for deploy RDS Database Resources
    """

    def __init__(self,
                 name: str,
                 args: RdsDbArgs,
                 opts: pulumi.ResourceOptions = None):
        """
        Constructs the infra resources for RDS Databases.

        :param name: The Pulumi resource name. Child resource names are constructed based on this.
        :param args: A RdsDbArgs object.
        :param opts: A pulumi.ResourceOptions object.
        """
        super().__init__('RdsDb', name, None, opts)

        # Make base info available to other methods
        self.name = name
        self.base_tags = args.base_tags
        self.cidr_blocks = args.cidr_blocks
        self.is_prod_database = args.is_prod_database
        self.major_version = args.major_version
        self.private_subnets = args.private_subnets
        self.storage_size = args.storage_size
        self.vpc_id = args.vpc_id
        self.zone_name = args.zone_name
        self.zone_id = aws.route53.get_zone(name=self.zone_name).zone_id

        # Major version - Minor version dictionary
        db_versions = {
            # '8.0': '8.0.36'
            '8.0': '3.06'
        }

        self.latest_cert = aws.rds.get_certificate(
            id="rds-ca-rsa2048-g1"
        )

        self.db_parameter_group = {}
        for v in db_versions.keys():
            self.db_parameter_group[v] = aws.rds.ParameterGroup(
                f"{self.name}-db-mysql-{v}",
                family=f"aurora-mysql{v}",
                name=f"mysql{v.replace('.', '')}",
                tags=self.base_tags,
                opts=pulumi.ResourceOptions(
                    parent=self
                )
            )
        
        self.db_subnet = aws.rds.SubnetGroup(
            f"{self.name}-db-subnet",
            description="Mysql db subnet",
            subnet_ids=self.private_subnets,
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_security_group = aws.ec2.SecurityGroup(
            f"{self.name}-db-security-group",
            description='main db access',
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    cidr_blocks=self.cidr_blocks,
                    protocol='tcp',
                    from_port=3306,
                    to_port=3306
                )
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"]
                )
            ],
            vpc_id=self.vpc_id,
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_password = random.RandomPassword(
            f"{self.name}-db-mysql-password",
            length=32,
            special=False,
            opts=pulumi.ResourceOptions(
                parent=self,
                additional_secret_outputs=['result']
            )
        )
        
        # Serverless DB
        self.serverless_db = aws.rds.Cluster(
            f"{self.name}-db-cluster",
            apply_immediately=True,
            # allocated_storage=self.storage_size,
            allow_major_version_upgrade=True,
            cluster_identifier_prefix=f"{self.name}-db-cluster",
            database_name='demoapp',
            db_subnet_group_name=self.db_subnet.name,
            engine="aurora-mysql",
            engine_mode="provisioned",
            # engine_version=db_versions[self.major_version],
            engine_version="8.0.mysql_aurora.3.06.0",
            final_snapshot_identifier=f"{self.name}-db-cluster" if self.is_prod_database else None,
            master_username='root',
            master_password=self.db_password.result,
            skip_final_snapshot=not self.is_prod_database,
            serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
                min_capacity=2,
                max_capacity=args.serverless_max_capacity
            ),
            vpc_security_group_ids=[self.db_security_group.id],
            storage_encrypted=True,
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_cluster_instance = aws.rds.ClusterInstance(
            f"{self.name}-db-instance",
            apply_immediately=True,
            ca_cert_identifier=self.latest_cert.id,
            cluster_identifier=self.serverless_db.id,
            instance_class='db.serverless',
            engine=self.serverless_db.engine,
            engine_version=self.serverless_db.engine_version,
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )


        # DB Proxy

        self.db_proxy_secret = aws.secretsmanager.Secret(
            f"{self.name}-db-proxy-secret",
            description="Secret for the RDS proxy",
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )
        
        self.db_proxy_secret_version = aws.secretsmanager.SecretVersion(
            f"{self.name}-db-proxy-secret",
            secret_id=self.db_proxy_secret.id,
            secret_string=self.db_password.result.apply(lambda p: json.dumps({
                "username": "root",
                "password": p
            })),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        db_proxy_role = aws.iam.Role(
            f"{self.name}-db-proxy-role",
            name=f"{self.name}-db-proxy-role",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Sid": "RoleAssume",
                    "Principal": {
                        "Service": "rds.amazonaws.com",
                    },
                }],
            }),
            inline_policies=[
                aws.iam.RoleInlinePolicyArgs(
                    name="SecretManagerAccess",
                    policy=self.db_proxy_secret.arn.apply(
                        lambda arn:
                        json.dumps(
                            {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Action": [
                                            "secretsmanager:GetRandomPassword",
                                            "secretsmanager:CreateSecret",
                                            "secretsmanager:ListSecrets",
                                            "secretsmanager:GetSecretValue"
                                        ],
                                        "Effect": "Allow",
                                        "Resource": [arn]
                                    },
                                    {
                                        "Action": [
                                            "kms:Decrypt"
                                        ],
                                        "Effect": "Allow",
                                        "Resource": "*"
                                    }
                                ]
                            }
                        )
                    )
                )
            ],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_proxy = aws.rds.Proxy(
            f"{self.name}-db-proxy",
            name=f"{self.name}-db-proxy",
            debug_logging=True,
            engine_family="MYSQL",
            idle_client_timeout=1800,
            require_tls=False,
            role_arn=db_proxy_role.arn,
            vpc_security_group_ids=[self.db_security_group.id],
            vpc_subnet_ids=self.private_subnets,
            auths=[aws.rds.ProxyAuthArgs(
                auth_scheme="SECRETS",
                description="db-creds",
                iam_auth="DISABLED",
                secret_arn=self.db_proxy_secret.arn,
            )],
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_proxy_default_target = aws.rds.ProxyDefaultTargetGroup(
            f"{self.name}-db-proxy-default-target-group",
            db_proxy_name=self.db_proxy.name,
            connection_pool_config=aws.rds.ProxyDefaultTargetGroupConnectionPoolConfigArgs(
                connection_borrow_timeout=120,
                max_connections_percent=100,
                max_idle_connections_percent=50,
                session_pinning_filters=["EXCLUDE_VARIABLE_SETS"],
            ),
	        opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_proxy_target = aws.rds.ProxyTarget(
            f"{self.name}-db-proxy-target-group",
            db_proxy_name=self.db_proxy.name,
            db_cluster_identifier=self.serverless_db.cluster_identifier,
            target_group_name=self.db_proxy_default_target.name,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_proxy_endpoint = aws.rds.ProxyEndpoint(
            f"{self.name}-db-proxy-endpoint",
            db_proxy_endpoint_name=f"{self.name}-db-proxy-endpoint",
            db_proxy_name=self.db_proxy.name,
            vpc_subnet_ids=self.private_subnets,
            vpc_security_group_ids=[self.db_security_group.id],
            target_role="READ_WRITE",
            opts=pulumi.ResourceOptions(
                parent=self
            ),
            tags=self.base_tags
        )

        self.db_record = aws.route53.Record(
            f"{self.name}-db-record",
            zone_id=self.zone_id,
            name="db",
            type="CNAME",
            ttl=300,
            records=[
                self.serverless_db.endpoint
            ],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.db_proxy_record = aws.route53.Record(
            f"{self.name}-db-proxy-record",
            zone_id=self.zone_id,
            name="db-proxy",
            type='CNAME',
            ttl=300,
            records=[
                self.db_proxy_endpoint.endpoint
            ],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        super().register_outputs({})
