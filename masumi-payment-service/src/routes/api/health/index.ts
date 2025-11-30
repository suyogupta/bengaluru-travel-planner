import { unauthenticatedEndpointFactory } from '@/utils/security/auth/not-authenticated';
import { z } from 'zod';

export const healthResponseSchema = z.object({
  status: z.string(),
});

export const healthEndpointGet = unauthenticatedEndpointFactory.build({
  method: 'get',
  input: z.object({}),
  output: healthResponseSchema,
  handler: async () => {
    return {
      status: 'ok',
    };
  },
});
