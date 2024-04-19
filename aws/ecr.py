import boto3

class ECR():
    """Helper class for building ECR clients"""
    def __init__(self):
        self.ecr = boto3.client('ecr')
