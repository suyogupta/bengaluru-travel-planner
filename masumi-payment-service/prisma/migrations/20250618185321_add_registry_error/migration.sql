-- CreateEnum
CREATE TYPE "CollateralRequestState" AS ENUM ('Pending', 'Confirmed', 'Failed');

-- AlterTable
ALTER TABLE "PaymentSource" ALTER COLUMN "feeRatePermille" DROP DEFAULT,
ALTER COLUMN "cooldownTime" DROP DEFAULT;

-- AlterTable
ALTER TABLE "RegistryRequest" ADD COLUMN     "error" TEXT;

-- CreateTable
CREATE TABLE "CollateralRequest" (
    "id" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "lastCheckedAt" TIMESTAMP(3),
    "paymentSourceId" TEXT NOT NULL,
    "hotWalletId" TEXT NOT NULL,
    "agentIdentifier" TEXT,
    "state" "CollateralRequestState" NOT NULL,
    "transactionId" TEXT,
    "error" TEXT,

    CONSTRAINT "CollateralRequest_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "CollateralRequest_agentIdentifier_key" ON "CollateralRequest"("agentIdentifier");

-- AddForeignKey
ALTER TABLE "CollateralRequest" ADD CONSTRAINT "CollateralRequest_paymentSourceId_fkey" FOREIGN KEY ("paymentSourceId") REFERENCES "PaymentSource"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CollateralRequest" ADD CONSTRAINT "CollateralRequest_hotWalletId_fkey" FOREIGN KEY ("hotWalletId") REFERENCES "HotWallet"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CollateralRequest" ADD CONSTRAINT "CollateralRequest_transactionId_fkey" FOREIGN KEY ("transactionId") REFERENCES "Transaction"("id") ON DELETE SET NULL ON UPDATE CASCADE;
