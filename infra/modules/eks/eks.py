
from typing import Mapping, Sequence
import json
import base64
import pulumi
import pulumi_aws as aws
import pulumi_tls as tls


# EKS Cluster
class EksArgs:
    """
    The arguments necessary to construct a `EKS` resource.
    """

    def __init__(self,
                 base_tags: Mapping[str, str],
                 default_certificate_arn: pulumi.Input[str],
                 eks_version: pulumi.Input[str],
                 private_subnet_ids: pulumi.Input[Sequence[pulumi.Input[str]]],
                 public_subnet_ids: pulumi.Input[Sequence[pulumi.Input[str]]],
                 vpc_id: pulumi.Input[str],
                 worker_image_id: pulumi.Input[str],
                 worker_key_name: pulumi.Input[str],
                 private_endpoint: pulumi.Input[bool] = False,
                 public_endpoint: pulumi.Input[bool] = False,
                 worker_instance_type: pulumi.Input[str] = 't2.medium',
                 worker_max_size: pulumi.Input[int] = 10,
                 worker_min_size: pulumi.Input[int] = 2
                 ):
        """
        Constructs an EksArgs.

        :param base_tags: Tags which are applied to all taggable resources.
        :param default_certificate_arn: Arn of the certificate used by the load balancer.
        :param eks_version: EKS version of the cluster
        :param private_subnet_ids: the private subnets for the nodes to be deployed
        :param private_subnet_ids: the public subnets for the Load Balancer to be deployed
        :param vpc_id: The VPC id for this deployment
        :param worker_image_id: AMI image for the nodes
        :param worker_instance_type: EC2 instance type for the nodes
        :param worker_key_name: Key pair for the nodes
        :param worker_max_size: Worker Autoscaling maximum size
        :param worker_max_size: Worker Autoscaling minimum size
        """

        self.base_tags = base_tags
        self.default_certificate_arn = default_certificate_arn
        self.eks_version = eks_version
        self.private_endpoint = private_endpoint
        self.private_subnet_ids = private_subnet_ids
        self.public_subnet_ids = public_subnet_ids
        self.public_endpoint = public_endpoint
        self.vpc_id = vpc_id
        self.worker_image_id = worker_image_id
        self.worker_instance_type = worker_instance_type
        self.worker_key_name = worker_key_name
        self.worker_max_size = worker_max_size
        self.worker_min_size = worker_min_size


