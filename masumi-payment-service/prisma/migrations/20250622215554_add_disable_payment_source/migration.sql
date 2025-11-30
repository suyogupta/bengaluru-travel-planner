-- AlterTable
ALTER TABLE "PaymentSource" ADD COLUMN     "disablePaymentAt" TIMESTAMP(3),
ADD COLUMN     "disableSyncAt" TIMESTAMP(3);
