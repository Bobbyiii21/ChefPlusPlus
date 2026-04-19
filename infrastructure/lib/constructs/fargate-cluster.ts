import * as ecs from 'aws-cdk-lib/aws-ecs';
import { Construct } from 'constructs';

export interface FargateClusterProps {
  readonly clusterName: string;
}

/**
 * Dedicated ECS cluster for the app (isolates capacity and services from other workloads).
 */
export class FargateCluster extends Construct {
  public readonly cluster: ecs.CfnCluster;

  constructor(scope: Construct, id: string, props: FargateClusterProps) {
    super(scope, id);

    this.cluster = new ecs.CfnCluster(this, 'Resource', {
      clusterName: props.clusterName,
    });
    this.cluster.overrideLogicalId('Cluster');
  }
}
