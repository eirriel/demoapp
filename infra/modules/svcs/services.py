"""
Contains a Pulumi ComponentResource for creating the infra resources
for Kubernetes Resources.
"""
from typing import Mapping, Sequence, Any

import json
import yaml
import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s


class ServicesArgs:
    """
    The arguments necessary to construct `KubeServices` resource.
    """

    def __init__(self,
                 base_tags: Mapping[str, str],
                 ebs_csi_chart_version: pulumi.Input[str], 
                 kube_users: Sequence[str],
                 public_alb: pulumi.Input[str],
                 vpc_id: pulumi.Input[str],
                 worker_role_arn: pulumi.Input[str],
                 traefik_chart_version: pulumi.Input[str] = "v23.2.0"):
        """
        Constructs a KubeServicesArgs.

        :param base_tags: Tags which are applied to all taggable resources.
        """
        self.base_tags = base_tags
        self.ebs_csi_chart_version = ebs_csi_chart_version
        self.kube_users = kube_users
        self.public_alb = public_alb
        self.traefik_chart_version = traefik_chart_version
        self.vpc_id = vpc_id
        self.worker_role_arn = worker_role_arn


class ServicesResources(pulumi.ComponentResource):
    """
    Creates the infra resources for deploy Kubernetes Resources
    """

    def __init__(self,
                 name: str,
                 args: ServicesArgs,
                 opts: pulumi.ResourceOptions = None):
        """
        Constructs the infra resources for Kubernetes Services resources.

        :param name: The Pulumi resource name. Child resource names
        are constructed based on this.
        :param args: An KubeServicesArgs object.
        :param opts: A pulumi.ResourceOptions object.
        """
        super().__init__('ServicesResources', name, None, opts)

        # Make base info available to other methods
        self.name = name
        self.account_id = aws.get_caller_identity().account_id
        self.base_tags = args.base_tags
        self.ebs_csi_chart_version = args.ebs_csi_chart_version
        self.kube_users = args.kube_users
        self.public_alb = args.public_alb
        self.traefik_chart_version = args.traefik_chart_version
        self.vpc_id = args.vpc_id
        self.worker_role_arn = args.worker_role_arn

        # Auth

        node_cluster_map_users = [
            {
                'userarn': user,
                'username': user.split('/')[-1],
                'groups': [
                    'system:masters'
                ]
            } for user in self.kube_users
        ]

        self.cluster_auth = k8s.core.v1.ConfigMap(
            f"{self.name}-kauth",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="aws-auth",
                namespace="kube-system"
            ),
            data={
                "mapRoles": self.worker_role_arn.apply(lambda r: self.get_node_roles(r)),
                "mapUsers": yaml.dump(node_cluster_map_users)
            },
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Deploy Metric Server from the URL
        metric_server = k8s.yaml.ConfigFile(
            f"{self.name}-metric-server",
            file="metric_server.yaml",
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )
        
        # EBS CSI Driver

        self.ebs_csi = k8s.helm.v3.Release(
            f"{self.name}-ebs-csi",
            k8s.helm.v3.ReleaseArgs(
                chart="aws-ebs-csi-driver",
                namespace='kube-system',
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://kubernetes-sigs.github.io/aws-ebs-csi-driver"
                ),
                version=self.ebs_csi_chart_version,
                values={}
            ),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Traefik

        self.traefik_ns = k8s.core.v1.Namespace(
            f"{self.name}-traefik-ns",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name='traefik'
            ),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.traefik = k8s.helm.v3.Release(
            f"{self.name}-traefik",
            k8s.helm.v3.ReleaseArgs(
                chart="traefik",
                namespace=self.traefik_ns.metadata.name,
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://traefik.github.io/charts/",
                ),
                version=self.traefik_chart_version,
                values={
                    "ingressClass": {
                        "enabled": True,
                        "isDefaultClass": False},
                    "ingressRoute": {
                        "dashboard": {
                            "enabled": False,
                        }
                    },
                    "ports": {
                        "traefik": {
                            "expose": True,
                            "exposedPort": 9000,
                            "nodePort": 30900
                        },
                        "web": {
                            "expose": True,
                            "nodePort": 32080
                        }
                    },
                    "service": {
                        "type": "NodePort",
                    }
                }),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # ECR Repo

        self.ecr_repo = aws.ecr.Repository(
            f"{self.name}-ecr-repository",
            name="demoapp",
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        aws.ecr.LifecyclePolicy(
            f"{self.name}-lifecycle-policy",
            repository=self.ecr_repo.name,
            policy=json.dumps({
                "rules": [
                    {
                        "rulePriority": 1,
                        "description": "Expire images count more than 30",
                        "selection": {
                            "tagStatus": "any",
                            "countType": "imageCountMoreThan",
                            "countNumber": 30
                        },
                        "action": {
                            "type": "expire"
                        }
                    }
                ]
            }),
            opts=pulumi.ResourceOptions(
                parent=self.ecr_repo
            )
        )


        super().register_outputs({})


    def create_records(self, h):
        if h.get('create_records', True):
            nice_name = h.get('name').split('.')[0]
            zone_name = 'cloudlan.net'
            hz = aws.route53.get_zone(name=zone_name)
            aws.route53.Record(
                f"{self.name}-{nice_name}-record",
                name=h['name'].replace(f".{zone_name}", ""),
                records=[self.public_alb],
                ttl=300,
                type='CNAME',
                zone_id=hz.zone_id,
                opts=pulumi.ResourceOptions(
                    parent=self
                )
            )
            
    @staticmethod
    def get_node_roles(worker_role):
        node_cluster_map_roles = [
            {
                'rolearn': worker_role,
                'username': 'system:node:{{EC2PrivateDNSName}}',
                'groups': [
                    'system:bootstrappers',
                    'system:nodes'
                ]
            },
            {
                'rolearn': 'arn:aws:iam::389169665533:role/ci-role',
                'username': 'ci-user',
                'groups': [
                    'system:masters'
                ]
            }
        ]
        return yaml.dump(node_cluster_map_roles)

