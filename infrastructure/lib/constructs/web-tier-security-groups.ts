import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export interface WebTierSecurityGroupsProps {
  readonly vpcId: string;
  readonly listenerPort: number;
  readonly containerPort: number;
}

/**
 * Security groups for internet → ALB → tasks. Keeps task port reachable only from the ALB.
 */
export class WebTierSecurityGroups extends Construct {
  public readonly loadBalancerSecurityGroup: ec2.CfnSecurityGroup;
  public readonly serviceSecurityGroup: ec2.CfnSecurityGroup;

  constructor(scope: Construct, id: string, props: WebTierSecurityGroupsProps) {
    super(scope, id);

    this.loadBalancerSecurityGroup = new ec2.CfnSecurityGroup(this, 'AlbSg', {
      groupDescription: 'Inbound HTTP to ALB',
      vpcId: props.vpcId,
      securityGroupIngress: [
        {
          ipProtocol: 'tcp',
          fromPort: props.listenerPort,
          toPort: props.listenerPort,
          cidrIp: '0.0.0.0/0',
        },
      ],
    });
    this.loadBalancerSecurityGroup.overrideLogicalId('LoadBalancerSecurityGroup');

    this.serviceSecurityGroup = new ec2.CfnSecurityGroup(this, 'ServiceSg', {
      groupDescription: 'ALB to ECS tasks on container port',
      vpcId: props.vpcId,
      securityGroupIngress: [
        {
          ipProtocol: 'tcp',
          fromPort: props.containerPort,
          toPort: props.containerPort,
          sourceSecurityGroupId: this.loadBalancerSecurityGroup.attrGroupId,
        },
      ],
    });
    this.serviceSecurityGroup.overrideLogicalId('ServiceSecurityGroup');
  }
}
