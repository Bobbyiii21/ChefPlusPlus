import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export interface WebTierSecurityGroupsProps {
  readonly vpcId: string;
  readonly containerPort: number;
}

/**
 * Single security group: internet → task container port (no ALB).
 * Tasks use a public IP in public subnets; the IP can change when the task is replaced.
 */
export class WebTierSecurityGroups extends Construct {
  public readonly serviceSecurityGroup: ec2.CfnSecurityGroup;

  constructor(scope: Construct, id: string, props: WebTierSecurityGroupsProps) {
    super(scope, id);

    this.serviceSecurityGroup = new ec2.CfnSecurityGroup(this, 'ServiceSg', {
      groupDescription: 'Inbound HTTP to Fargate tasks on container port',
      vpcId: props.vpcId,
      securityGroupIngress: [
        {
          ipProtocol: 'tcp',
          fromPort: props.containerPort,
          toPort: props.containerPort,
          cidrIp: '0.0.0.0/0',
        },
      ],
    });
    this.serviceSecurityGroup.overrideLogicalId('ServiceSecurityGroup');
  }
}
