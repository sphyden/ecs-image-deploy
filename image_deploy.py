import time
import copy
import json
import traceback
from config.config import Config
from aws.ecs import ECS
from aws.ecr import ECR
from aws.sns import SNS
import botocore.exceptions

ecs = ECS().ecs
ecr = ECR().ecr
sns = SNS().sns

def start_notification(message_body):
    """Returns custom notification event published to SNS"""
    message = { "version": 1.0,
                "source": "custom",
                "content": {
                    "textType": "client-markdown",
                    "title": "ECS Service Deploy: :beachball: PENDING",
                    "description": message_body
                   }
               }
    topic_arn = "arn:aws:sns:us-east-1:928401392503:ecs-deployment-notifications-snstopic"
    response = sns.publish(TopicArn=topic_arn, Message=json.dumps(message))
    return response

def fail_notification(message_body):
    """Returns custom notification event published to SNS"""
    message = { "version": 1.0,
                "source": "custom",
                "content": {
                    "textType": "client-markdown",
                    "title": "ECS Service Deploy: :x: FAILED",
                    "description": message_body
                   }    
               }
    topic_arn = "arn:aws:sns:us-east-1:928401392503:ecs-deployment-notifications-snstopic"
    response = sns.publish(TopicArn=topic_arn, Message=json.dumps(message))
    return response

def pass_notification(message_body):
    """Returns custom notification event published to SNS"""
    message = { "version": 1.0,
                "source": "custom",
                "content": {
                    "textType": "client-markdown",
                    "title": "ECS Service Deploy: :white_check_mark: SUCCESS",
                    "description": message_body
                   }    
               }
    topic_arn = "arn:aws:sns:us-east-1:928401392503:ecs-deployment-notifications-snstopic"
    response = sns.publish(TopicArn=topic_arn, Message=json.dumps(message))
    return response

def validate_cluster(cluster):
    clusters = ["pe", "stage", "production"]
    if cluster in clusters:
        return True
    return False

def validate_service(config, service):
    services = config.keys()
    if service in services:
        return True
    return False

def scrub_tag(image_tag):
    """Ensures we return the valid tag if a branch name with / char is passed"""
    if "/" in image_tag:
        return image_tag.split("/")[-1]
    else:
        return image_tag

def validate_tag(repo, image_tag):
    """Checks to see if the image_tag string passed in matches an actual tag in ECR"""
    try:
        response = ecr.describe_images(
            repositoryName=repo,
            imageIds=[{'imageTag': image_tag}], 
            filter={'tagStatus': 'TAGGED'})
    except ecr.exceptions.ImageNotFoundException:
        return False
    return True

def get_version_tag(repo, image_tag):
    response = ecr.describe_images(
        repositoryName=repo,
        imageIds=[{'imageTag': image_tag}],
        filter={'tagStatus': 'TAGGED'})

    for image in response['imageDetails']:
        for tag in image['imageTags']:
            if tag.startswith('v') and "." in tag:
                return tag
    return ""

def get_existing_task_definition_name(cluster, service):
    """Returns the current task definition name used by a given service running in ECS"""
    response = ecs.describe_services(cluster=cluster, services=[service])
    existing_task_definition_name = response['services'][0][
        'deployments'][0]['taskDefinition']
    return existing_task_definition_name

def describe_existing_task_defintion(existing_task_definition_name):
    """Retrieves the task definition from AWS"""
    response = ecs.describe_task_definition(
        taskDefinition=existing_task_definition_name)
    return response

def create_new_task_definition_revision(existing_task_definition, image_tag, version):
    """Creates a new task definition dictionary pointing to the new tag"""
    task_definition = existing_task_definition['taskDefinition']
    new_task_definition = copy.deepcopy(task_definition)
    aws_reserved_params = ['status',
                           'compatibilities',
                           'taskDefinitionArn',
                           'registeredAt',
                           'registeredBy',
                           'revision',
                           'requiresAttributes']

    for param in aws_reserved_params:
        if new_task_definition.get(param):
            del new_task_definition[param]

    for container in new_task_definition['containerDefinitions']:
        #Image updating logic
        image_uri_base = container['image'].split('/')[0]
        tagged_image = container['image'].split('/')[-1]
        image_basename = tagged_image.split(':')[0]
        if image_basename == "agent":
            continue
        new_tagged_image = f"{image_uri_base}/{image_basename}:{image_tag}"
        container['image'] = new_tagged_image

        #Version tracking logic
        version_key_exists = False
        if version is not "":
            for env_var in container['environment']:
                if env_var['name'] == "DD_VERSION":
                    env_var['value'] = version
                    version_key_exists = True
                    if container.get('dockerLabels'):
                        container['dockerLabels']['com.datadoghq.tags.version'] = version
            
            if version_key_exists == False:    
                new_version_env_var = { 'name': "DD_VERSION",
                                        'value': version }
                container['environment'].append(new_version_env_var)
                if container.get('dockerLabels'):
                    container['dockerLabels']['com.datadoghq.tags.version'] = version
        break

    return new_task_definition

