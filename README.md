# ecs-service-deploy
Depoloys updated service images to corresponding ecs services

## How to use:
in the svod-releases slack channel you can run this script in two ways:

### Verbose:

```
@aws run ecs-deploy --cluster <production|stage|pe> --service <service name> --image_tag <image tag name>
```

### Shortform:

If running shortform, the cluster, service, and tag must be defined in that order.

```
@aws run ecs-deploy <production|stage|pe> <service name> <image tag name>
```

### Examples:
Deploy the master branch to a FE PE service using the verbose method:

```
@aws run ecs-deploy --cluster pe --service sammy --image_tag master
```

Deploy the master branch to the svod-be service on the staging cluster using the shortform method:

```
@aws run ecs-deploy stage svod-be master
```
