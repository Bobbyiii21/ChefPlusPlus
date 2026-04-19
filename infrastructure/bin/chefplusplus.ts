#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CHEFPLUSPLUS_DEPLOY_REGION } from '../lib/config/constants';
import { ChefplusplusStack } from '../lib/chefplusplus-stack';

const app = new cdk.App();

new ChefplusplusStack(app, 'ChefplusplusStack', {
  description:
    'Minimal ECS Fargate service for chefplusplus (Django in app/ + Gunicorn) with a task public IP (no ALB), ' +
    'plus Bedrock Knowledge Base (S3 + OpenSearch Serverless) and Qwen3 chat access from the task role. ' +
    'Build the image from the repo root (Dockerfile copies ./app). ' +
    'Use public subnets with a route to an internet gateway so tasks can pull images and write logs.',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: CHEFPLUSPLUS_DEPLOY_REGION,
  },
});
