import pulumi
import pulumi_aws as aws
from vpc import Vpc,VpcArgs

envName = pulumi.get_stack()
config = pulumi.Config()

BASE_TAGS = {
    "Environment": envName,
}

# Get first and last from all avaiable AZs
zoneList = aws.get_availability_zones(state="available")
zones = [zoneList.names[i] for i in (0,-1)]

vpc = Vpc(f"{envName}-vpc", VpcArgs(
    description=f"{envName} VPC",
    base_tags=BASE_TAGS,
    base_cidr=config.require('vpc_cidr'),
    availability_zone_names=zones,
    # zone_name="example.local",
    create_s3_endpoint=config.get_bool('create_s3_endpoint', True),
))
vpc.enableFlowLoggingToCloudWatchLogs("ALL")

pulumi.export("vpc_id", vpc.vpc.id)
pulumi.export("vpc_cidr", config.require('vpc_cidr'))
pulumi.export("public_subnet_ids", [subnet.id for subnet in vpc.public_subnets])
pulumi.export("private_subnet_ids", [subnet.id for subnet in vpc.private_subnets])
pulumi.export("nat_gateway_ips", [i.public_ip for i in vpc.nat_elastic_ip_addresses])