def register_task_definition(new_task_definition):
    """Registers a new task definition given by the dictionary parameter"""
    response = ecs.register_task_definition(**new_task_definition)
    return response['taskDefinition']['taskDefinitionArn']

def update_service(cluster, service, new_task_definition_arn):
    """Performs a deployment of a service to point to a new task definition arn (incl. revision)"""
    response = ecs.update_service(
        cluster=cluster, service=service,
        taskDefinition=new_task_definition_arn)
    return response

def get_deployment_status(cluster, service):
    """Returns whether or not the deployment has completed successfully"""
    response = ecs.describe_services(cluster=cluster, services=[service])
    deployments = response['services'][0]['deployments']
    primary_deployment = {}

    for deployment in deployments:
        if deployment['status'] == "PRIMARY":
            primary_deployment = deployment

    if primary_deployment['desiredCount'] == primary_deployment['runningCount']:
        return True
    return False


def main(event, context):
    """Lambda starts here"""
    config = Config().load_from_file("config/config.yml").get_config()

    print(event)
    cluster = event['cluster']
    image_tag = scrub_tag(event['image_tag'])
    service = event['service']
    repo = config[service]['ecr_repo']
    service_group = []
    valid_cluster = validate_cluster(cluster)
    valid_service = validate_service(config, service)
    valid_tag = validate_tag(repo, image_tag)

    if valid_cluster is False:
        message_body = f"The Cluster provided ({cluster}) does not match one of our ECS clusters"
        fail_notification(message_body)
        return {
            'statusCode': 400,
            'body': json.dumps(message_body)
        }

    if valid_service is False:
        message_body = f"The Service name provided ({service}) does not match on of our ECS services"
        fail_notification(message_body)
        return {
            'statusCode': 400,
            'body': json.dumps(message_body)
        }

    if valid_tag is False:
        message_body = f'The image tag provided ({image_tag}) did not match any tags currently in ECR for {service}, please check the tag string again'
        fail_notification(message_body)
        return {
            'statusCode': 400,
            'body': json.dumps(message_body)
        }

    version = get_version_tag(repo, image_tag)

    service_group = [config[service]['service_name']]

    deployed_services = []
    deployed_tds = []

    start_message_body = f"Attempting to deploy the image_tag: `{image_tag}` to the `{service_group}` services on the `{cluster}` cluster"
    start_notification(start_message_body)

    try:
        for service in service_group:
            existing_task_definition_name = get_existing_task_definition_name(
                cluster, service)
            existing_task_definition = describe_existing_task_defintion(
                existing_task_definition_name)
            new_task_definition = create_new_task_definition_revision(
                existing_task_definition, image_tag, version)
            new_task_definition_arn = register_task_definition(new_task_definition)
            update_service(cluster, service, new_task_definition_arn)

            deployed_services.append(service)
            deployed_tds.append(new_task_definition_arn.split('/')[-1])

        for service in deployed_services:
            retries = 20
            while retries > 0:
                time.sleep(30)
                if get_deployment_status(cluster, service) is True:
                    break
                retries -= 1

    except botocore.exceptions.ClientError as e:
        print(e)
        message_body = "There was an error within the AWS SDK while attempting to deploy, please ask your SRE to look at the logs"
        fail_notification(message_body)
        return {
            'statusCode': 400,
            'body': json.dumps(message_body)
        }
    except Exception:
        traceback.print_exc()
        message_body = "There was Python specific error while attemtping to deploy, please ask your SRE to look at the logs"
        fail_notification(message_body)
        return {
            'statusCode': 400,
            'body': json.dumps(message_body)
        }

    message_body = f'Deployed image tag: `{image_tag}` to the `{deployed_services}` services  on the `{cluster}` cluster'
    pass_notification(message_body)

    return {
        'statusCode': 200,
        'body': json.dumps(message_body)
    }

