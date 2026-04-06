/**
 * Shared deployment values for the chefplusplus web tier.
 * Centralizes ports and logging so security groups and tasks stay aligned.
 */

/** All chefplusplus infrastructure is intended for IAD (N. Virginia) only. */
export const CHEFPLUSPLUS_DEPLOY_REGION = 'us-east-1' as const;

export const CHEFPLUSPLUS_SERVICE = {
  containerName: 'chefplusplus',
  containerPort: 8000,
  /** Short retention keeps CloudWatch Logs storage minimal for class / demo stacks. */
  logRetentionDays: 1,
  logStreamPrefix: 'chefplusplus',
} as const;
