from typing import Any, Mapping, Optional, Sequence
import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s

class KubernetesServiceArgs:
    def __init__(self,
                 base_tags: Mapping[str,str],
                 app_name: str,
                 container_ports: Sequence[int],
                 environment_variables: Mapping[Any, Any],
                 image: pulumi.Input[str],
                 kube_issuer: pulumi.Input[str],
                 namespace: pulumi.Input[str],
                 openid_connector: str,
                 public_load_balancer: pulumi.Input[str],
                 secrets_data: Mapping[Any, Any],
                 service_permissions: Sequence[aws.iam.GetPolicyDocumentStatementArgs],
                 replicas: pulumi.Input[int],
                 hostname_list: Sequence[Any],
                 ingress_port: int = 80) -> None:

        self.base_tags = base_tags
        self.app_name = app_name
        self.container_ports = container_ports
        self.environment_variables = environment_variables
        self.image = image
        self.kube_issuer = kube_issuer
        self.namespace = namespace
        self.openid_connector = openid_connector
        self.public_load_balancer = public_load_balancer
        self.secrets_data = secrets_data
        self.service_permissions = service_permissions
        self.hostname_list = hostname_list
        self.ingress_port = ingress_port
        self.replicas = replicas


class KubernetesService(pulumi.ComponentResource):
    def __init__(self,
                 name: str,
                 args: KubernetesServiceArgs,
                 opts: Optional[pulumi.ResourceOptions] = None) -> None:
        super().__init__('KubernetesService', name,None, opts)

        self.name = name
        self.base_tags = args.base_tags
        self.app_name = args.app_name
        self.container_ports = args.container_ports
        self.environment_variables = args.environment_variables
        self.image = args.image
        self.kube_issuer = args.kube_issuer
        self.namespace = args.namespace
        self.openid_connector = args.openid_connector
        self.public_load_balancer = args.public_load_balancer
        self.secrets_data = args.secrets_data
        self.service_permissions = args.service_permissions
        self.hostname_list = args.hostname_list
        self.ingress_port = args.ingress_port
        self.replicas = args.replicas


        if len(self.service_permissions) > 0:
            policy_doc = aws.iam.get_policy_document(
                statements=self.service_permissions
            )

            self.policy = aws.iam.Policy(
                f"{self.name}-policy",
                policy=policy_doc.json,
                tags=self.base_tags,
                opts=pulumi.ResourceOptions(
                    parent=self
                )
            )

        service_role_assume_policy = aws.iam.get_policy_document(
            statements=[
                aws.iam.GetPolicyDocumentStatementArgs(
                    effect="Allow",
                    principals=[
                        aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                            identifiers=[self.openid_connector],
                            type='Federated'
                        )
                    ],
                    actions=['sts:AssumeRoleWithWebIdentity'],
                    conditions=[
                        aws.iam.GetPolicyDocumentStatementConditionArgs(
                           test="StringEquals",
                            variable=self.kube_issuer.apply(lambda ki: f"{ki.replace('https://', '')}:sub"),
                            values=[
                                self.namespace.apply(lambda ns: f"system:serviceaccount:{ns}:{self.name}")
                            ]
                        )
                    ]
                )
            ]
        )

        self.service_role = aws.iam.Role(
            f"{self.name}-role",
            assume_role_policy=service_role_assume_policy.json,
            name=f"{self.name}-role",
            tags=self.base_tags,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )
        ## Kubernetes resources ##


        # Service account
        self.sa = k8s.core.v1.ServiceAccount(
            f"{self.name}-sa",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                annotations={
                    "eks.amazonaws.com/role-arn": self.service_role.arn
                },
                name=self.name,
                namespace=self.namespace
            ),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )


        if len(self.service_permissions) > 0:
            aws.iam.RolePolicyAttachment(
                f"{self.name}-roleattach",
                role=self.service_role.name,
                policy_arn=self.policy.arn,
                opts=pulumi.ResourceOptions(
                    parent=self
                )
            )
        # Secrets

        self.secrets = k8s.core.v1.Secret(
            f"{self.name}-secrets",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=f"{self.name}",
                namespace=self.namespace
            ),
            string_data=self.secrets_data,
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Deployment

        self.deployment = k8s.apps.v1.Deployment(
            f"{self.name}-deployment",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={
                    "app.kubernetes.io/name": self.name
                },
                name=self.name,
                namespace=self.namespace
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=self.replicas,
                selector=k8s.meta.v1.LabelSelectorArgs(
                    match_labels={
                        "app.kubernetes.io/name": self.name
                    }
                ),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(
                        labels={
                            "app.kubernetes.io/name": self.name
                        },
                    ),
                    spec=k8s.core.v1.PodSpecArgs(
                        # service_account_name=self.sa.metadata.name,
                        containers=[
                            k8s.core.v1.ContainerArgs(
                                name=self.app_name,
                                env=[
                                    k8s.core.v1.EnvVarArgs(
                                        name=k,
                                        value=v
                                    ) for k, v in self.environment_variables.items()],
                                env_from=[
                                    k8s.core.v1.EnvFromSourceArgs(
                                        secret_ref=k8s.core.v1.SecretEnvSourceArgs(
                                            name=self.secrets.metadata.name
                                        )
                                    )
                                ],
                                image=self.image,
                                image_pull_policy="Always",
                                ports=[
                                    k8s.core.v1.ContainerPortArgs(
                                        name=f"{p}-tcp",
                                        container_port=p
                                    ) for p in self.container_ports
                                ]
                            )
                        ],
                        service_account_name=self.sa.metadata.name
                    )
                )
            ),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Autoscaling
        self.autoscaling = k8s.autoscaling.v2.HorizontalPodAutoscaler(
            f"{self.name}-app-hpa",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={
                    "app.kubernetes.io/name": self.name
                },
                name=self.name,
                namespace=self.namespace
            ),
            spec=k8s.autoscaling.v2.HorizontalPodAutoscalerSpecArgs(
                scale_target_ref=k8s.autoscaling.v2.CrossVersionObjectReferenceArgs(
                    api_version="apps/v1",
                    kind="Deployment",
                    name=self.name
                ),
                min_replicas=1,
                max_replicas=6,
                metrics=[
                    k8s.autoscaling.v2.MetricSpecArgs(
                        type="Resource",
                        resource=k8s.autoscaling.v2.ResourceMetricSourceArgs(
                            name='cpu',
                            target=k8s.autoscaling.v2.MetricTargetArgs(
                                type="Utilization",
                                average_value="60"
                            )
                        )
                    ),
                    k8s.autoscaling.v2.MetricSpecArgs(
                        type="Resource",
                        resource=k8s.autoscaling.v2.ResourceMetricSourceArgs(
                            name='memory',
                            target=k8s.autoscaling.v2.MetricTargetArgs(
                                type="Utilization",
                                average_value="60"
                            )
                        )
                    )
                ]
            ),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Service

        self.service = k8s.core.v1.Service(
            f"{self.name}-service",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={
                    "app.kubernetes.io/name": self.name
                },
                name=self.name,
                namespace=self.namespace
            ),
            spec=k8s.core.v1.ServiceSpecArgs(
                ports=[
                    k8s.core.v1.ServicePortArgs(
                        port=p,
                        name=f"{p}-tcp"
                    ) for p in self.container_ports
                ],
                selector={
                    "app.kubernetes.io/name": self.name
                }
            ),
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        # Ingress
        # Requires Traefik chart
        self.records = []
        if len(self.hostname_list) > 0:
            hosts = ",".join(
                [f"`{h['name']}`" for h in self.hostname_list]
            )
            self.ingress = k8s.apiextensions.CustomResource(
                f"{self.name}-ing",
                api_version="traefik.containo.us/v1alpha1",
                kind="IngressRoute",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=self.name,
                    namespace=self.namespace
                ),
                spec={
                    "entryPoints": ["web"],
                    "routes": [
                        {
                            'kind': 'Rule',
                            'match': f"Host({hosts})",
                            'priority': 10,
                            'services': [
                                {
                                    'kind': 'Service',
                                    'name': self.name,
                                    'namespace': self.namespace,
                                    'passHostHeader': True,
                                    'port': self.ingress_port,
                                    'scheme': 'http'
                                }
                            ]
                        }
                    ]
                },
                opts=pulumi.ResourceOptions(
                    parent=self
                )
            )

            for nrec, rec in enumerate(self.hostname_list):
                # A dns record will be created for each of these unless `create_record = False`
                if rec.get('create_record', True):
                    hz = aws.route53.get_zone(
                        name='cloudlan.net'
                    )
                    self.records.append(aws.route53.Record(
                        f"{self.name}-record{nrec}",
                        zone_id=hz.zone_id,
                        name=rec['name'],
                        type='CNAME',
                        ttl=300,
                        records=[self.public_load_balancer],
                        opts=pulumi.ResourceOptions(
                            parent=self
                        )
                    ))

