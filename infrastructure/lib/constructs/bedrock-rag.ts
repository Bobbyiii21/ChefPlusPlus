import * as cdk from 'aws-cdk-lib';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

import { BEDROCK_KB_VECTOR, BEDROCK_MODELS } from '../config/bedrock';

export interface BedrockRagProps {
  readonly stack: cdk.Stack;
}

/**
 * S3-backed Bedrock Knowledge Base (Titan embeddings) on OpenSearch Serverless,
 * plus IAM for the ECS task to invoke Qwen3 chat and RetrieveAndGenerate against the KB.
 */
export class BedrockRag extends Construct {
  public readonly docBucket: s3.CfnBucket;
  public readonly knowledgeBaseServiceRole: iam.CfnRole;
  public readonly knowledgeBase: bedrock.CfnKnowledgeBase;
  public readonly dataSource: bedrock.CfnDataSource;
  public readonly opensearchCollection: opensearchserverless.CfnCollection;
  public readonly embeddingModelArn: string;
  public readonly qwenChatModelArn: string;

  constructor(scope: Construct, id: string, props: BedrockRagProps) {
    super(scope, id);

    const { stack } = props;

    const collectionName = cdk.Fn.join('', ['ckb', cdk.Aws.ACCOUNT_ID]);
    const collectionResource = cdk.Fn.join('', ['collection/ckb', cdk.Aws.ACCOUNT_ID]);
    // OpenSearch Serverless policy names must be ≤32 chars; use fixed names (one chefplusplus stack per region).
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'OssEncryptionPolicy', {
      name: 'chefplusplus-kb-enc',
      type: 'encryption',
      policy: cdk.Fn.join('', [
        '[{"Rules":[{"Resource":["',
        collectionResource,
        '"],"ResourceType":"collection"}],"AWSOwnedKey":true}]',
      ]),
    });

    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'OssNetworkPolicy', {
      name: 'chefplusplus-kb-net',
      type: 'network',
      policy: cdk.Fn.join('', [
        '[{"Rules":[{"Resource":["',
        collectionResource,
        '"],"ResourceType":"collection"}],"AllowFromPublic":true}]',
      ]),
    });

    this.knowledgeBaseServiceRole = new iam.CfnRole(this, 'KnowledgeBaseServiceRole', {
      assumeRolePolicyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Effect: 'Allow',
            Principal: { Service: 'bedrock.amazonaws.com' },
            Action: 'sts:AssumeRole',
          },
        ],
      },
    });

    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'OssDataAccessPolicy', {
      name: 'chefplusplus-kb-dap',
      type: 'data',
      policy: cdk.Fn.sub(
        '[{"Rules":[{"Resource":["collection/ckb${AccountId}"],"Permission":["aoss:APIAccessAll"],"ResourceType":"collection"},{"Resource":["index/ckb${AccountId}/*"],"Permission":["aoss:APIAccessAll"],"ResourceType":"index"}],"Principal":["${PrincipalArn}"]}]',
        {
          AccountId: cdk.Aws.ACCOUNT_ID,
          PrincipalArn: this.knowledgeBaseServiceRole.attrArn,
        },
      ),
    });

    this.opensearchCollection = new opensearchserverless.CfnCollection(this, 'KbVectorCollection', {
      name: collectionName,
      type: 'VECTORSEARCH',
      standbyReplicas: 'DISABLED',
      description: 'Vector store for Bedrock Knowledge Base (chefplusplus)',
    });
    this.opensearchCollection.addDependency(encryptionPolicy);
    this.opensearchCollection.addDependency(networkPolicy);
    dataAccessPolicy.addDependency(this.knowledgeBaseServiceRole);
    dataAccessPolicy.addDependency(this.opensearchCollection);

    this.docBucket = new s3.CfnBucket(this, 'KnowledgeDocuments', {
      bucketEncryption: {
        serverSideEncryptionConfiguration: [
          { serverSideEncryptionByDefault: { sseAlgorithm: 'AES256' } },
        ],
      },
      publicAccessBlockConfiguration: {
        blockPublicAcls: true,
        blockPublicPolicy: true,
        ignorePublicAcls: true,
        restrictPublicBuckets: true,
      },
    });

    this.embeddingModelArn = stack.formatArn({
      account: '',
      region: stack.region,
      service: 'bedrock',
      resource: 'foundation-model',
      resourceName: BEDROCK_MODELS.embeddingModelId,
    });

    this.qwenChatModelArn = stack.formatArn({
      account: '',
      region: stack.region,
      service: 'bedrock',
      resource: 'foundation-model',
      resourceName: BEDROCK_MODELS.qwenChatModelId,
    });

    const kbS3Policy = new iam.CfnPolicy(this, 'KnowledgeBaseS3Policy', {
      policyName: 'BedrockKB-S3',
      roles: [this.knowledgeBaseServiceRole.ref],
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Effect: 'Allow',
            Action: ['s3:GetObject', 's3:ListBucket'],
            Resource: [this.docBucket.attrArn, cdk.Fn.join('', [this.docBucket.attrArn, '/*'])],
          },
        ],
      },
    });

    const kbEmbedPolicy = new iam.CfnPolicy(this, 'KnowledgeBaseBedrockEmbedPolicy', {
      policyName: 'BedrockKB-Embed',
      roles: [this.knowledgeBaseServiceRole.ref],
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Effect: 'Allow',
            Action: ['bedrock:InvokeModel'],
            Resource: [this.embeddingModelArn],
          },
        ],
      },
    });

    const kbAossPolicy = new iam.CfnPolicy(this, 'KnowledgeBaseOpenSearchPolicy', {
      policyName: 'BedrockKB-AOSS',
      roles: [this.knowledgeBaseServiceRole.ref],
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Effect: 'Allow',
            Action: ['aoss:APIAccessAll'],
            Resource: [this.opensearchCollection.attrArn],
          },
        ],
      },
    });

    this.knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'KnowledgeBase', {
      name: cdk.Fn.sub('${AWS::StackName}-kb'),
      description: 'Chefplusplus docs (S3) with Titan embeddings; query with Qwen3 from the app.',
      roleArn: this.knowledgeBaseServiceRole.attrArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: this.embeddingModelArn,
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: this.opensearchCollection.attrArn,
          vectorIndexName: BEDROCK_KB_VECTOR.vectorIndexName,
          fieldMapping: {
            vectorField: BEDROCK_KB_VECTOR.vectorField,
            textField: BEDROCK_KB_VECTOR.textField,
            metadataField: BEDROCK_KB_VECTOR.metadataField,
          },
        },
      },
    });
    this.knowledgeBase.addDependency(this.opensearchCollection);
    this.knowledgeBase.addDependency(dataAccessPolicy);
    this.knowledgeBase.addDependency(kbS3Policy);
    this.knowledgeBase.addDependency(kbEmbedPolicy);
    this.knowledgeBase.addDependency(kbAossPolicy);

    this.dataSource = new bedrock.CfnDataSource(this, 'KnowledgeBaseS3DataSource', {
      knowledgeBaseId: this.knowledgeBase.attrKnowledgeBaseId,
      name: 's3-documents',
      description: 'Documents in the knowledge bucket (start sync from console or StartIngestionJob).',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: this.docBucket.attrArn,
        },
      },
    });
    this.dataSource.addDependency(this.knowledgeBase);
  }
}
