import boto3

class SNS():
    """Helper class for building SNS clients"""
    def __init__(self):
        self.sns = boto3.client('sns')
