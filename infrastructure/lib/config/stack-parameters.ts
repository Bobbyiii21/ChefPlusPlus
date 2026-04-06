import * as cdk from 'aws-cdk-lib';
import type { Stack } from 'aws-cdk-lib';

/**
 * CloudFormation parameters for the stack. Defined once and passed into constructs
 * so deploy-time inputs are documented in a single place.
 */
export interface ChefplusplusStackParameters {
  readonly imageUri: cdk.CfnParameter;
  readonly vpcId: cdk.CfnParameter;
  readonly publicSubnetIds: cdk.CfnParameter;
  readonly desiredCount: cdk.CfnParameter;
  readonly containerCpu: cdk.CfnParameter;
  readonly containerMemory: cdk.CfnParameter;
  readonly djangoAllowedHosts: cdk.CfnParameter;
  readonly djangoSecretKey: cdk.CfnParameter;
}

export function defineChefplusplusStackParameters(stack: Stack): ChefplusplusStackParameters {
  return {
    imageUri: new cdk.CfnParameter(stack, 'ImageUri', {
      type: 'String',
      description:
        'Full container image URI (e.g. ECR after push). Build from repo root: docker build -t NAME . ' +
        '(Dockerfile copies the Django project from ./app).',
    }),

    vpcId: new cdk.CfnParameter(stack, 'VpcId', {
      type: 'AWS::EC2::VPC::Id',
      description: 'VPC where Fargate tasks and security groups are created.',
    }),

    publicSubnetIds: new cdk.CfnParameter(stack, 'PublicSubnetIds', {
      type: 'CommaDelimitedList',
      description:
        'Public subnet ID(s) with a route to an internet gateway. One subnet is enough; use two only if you want tasks spread across AZs.',
    }),

    desiredCount: new cdk.CfnParameter(stack, 'DesiredCount', {
      type: 'Number',
      default: 1,
      description: 'Number of Fargate tasks to run.',
    }),

    containerCpu: new cdk.CfnParameter(stack, 'ContainerCpu', {
      type: 'Number',
      default: 256,
      allowedValues: ['256', '512', '1024', '2048', '4096'],
      description: 'Fargate CPU units.',
    }),

    containerMemory: new cdk.CfnParameter(stack, 'ContainerMemory', {
      type: 'Number',
      default: 512,
      allowedValues: ['512', '1024', '2048', '4096', '8192', '16384'],
      description: 'Fargate memory (MiB).',
    }),

    djangoAllowedHosts: new cdk.CfnParameter(stack, 'DjangoAllowedHosts', {
      type: 'String',
      default: '*',
      description:
        'Comma-separated Host headers Django accepts. Use * for demos, or the task public IP if you restrict hosts.',
    }),

    djangoSecretKey: new cdk.CfnParameter(stack, 'DjangoSecretKey', {
      type: 'String',
      noEcho: true,
      description:
        'Django SECRET_KEY (generate a long random string for anything beyond local testing).',
    }),
  };
}
