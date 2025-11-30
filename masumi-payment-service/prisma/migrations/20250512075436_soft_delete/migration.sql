-- AlterTable
ALTER TABLE "HotWallet" ADD COLUMN     "deletedAt" TIMESTAMP(3);

-- AlterTable
ALTER TABLE "PaymentSource" ADD COLUMN     "deletedAt" TIMESTAMP(3);
