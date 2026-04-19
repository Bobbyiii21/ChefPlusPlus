import * as cdk from 'aws-cdk-lib';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';

export interface EcsLogGroupProps {
  /** CloudWatch Logs group name (may include Fn::Sub). */
  readonly logGroupName: string;
  readonly retentionInDays: number;
}

/**
 * Log group for Fargate task stdout/stderr (awslogs driver).
 */
export class EcsLogGroup extends Construct {
  public readonly logGroup: logs.CfnLogGroup;

  constructor(scope: Construct, id: string, props: EcsLogGroupProps) {
    super(scope, id);

    this.logGroup = new logs.CfnLogGroup(this, 'Resource', {
      logGroupName: props.logGroupName,
      retentionInDays: props.retentionInDays,
    });
    this.logGroup.overrideLogicalId('LogGroup');
  }
}
