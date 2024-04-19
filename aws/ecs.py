import boto3

class ECS():
    """Helper class for building ECS clients"""
    def __init__(self):
        self.ecs = boto3.client('ecs')
