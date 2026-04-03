#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { ChefplusplusStack } from '../lib/chefplusplus-stack';

const app = new cdk.App();

new ChefplusplusStack(app, 'ChefplusplusStack', {
  description:
    'ECS Fargate service for chefplusplus (Django in app/ + Gunicorn) behind an Application Load Balancer. ' +
    'Build the image from the repo root (Dockerfile copies ./app). ' +
    'Use public subnets with a route to an internet gateway so tasks can pull images and write logs.',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
