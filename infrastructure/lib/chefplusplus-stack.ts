import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import type { Construct } from 'constructs';

import { BEDROCK_MODELS } from './config/bedrock';
import { CHEFPLUSPLUS_DEPLOY_REGION, CHEFPLUSPLUS_SERVICE } from './config/constants';
import { defineChefplusplusStackParameters } from './config/stack-parameters';
import { BedrockRag } from './constructs/bedrock-rag';
import { DjangoFargateService } from './constructs/django-fargate-service';
import { EcsLogGroup } from './constructs/ecs-log-group';
import { FargateCluster } from './constructs/fargate-cluster';
import { WebTierSecurityGroups } from './constructs/web-tier-security-groups';

/**
 * Orchestrates deploy-time parameters, networking, and a minimal public-IP Fargate service (no ALB).
 * Resource implementations live under lib/constructs and lib/config.
 */
export class ChefplusplusStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    if (!cdk.Token.isUnresolved(this.region) && this.region !== CHEFPLUSPLUS_DEPLOY_REGION) {
      throw new Error(
        `ChefplusplusStack is pinned to ${CHEFPLUSPLUS_DEPLOY_REGION} (IAD). Got region: ${this.region}.`,
      );
    }

    const parameters = defineChefplusplusStackParameters(this);

    const logging = new EcsLogGroup(this, 'Logging', {
      logGroupName: cdk.Fn.sub('/ecs/${AWS::StackName}/chefplusplus'),
      retentionInDays: CHEFPLUSPLUS_SERVICE.logRetentionDays,
    });

    const webSecurity = new WebTierSecurityGroups(this, 'WebSecurity', {
      vpcId: parameters.vpcId.valueAsString,
      containerPort: CHEFPLUSPLUS_SERVICE.containerPort,
    });

    const cluster = new FargateCluster(this, 'Cluster', {
      clusterName: cdk.Fn.sub('${AWS::StackName}-cluster'),
    });

    const bedrockRag = new BedrockRag(this, 'BedrockRag', { stack: this });

    const djangoService = new DjangoFargateService(this, 'DjangoService', {
      parameters,
      cluster: cluster.cluster,
      logGroup: logging.logGroup,
      awsRegion: this.region,
      subnets: parameters.publicSubnetIds.valueAsList,
      serviceSecurityGroupId: webSecurity.serviceSecurityGroup.attrGroupId,
      containerName: CHEFPLUSPLUS_SERVICE.containerName,
      containerPort: CHEFPLUSPLUS_SERVICE.containerPort,
      additionalEnvironment: [
        { name: 'BEDROCK_KNOWLEDGE_BASE_ID', value: bedrockRag.knowledgeBase.attrKnowledgeBaseId },
        { name: 'BEDROCK_QWEN_MODEL_ID', value: BEDROCK_MODELS.qwenChatModelId },
      ],
    });

    new iam.CfnPolicy(this, 'EcsTaskBedrockPolicy', {
      policyName: 'chefplusplus-ecs-bedrock',
      roles: [djangoService.taskRole.ref],
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Sid: 'InvokeQwenChat',
            Effect: 'Allow',
            Action: ['bedrock:InvokeModel'],
            Resource: [bedrockRag.qwenChatModelArn],
          },
          {
            Sid: 'RetrieveAndGenerate',
            Effect: 'Allow',
            Action: ['bedrock:Retrieve', 'bedrock:RetrieveAndGenerate'],
            Resource: [bedrockRag.knowledgeBase.attrKnowledgeBaseArn, bedrockRag.qwenChatModelArn],
          },
        ],
      },
    });

    new cdk.CfnOutput(this, 'WebContainerPort', {
      description:
        'HTTP port on the task public IP (http://TASK_PUBLIC_IP:PORT). Get the IP from the running task in ECS; it changes when the task is replaced.',
      value: String(CHEFPLUSPLUS_SERVICE.containerPort),
    });

    new cdk.CfnOutput(this, 'ClusterName', {
      value: cluster.cluster.ref,
    });

    new cdk.CfnOutput(this, 'ServiceName', {
      value: djangoService.service.attrName,
    });

    new cdk.CfnOutput(this, 'BedrockKnowledgeBaseId', {
      description: 'Pass to RetrieveAndGenerate / Retrieve APIs.',
      value: bedrockRag.knowledgeBase.attrKnowledgeBaseId,
    });

    new cdk.CfnOutput(this, 'BedrockKnowledgeDocumentsBucket', {
      description: 'Upload PDF/txt/md here, then sync the knowledge base data source.',
      value: bedrockRag.docBucket.ref,
    });

    new cdk.CfnOutput(this, 'BedrockQwenModelId', {
      description: 'Qwen3 dense 32B (non-Coder) for InvokeModel / RAG generation.',
      value: BEDROCK_MODELS.qwenChatModelId,
    });
  }
}
