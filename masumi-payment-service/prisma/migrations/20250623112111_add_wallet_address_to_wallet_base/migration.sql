/*
  Warnings:

  - A unique constraint covering the columns `[paymentSourceId,walletVkey,walletAddress,type]` on the table `WalletBase` will be added. If there are existing duplicate values, this will fail.

*/
-- DropIndex
DROP INDEX "WalletBase_paymentSourceId_walletVkey_type_key";

-- AlterTable
ALTER TABLE "WalletBase" ADD COLUMN     "walletAddress" TEXT NOT NULL DEFAULT '';

-- CreateIndex
CREATE UNIQUE INDEX "WalletBase_paymentSourceId_walletVkey_walletAddress_type_key" ON "WalletBase"("paymentSourceId", "walletVkey", "walletAddress", "type");
