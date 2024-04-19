# ecs-service-deploy
Depoloys updated service images to corresponding ecs services

NOTE: This is meant to be deployed as a Lambda function in AWS, I have a TODO to document the packaging and deployment steps. All instructions below assume that this has already been deployed to lambda, and invoked via a Slack > AWS chatbot integration. This can also be invoked similarly with the aws cli.

## How to use:
in the svod-releases slack channel you can run this script in two ways:

### Verbose:

```
@aws run ecs-deploy --cluster <cluster name> --service <service name> --image_tag <image tag name>
```

### Shortform:

If running shortform, the cluster, service, and tag must be defined in that order.

```
@aws run ecs-deploy <cluster name> <service name> <image tag name>
```

