/*
  Warnings:

  - A unique constraint covering the columns `[walletVkey]` on the table `HotWallet` will be added. If there are existing duplicate values, this will fail.
  - A unique constraint covering the columns `[blockchainIdentifier]` on the table `PaymentRequest` will be added. If there are existing duplicate values, this will fail.
  - A unique constraint covering the columns `[network,policyId]` on the table `PaymentSource` will be added. If there are existing duplicate values, this will fail.
  - A unique constraint covering the columns `[blockchainIdentifier]` on the table `PurchaseRequest` will be added. If there are existing duplicate values, this will fail.

*/
-- DropIndex
DROP INDEX "HotWallet_paymentSourceId_walletVkey_key";

-- DropIndex
DROP INDEX "PaymentRequest_paymentSourceId_blockchainIdentifier_key";

-- DropIndex
DROP INDEX "PurchaseRequest_paymentSourceId_blockchainIdentifier_key";

-- AlterTable
ALTER TABLE "PaymentSource" ADD COLUMN     "policyId" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX "HotWallet_walletVkey_key" ON "HotWallet"("walletVkey");

-- CreateIndex
CREATE UNIQUE INDEX "PaymentRequest_blockchainIdentifier_key" ON "PaymentRequest"("blockchainIdentifier");

-- CreateIndex
CREATE UNIQUE INDEX "PaymentSource_network_policyId_key" ON "PaymentSource"("network", "policyId");

-- CreateIndex
CREATE UNIQUE INDEX "PurchaseRequest_blockchainIdentifier_key" ON "PurchaseRequest"("blockchainIdentifier");
