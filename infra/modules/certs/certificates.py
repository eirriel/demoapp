"""
Contains a Pulumi ComponentResource for creating the certificates
"""
from typing import Mapping, Sequence

import pulumi
import pulumi_aws as aws


class CertArgs:
    """
    The arguments necessary to construct `Certificates` resource.
    """

    def __init__(self,
                 alt_names: pulumi.Input[Sequence[pulumi.Input[str]]],
                 base_tags: Mapping[str, str],
                 domain_name: pulumi.Input[str],
                 zone_name: pulumi.Input[str] = 'cloudlan.net'):
        """
        Constructs a CertArgs.

        :param alt_names: Aternative domains for certificates.
        :param base_tags: Tags which are applied to all taggable resources.
        :param domain_name: Full fqdn for certificate
        """
        self.alt_names = alt_names
        self.base_tags = base_tags
        self.domain_name = domain_name
        self.zone_name = zone_name


class Certs(pulumi.ComponentResource):
    """
    Creates the infra resources for deploy certificates
    """

    def __init__(self,
                 name: str,
                 args: CertArgs,
                 opts: pulumi.ResourceOptions = None):
        """
        Constructs the infra resources for certificates.

        :param name: The Pulumi resource name. Child resource names are constructed based on this.
        :param args: A CertArgs object.
        :param opts: A pulumi.ResourceOptions object.
        """
        super().__init__('Certs', name, None, opts)

        # Make base info available to other methods
        self.name = name
        # self.description = args.description
        self.alt_names = args.alt_names or []
        self.base_tags = args.base_tags
        self.domain_name = args.domain_name
        self.zone_name = args.zone_name
        self.zone_id = aws.route53.get_zone(name=self.zone_name).zone_id

        self.cert = aws.acm.Certificate(f'{name}-certificate',
            domain_name=self.domain_name,
            subject_alternative_names=self.alt_names,
            tags=self.base_tags,
            validation_method="DNS",
            opts=pulumi.ResourceOptions(
                parent=self
            )
        )

        self.dvo_records = self.cert.domain_validation_options.apply(lambda e: iterate_records(e))
        # pulumi.info(self.dvo_records)

        def iterate_records(dvo):
            dvo_records = []
            for num, f in enumerate(dvo):
                if self.zone_name in f.resource_record_name:
                    dvo_records.append(aws.route53.Record(
                        f'{self.name}-dvo-records-{num}',
                        allow_overwrite=True,
                        name=f.resource_record_name.replace(f".{self.zone_name}.",''),
                        ttl=300,
                        type=f.resource_record_type,
                        records=[
                            f.resource_record_value
                        ],
                        zone_id=self.zone_id,
                        opts=pulumi.ResourceOptions(
                            parent=self.cert
                        )
                    ))
            return dvo_records

 
        super().register_outputs({})

