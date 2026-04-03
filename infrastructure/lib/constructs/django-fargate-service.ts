import * as cdk from 'aws-cdk-lib';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

import { CHEFPLUSPLUS_SERVICE } from '../config/constants';
import type { ChefplusplusStackParameters } from '../config/stack-parameters';

export interface DjangoFargateServiceProps {
  readonly parameters: ChefplusplusStackParameters;
  readonly cluster: ecs.CfnCluster;
  readonly logGroup: logs.CfnLogGroup;
  readonly awsRegion: string;
  readonly subnets: string[];
  readonly serviceSecurityGroupId: string;
  readonly targetGroup: elbv2.CfnTargetGroup;
  readonly httpListener: elbv2.CfnListener;
  readonly containerName: string;
  readonly containerPort: number;
}

/**
 * Fargate task definition (Django + Gunicorn), IAM roles, and ECS service wired to the target group.
 */
export class DjangoFargateService extends Construct {
  public readonly taskExecutionRole: iam.CfnRole;
  public readonly taskRole: iam.CfnRole;
  public readonly taskDefinition: ecs.CfnTaskDefinition;
  public readonly service: ecs.CfnService;

  constructor(scope: Construct, id: string, props: DjangoFargateServiceProps) {
    super(scope, id);

    const { parameters, cluster, logGroup, awsRegion } = props;

    this.taskExecutionRole = new iam.CfnRole(this, 'ExecRole', {
      assumeRolePolicyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Effect: 'Allow',
            Principal: { Service: 'ecs-tasks.amazonaws.com' },
            Action: 'sts:AssumeRole',
          },
        ],
      },
      managedPolicyArns: ['arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'],
    });
    this.taskExecutionRole.overrideLogicalId('TaskExecutionRole');

    this.taskRole = new iam.CfnRole(this, 'TaskRole', {
      assumeRolePolicyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Effect: 'Allow',
            Principal: { Service: 'ecs-tasks.amazonaws.com' },
            Action: 'sts:AssumeRole',
          },
        ],
      },
    });
    this.taskRole.overrideLogicalId('TaskRole');

    this.taskDefinition = new ecs.CfnTaskDefinition(this, 'TaskDef', {
      cpu: parameters.containerCpu.valueAsString,
      memory: parameters.containerMemory.valueAsString,
      networkMode: 'awsvpc',
      requiresCompatibilities: ['FARGATE'],
      executionRoleArn: this.taskExecutionRole.attrArn,
      taskRoleArn: this.taskRole.attrArn,
      containerDefinitions: [
        {
          name: props.containerName,
          image: parameters.imageUri.valueAsString,
          essential: true,
          portMappings: [{ containerPort: props.containerPort, protocol: 'tcp' }],
          environment: [
            { name: 'DJANGO_ALLOWED_HOSTS', value: parameters.djangoAllowedHosts.valueAsString },
            { name: 'DJANGO_SECRET_KEY', value: parameters.djangoSecretKey.valueAsString },
            { name: 'DJANGO_DEBUG', value: 'false' },
          ],
          logConfiguration: {
            logDriver: 'awslogs',
            options: {
              // Ref for AWS::Logs::LogGroup is the log group name (same as explicit LogGroupName).
              'awslogs-group': logGroup.ref,
              'awslogs-region': awsRegion,
              'awslogs-stream-prefix': CHEFPLUSPLUS_SERVICE.logStreamPrefix,
            },
          },
        },
      ],
    });
    this.taskDefinition.overrideLogicalId('TaskDefinition');

    this.service = new ecs.CfnService(this, 'Service', {
      serviceName: cdk.Fn.sub('${AWS::StackName}-svc'),
      cluster: cluster.ref,
      desiredCount: parameters.desiredCount.valueAsNumber,
      launchType: 'FARGATE',
      taskDefinition: this.taskDefinition.ref,
      networkConfiguration: {
        awsvpcConfiguration: {
          assignPublicIp: 'ENABLED',
          subnets: props.subnets,
          securityGroups: [props.serviceSecurityGroupId],
        },
      },
      loadBalancers: [
        {
          containerName: props.containerName,
          containerPort: props.containerPort,
          targetGroupArn: props.targetGroup.ref,
        },
      ],
    });
    this.service.overrideLogicalId('Service');
    this.service.addDependency(props.httpListener);
  }
}
