/**
 * Shared deployment values for the chefplusplus web tier.
 * Centralizes ports and health checks so ALB, security groups, and tasks stay aligned.
 */
export const CHEFPLUSPLUS_SERVICE = {
  containerName: 'chefplusplus',
  containerPort: 8000,
  healthCheckPath: '/admin/login/',
  listenerPort: 80,
  logRetentionDays: 14,
  logStreamPrefix: 'chefplusplus',
} as const;
