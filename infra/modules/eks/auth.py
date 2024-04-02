""" Pulumi resources for Kubernetes authorization."""
import pulumi
import pulumi_kubernetes as k
import yaml
from typing import Optional, Sequence


class KAuthArgs:
    def __init__(self,
                 admin_users: Sequence[str],
                 worker_role_arn: pulumi.Input[str]) -> None:
        """
        Arguments for KAuth object

        :param admin_users: Array of IAM users arns to declare as cluster admins
        :param worker_role_arn: The instance role for the worker nodes
        """
        self.admin_users = admin_users
        self.worker_role_arn = worker_role_arn

class KAuth(pulumi.ComponentResource):
    def __init__(self,
                 name: str,
                 args: KAuthArgs,
                 opts: Optional[pulumi.ResourceOptions] = None) -> None:
        """
        Creates the required resources for authenticate users and instance
        with EKS API

        :param name: The Pulumi resource name. Child resource names are contructed based on this.
        :param args: A KAuthArgs object containing the class arguments
        :param opts: A pulumi.ResourceOptions object.
        """
        super().__init__('Kauth', name, None, opts)

        self.name = name
        # Create admin users dictionary
        self.admin_users = [
            {
                'userarn': u,
                'username': u.split('/')[-1],
                'groups': [
                    'system:masters'
                ]
            } for u in args.admin_users
        ]

        # Create required configmap
        # (https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html)
        self.cm_auth = k.core.v1.ConfigMap(
            f"{self.name}-auth-cm",
            metadata=k.meta.v1.ObjectMetaArgs(
                name='aws-auth',
                namespace='kube-system'
            ),
            data={
                "mapRoles": args.worker_role_arn.apply(lambda r: yaml.dump(self.get_node_role(r))),
                "mapUsers": yaml.dump(self.admin_users)
            },
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

    @staticmethod
    def get_node_role(r):
        node_role = [
            {
                'rolearn': r,
                'username': 'system:node:{{EC2PrivateDNSName}}',
                'groups': [
                    'system:bootstrappers',
                    'system:nodes'
                ]
            }
        ]
        return node_role

