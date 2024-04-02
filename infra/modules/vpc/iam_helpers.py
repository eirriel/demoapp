
"""
Contains helper methods for building IAM policies.
"""
import json


def assume_role_policy_for_principal(principal) -> str:
    """
    Creates a policy allowing the given principal to call the sts:AssumeRole
    action.
    :param any principal: The principal
    """
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": principal,
                "Action": "sts:AssumeRole"
            }
        ]
    })