import { adminAuthenticatedEndpointFactory } from '@/utils/security/auth/admin-authenticated';
import { z } from 'zod';
import { prisma } from '@/utils/db';
import { $Enums, Network, RPCProvider } from '@prisma/client';

export const getRpcProviderKeysSchemaInput = z.object({
  cursorId: z
    .string()
    .min(1)
    .max(250)
    .optional()
    .describe('Used to paginate through the rpc provider keys'),
  limit: z
    .number({ coerce: true })
    .min(1)
    .max(100)
    .default(100)
    .describe('The number of rpc provider keys to return'),
});

export const getRpcProviderKeysSchemaOutput = z.object({
  RpcProviderKeys: z.array(
    z.object({
      id: z.string(),
      rpcProviderApiKey: z.string(),
      rpcProvider: z.nativeEnum(RPCProvider),
      createdAt: z.date(),
      updatedAt: z.date(),
      network: z.nativeEnum(Network),
    }),
  ),
});

export const queryRpcProviderKeysEndpointGet =
  adminAuthenticatedEndpointFactory.build({
    method: 'get',
    input: getRpcProviderKeysSchemaInput,
    output: getRpcProviderKeysSchemaOutput,
    handler: async ({
      input,
      options,
    }: {
      input: z.infer<typeof getRpcProviderKeysSchemaInput>;
      options: {
        id: string;
        permission: $Enums.Permission;
        networkLimit: $Enums.Network[];
        usageLimited: boolean;
      };
    }) => {
      const rpcProviderKeys = await prisma.paymentSourceConfig.findMany({
        cursor: input.cursorId ? { id: input.cursorId } : undefined,
        take: input.limit,
        orderBy: { createdAt: 'asc' },
        where: {
          PaymentSource: {
            network: { in: options.networkLimit },
          },
        },
        include: {
          PaymentSource: true,
        },
      });

      return {
        RpcProviderKeys: rpcProviderKeys.map((rpcProviderKey) => ({
          id: rpcProviderKey.id,
          rpcProviderApiKey: rpcProviderKey.rpcProviderApiKey,
          rpcProvider: rpcProviderKey.rpcProvider,
          createdAt: rpcProviderKey.createdAt,
          updatedAt: rpcProviderKey.updatedAt,
          network: rpcProviderKey.PaymentSource!.network,
        })),
      };
    },
  });
