import * as cdk from 'aws-cdk-lib';
import type { Construct } from 'constructs';

import { CHEFPLUSPLUS_SERVICE } from './config/constants';
import { defineChefplusplusStackParameters } from './config/stack-parameters';
import { DjangoFargateService } from './constructs/django-fargate-service';
import { EcsLogGroup } from './constructs/ecs-log-group';
import { FargateCluster } from './constructs/fargate-cluster';
import { PublicApplicationLoadBalancer } from './constructs/public-application-load-balancer';
import { WebTierSecurityGroups } from './constructs/web-tier-security-groups';

/**
 * Orchestrates deploy-time parameters, networking, load balancing, and the Fargate service.
 * Resource implementations live under lib/constructs and lib/config.
 */
export class ChefplusplusStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const parameters = defineChefplusplusStackParameters(this);

    const logging = new EcsLogGroup(this, 'Logging', {
      logGroupName: cdk.Fn.sub('/ecs/${AWS::StackName}/chefplusplus'),
      retentionInDays: CHEFPLUSPLUS_SERVICE.logRetentionDays,
    });

    const webSecurity = new WebTierSecurityGroups(this, 'WebSecurity', {
      vpcId: parameters.vpcId.valueAsString,
      listenerPort: CHEFPLUSPLUS_SERVICE.listenerPort,
      containerPort: CHEFPLUSPLUS_SERVICE.containerPort,
    });

    const alb = new PublicApplicationLoadBalancer(this, 'PublicAlb', {
      vpcId: parameters.vpcId.valueAsString,
      publicSubnetIds: parameters.publicSubnetIds.valueAsList,
      loadBalancerSecurityGroupId: webSecurity.loadBalancerSecurityGroup.attrGroupId,
      targetPort: CHEFPLUSPLUS_SERVICE.containerPort,
      healthCheckPath: CHEFPLUSPLUS_SERVICE.healthCheckPath,
      listenerPort: CHEFPLUSPLUS_SERVICE.listenerPort,
    });

    const cluster = new FargateCluster(this, 'Cluster', {
      clusterName: cdk.Fn.sub('${AWS::StackName}-cluster'),
    });

    const djangoService = new DjangoFargateService(this, 'DjangoService', {
      parameters,
      cluster: cluster.cluster,
      logGroup: logging.logGroup,
      awsRegion: this.region,
      subnets: parameters.publicSubnetIds.valueAsList,
      serviceSecurityGroupId: webSecurity.serviceSecurityGroup.attrGroupId,
      targetGroup: alb.targetGroup,
      httpListener: alb.httpListener,
      containerName: CHEFPLUSPLUS_SERVICE.containerName,
      containerPort: CHEFPLUSPLUS_SERVICE.containerPort,
    });

    new cdk.CfnOutput(this, 'LoadBalancerDnsName', {
      description: 'Open this URL in a browser (HTTP on port 80).',
      value: alb.loadBalancer.attrDnsName,
    });

    new cdk.CfnOutput(this, 'ClusterName', {
      value: cluster.cluster.ref,
    });

    new cdk.CfnOutput(this, 'ServiceName', {
      value: djangoService.service.attrName,
    });
  }
}
