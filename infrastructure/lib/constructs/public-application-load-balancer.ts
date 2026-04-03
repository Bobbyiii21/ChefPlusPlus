import * as cdk from 'aws-cdk-lib';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { Construct } from 'constructs';

export interface PublicApplicationLoadBalancerProps {
  readonly vpcId: string;
  readonly publicSubnetIds: string[];
  readonly loadBalancerSecurityGroupId: string;
  readonly targetPort: number;
  readonly healthCheckPath: string;
  readonly listenerPort: number;
}

/**
 * Internet-facing ALB, HTTP listener, and IP target group for Fargate awsvpc tasks.
 */
export class PublicApplicationLoadBalancer extends Construct {
  public readonly loadBalancer: elbv2.CfnLoadBalancer;
  public readonly targetGroup: elbv2.CfnTargetGroup;
  public readonly httpListener: elbv2.CfnListener;

  constructor(scope: Construct, id: string, props: PublicApplicationLoadBalancerProps) {
    super(scope, id);

    this.loadBalancer = new elbv2.CfnLoadBalancer(this, 'Alb', {
      name: cdk.Fn.sub('${AWS::StackName}-alb'),
      scheme: 'internet-facing',
      type: 'application',
      subnets: props.publicSubnetIds,
      securityGroups: [props.loadBalancerSecurityGroupId],
    });
    this.loadBalancer.overrideLogicalId('LoadBalancer');

    this.targetGroup = new elbv2.CfnTargetGroup(this, 'Tg', {
      name: cdk.Fn.sub('${AWS::StackName}-tg'),
      vpcId: props.vpcId,
      port: props.targetPort,
      protocol: 'HTTP',
      targetType: 'ip',
      healthCheckEnabled: true,
      healthCheckPath: props.healthCheckPath,
      healthCheckProtocol: 'HTTP',
      matcher: { httpCode: '200-399' },
    });
    this.targetGroup.overrideLogicalId('TargetGroup');

    this.httpListener = new elbv2.CfnListener(this, 'Http', {
      defaultActions: [
        {
          type: 'forward',
          targetGroupArn: this.targetGroup.ref,
        },
      ],
      loadBalancerArn: this.loadBalancer.ref,
      port: props.listenerPort,
      protocol: 'HTTP',
    });
    this.httpListener.overrideLogicalId('HttpListener');
  }
}
