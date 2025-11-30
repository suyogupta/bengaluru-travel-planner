-- AlterTable
ALTER TABLE "PaymentRequest" ADD COLUMN     "collateralReturnLovelace" BIGINT,
ADD COLUMN     "payByTime" BIGINT;

-- AlterTable
ALTER TABLE "PurchaseRequest" ADD COLUMN     "collateralReturnLovelace" BIGINT,
ADD COLUMN     "payByTime" BIGINT;