class EKS(pulumi.ComponentResource):
    """
    Creates the infra resources for deploy an EKS cluster
    """

    def __init__(self,
                 name: str,
                 args: EksArgs,
                 opts: pulumi.ResourceOptions = None):
        """
        Constructs the infra resources for an EKS cluster deployment.

        :param name: The Pulumi resource name. Child resource names are constructed based on this.
        :param args: A EKSArgs object.
        :param opts: A pulumi.ResourceOptions object.
        """
        super().__init__('EKS', name, None, opts)

        # Make base info available to other methods
        self.name = name
        self.base_tags = args.base_tags
        self.default_certificate_arn = args.default_certificate_arn
        self.eks_version = args.eks_version
        self.private_endpoint = args.private_endpoint
        self.private_subnet_ids = args.private_subnet_ids
        self.public_endpoint = args.public_endpoint
        self.public_subnet_ids = args.public_subnet_ids
        self.worker_image_id = args.worker_image_id
        self.worker_instance_type = args.worker_instance_type
        self.worker_key_name = args.worker_key_name
        self.worker_max_size = args.worker_max_size
        self.worker_min_size = args.worker_min_size
        self.vpc_id = args.vpc_id

        # IAM #

        eks_role = aws.iam.Role(
            'eks-iam-role',
            assume_role_policy=json.dumps({
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'sts:AssumeRole',
                        'Principal': {
                            'Service': 'eks.amazonaws.com'
                        },
                        'Effect': 'Allow',
                        'Sid': ''
                    }
                ],
            }),
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            'eks-service-policy-attachment',
            role=eks_role.id,
            policy_arn='arn:aws:iam::aws:policy/AmazonEKSServicePolicy',
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            'eks-cluster-policy-attachment',
            role=eks_role.id,
            policy_arn='arn:aws:iam::aws:policy/AmazonEKSClusterPolicy',
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Ec2 NodeGroup Role

        self.ec2_role = aws.iam.Role(
            'ec2-nodegroup-iam-role',
            assume_role_policy=json.dumps({
                'Version': '2012-10-17',
                'Statement': [
                    {
                        'Action': 'sts:AssumeRole',
                        'Principal': {
                            'Service': 'ec2.amazonaws.com'
                        },
                        'Effect': 'Allow',
                        'Sid': ''
                    }
                ],
            }),
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            'eks-workernode-policy-attachment',
            role=self.ec2_role.id,
            policy_arn='arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy',
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            'eks-cni-policy-attachment',
            role=self.ec2_role.id,
            policy_arn='arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy',
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            'ec2-container-ro-policy-attachment',
            role=self.ec2_role.id,
            policy_arn='arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly',
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            'ec2-ebs-csi-policy-attachment',
            role=self.ec2_role.id,
            policy_arn='arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy',
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            'ssm-session-policy-attachment',
            role=self.ec2_role.id,
            policy_arn='arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore',
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Security Groups #

        self.eks_security_group = aws.ec2.SecurityGroup(
            'eks-cluster-sg',
            vpc_id=self.vpc_id,
            description='Allow all HTTP(s) traffic to EKS Cluster',
            tags={
                'Name': 'eks-cluster-sg',
                **self.base_tags
            },
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    cidr_blocks=['0.0.0.0/0'],
                    from_port=443,
                    to_port=443,
                    protocol='tcp',
                    description='Allow pods to communicate with the cluster API Server.'
                ),
                aws.ec2.SecurityGroupIngressArgs(
                    cidr_blocks=['0.0.0.0/0'],
                    from_port=80,
                    to_port=80,
                    protocol='tcp',
                    description='Allow internet access to pods'
                )
            ],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # EKS Cluster #
        cluster_name = f'{self.name}-eks-cluster'
        self.eks_cluster = aws.eks.Cluster(
            'eks-cluster',
            enabled_cluster_log_types=[
                'api',
                'audit',
                'authenticator',
                'controllerManager',
                'scheduler'
            ],
            name=cluster_name,
            role_arn=eks_role.arn,
            tags={
                'Name': cluster_name,
                **self.base_tags
            },
            vpc_config=aws.eks.ClusterVpcConfigArgs(
                public_access_cidrs=['0.0.0.0/0'],
                endpoint_private_access=True if self.private_endpoint else False,
                endpoint_public_access=True if self.public_endpoint else False,
                security_group_ids=[self.eks_security_group.id],
                subnet_ids=self.private_subnet_ids,
            ),
            version=self.eks_version,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        cluster_certificate = self.eks_cluster.identities.apply(
            lambda identities: tls.get_certificate(
                url=identities[0].oidcs[0].issuer
            )
        )
        
        self.openid_connector = aws.iam.OpenIdConnectProvider(
            f'{self.name}-oidc-provider',
            client_id_lists=['sts.amazonaws.com'],
            thumbprint_lists=[
                cluster_certificate.certificates[0].sha1_fingerprint
            ],
            url=self.eks_cluster.identities[0].oidcs[0].issuer,
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self.eks_cluster
            )
        )

        #self.eks_log_group = aws.cloudwatch.LogGroup(
        #    f"{self.name}-eks-logs",
        #    name=self.eks_cluster.name.apply(lambda c: f"eks/{c}/logs"),
        #    retention_in_days=7,
        #    opts=pulumi.ResourceOptions(
        #        parent=self
        #    )
        #)

        # Load Balancer
        eks_load_balancer_sec_grp = aws.ec2.SecurityGroup(
            f'{self.name}-alb-sec-grp',
            vpc_id=self.vpc_id,
            description='Security group for EKS Cluster nodes',
            tags={
                'Name': 'eks-alb-sg',
            },
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    cidr_blocks=['0.0.0.0/0'],
                    from_port=80,
                    to_port=80,
                    protocol='tcp',
                    description='HTTP access for ALB'
                ),
                aws.ec2.SecurityGroupIngressArgs(
                    cidr_blocks=['0.0.0.0/0'],
                    from_port=443,
                    to_port=443,
                    protocol='tcp',
                    description='HTTPS access for ALB'
                )
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    cidr_blocks=['0.0.0.0/0'],
                    from_port=0,
                    to_port=0,
                    protocol="-1"
                )
            ],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.eks_alb = aws.lb.LoadBalancer(
            f'{self.name}-eks-lb',
            load_balancer_type='application',
            security_groups=[eks_load_balancer_sec_grp.id],
            subnets=self.public_subnet_ids,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        eks_alb_tg = aws.lb.TargetGroup(
            f'{self.name}-eks-lb-tg',
            health_check=aws.lb.TargetGroupHealthCheckArgs(
                path='/ping',
                port="30900",
                interval=30
            ),
            port=32080,
            protocol="HTTP",
            vpc_id=self.vpc_id,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        eks_alb_http_listener = aws.lb.Listener(
            f'{self.name}-eks-lb-http-listener',
            load_balancer_arn=self.eks_alb.arn,
            port=80,
            protocol='HTTP',
            default_actions=[
                aws.lb.ListenerDefaultActionArgs(
                    type="redirect",
                    redirect=aws.lb.ListenerDefaultActionRedirectArgs(
                        port="443",
                        protocol="HTTPS",
                        status_code="HTTP_301",
                    )
                )
            ],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.elk_alb_https_listener = aws.lb.Listener(
            f'{self.name}-eks-lb-https-listener',
            load_balancer_arn=self.eks_alb.arn,
            port=443,
            protocol='HTTPS',
            ssl_policy="ELBSecurityPolicy-2016-08",
            certificate_arn=self.default_certificate_arn,
            default_actions=[aws.lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=eks_alb_tg.arn,
            )],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )
        # Using EC2 Autoscaling #

        eks_node_sec_grp = aws.ec2.SecurityGroup(
            f'{self.name}-node-sec-grp',
            vpc_id=self.vpc_id,
            description='Security group for EKS Cluster nodes',
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"]
                )
            ],
            tags={
                'Name': 'eks-cluster-node-sg',
                **self.base_tags,
            },
            opts=pulumi.ResourceOptions(
                parent=self
            ))

        aws.ec2.SecurityGroupRule(
            f'{self.name}-node-sec-grp-self',
            type="ingress",
            from_port=0,
            to_port=0,
            protocol='-1',
            description='Allow node to communicate with each other',
            security_group_id=eks_node_sec_grp.id,
            source_security_group_id=eks_node_sec_grp.id,
            opts=pulumi.ResourceOptions(
                parent=eks_node_sec_grp
            )
        )
                    
        aws.ec2.SecurityGroupRule(
            f'{self.name}-node-sec-grp-cluster',
            type="ingress",
            from_port=0,
            to_port=0,
            protocol='-1',
            security_group_id=eks_node_sec_grp.id,
            source_security_group_id=self.eks_security_group.id,
            description='Allow worker Kubelets and pods to receive communication from the cluster control plane',
            opts=pulumi.ResourceOptions(
                parent=eks_node_sec_grp
            )
        )

        aws.ec2.SecurityGroupRule(
            f'{self.name}-node-sec-grp-ssh',
            type="ingress",
            from_port=22,
            to_port=22,
            protocol='tcp',
            security_group_id=eks_node_sec_grp.id,
            cidr_blocks=['10.0.0.0/8'],
            description='Allow ssh from vpc',
            opts=pulumi.ResourceOptions(
                parent=eks_node_sec_grp
            )
        )

        aws.ec2.SecurityGroupRule(
            f'{self.name}-node-sec-grp-app',
            type="ingress",
            from_port=30000,
            to_port=32800,
            protocol='tcp',
            security_group_id=eks_node_sec_grp.id,
            cidr_blocks=['10.0.0.0/8'],
            description='Allow app access from vpc',
            opts=pulumi.ResourceOptions(
                parent=eks_node_sec_grp
            )
        )

        eks_node_instance_profile = aws.iam.InstanceProfile(
            f'{self.name}-node-instance-profile',
            role=self.ec2_role.name,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        eks_node_launch_template = aws.ec2.LaunchTemplate(
            f'{self.name}-node-launch-template',
            iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
                arn=eks_node_instance_profile.arn
            ),
            image_id=self.worker_image_id,
            instance_type=self.worker_instance_type,
            key_name=self.worker_key_name,
            name_prefix=cluster_name,
            network_interfaces=[
                aws.ec2.LaunchTemplateNetworkInterfaceArgs(
                    associate_public_ip_address=False,
                    security_groups=[
                        eks_node_sec_grp.id
                    ]
                )
            ],
            block_device_mappings=[
                aws.ec2.LaunchTemplateBlockDeviceMappingArgs(
                    device_name="/dev/xvda",
                    ebs=aws.ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
                        delete_on_termination=True,
                        iops=0,
                        volume_size=50,
                        volume_type="gp2"
                    )
                )
            ],
            user_data=pulumi.Output.all(
                self.eks_cluster.endpoint,
                self.eks_cluster.certificate_authority.data,
                cluster_name
            ).apply(lambda args: base64.b64encode(f"""
            #!/bin/bash
            set -o xtrace
            /etc/eks/bootstrap.sh --apiserver-endpoint '{args[0]}' --kubelet-extra-args --node-labels=node.kubernetes.io/lifecycle=`curl -s http://169.254.169.254/latest/meta-data/instance-life-cycle` --b64-cluster-ca '{args[1]}' '{args[2]}' 
            """.encode()).decode()),
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        eks_node_autoscaling = aws.autoscaling.Group(
            f'{self.name}-node-asg',
            # desired_capacity=args.desired_capacity,
            instance_refresh=aws.autoscaling.GroupInstanceRefreshArgs(
                strategy="Rolling"
            ),
            launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
                id=eks_node_launch_template.id,
                version="$Latest"
            ),
            max_size=self.worker_max_size,
            min_size=self.worker_min_size,
            name=f"{cluster_name}-worker-node-asg",
            vpc_zone_identifiers=self.private_subnet_ids,
            tags=[
                aws.autoscaling.GroupTagArgs(
                    key="Name",
                    value=f"{cluster_name}-worker-node",
                    propagate_at_launch=True
                ),
                aws.autoscaling.GroupTagArgs(
                    key=f"kubernetes.io/cluster/{cluster_name}",
                    value="owned",
                    propagate_at_launch=True
                ),
                aws.autoscaling.GroupTagArgs(
                    key=f"k8s.io/cluster-autoscaler/{cluster_name}",
                    value="owned",
                    propagate_at_launch=True
                ),
                aws.autoscaling.GroupTagArgs(
                    key="k8s.io/cluster-autoscaler/enabled",
                    value="true",
                    propagate_at_launch=True
                ),
            ] + [
                aws.autoscaling.GroupTagArgs(
                    key=k,
                    value=self.base_tags[k],
                    propagate_at_launch=True
                ) for k in self.base_tags.keys()
            ],
            target_group_arns=[eks_alb_tg.arn],
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Autoscaler #
        eks_autoscaler_policy = aws.iam.Policy(
            f'{self.name}-eks-autoscaler-policy',
            policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": [
                            "autoscaling:DescribeAutoScalingGroups",
                            "autoscaling:DescribeAutoScalingInstances",
                            "autoscaling:DescribeLaunchConfigurations",
                            "autoscaling:DescribeTags",
                            "autoscaling:SetDesiredCapacity",
                            "autoscaling:TerminateInstanceInAutoScalingGroup",
                            "ec2:DescribeLaunchTemplateVersions"
                        ],
                        "Resource": "*",
                        "Effect": "Allow"
                    }
                ]
            }),
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        eks_autoscaler_role = aws.iam.Role(
            f'{self.name}-eks-autoscaler-role',
            assume_role_policy=self.openid_connector.arn.apply(lambda o: aws.iam.get_policy_document(
                statements=[
                    aws.iam.GetPolicyDocumentStatementArgs(
                        effect="Allow",
                        principals=[
                            aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                                type='Federated',
                                identifiers=[o]
                            )
                        ],
                        actions=["sts:AssumeRoleWithWebIdentity"],
                        conditions=[
                            aws.iam.GetPolicyDocumentStatementConditionArgs(
                                test='StringEquals',
                                variable=f"{o.split('/',1)[1]}:sub",
                                values=["system:serviceaccount:kube-system:cluster-autoscaler"]
                            )
                        ]
                    )
                ]
            ).json),
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.iam.RolePolicyAttachment(
            f'{self.name}-eks-autoscaler-attach',
            role=eks_autoscaler_role.name,
            policy_arn=eks_autoscaler_policy.arn,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )
        
        self.eks_sc_policy = aws.autoscaling.Policy(
            f"{self.name}-asg-policy",
            scaling_adjustment=2,
            adjustment_type="ChangeInCapacity",
            cooldown=300,
            autoscaling_group_name=eks_node_autoscaling.name,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.cpu_alarm = aws.cloudwatch.MetricAlarm(
            f"{self.name}-eks-cpu-alarm",
            comparison_operator="GreaterThanOrEqualToThreshold",
            evaluation_periods=2,
            metric_name="CPUUtilization",
            namespace="AWS/EC2",
            period=300,
            statistic="Average",
            threshold=60,
            alarm_actions=[self.eks_sc_policy.arn],
            dimensions={"AutoScalingGroupName": eks_node_autoscaling.name},
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        super().register_outputs({})
