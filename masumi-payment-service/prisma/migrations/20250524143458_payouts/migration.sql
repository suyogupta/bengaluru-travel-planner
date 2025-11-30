-- AlterTable
ALTER TABLE "UnitValue" ADD COLUMN     "buyerWithdrawnPaymentRequestId" TEXT,
ADD COLUMN     "buyerWithdrawnPurchaseRequestId" TEXT,
ADD COLUMN     "sellerWithdrawnPaymentRequestId" TEXT,
ADD COLUMN     "sellerWithdrawnPurchaseRequestId" TEXT;

-- AddForeignKey
ALTER TABLE "UnitValue" ADD CONSTRAINT "UnitValue_sellerWithdrawnPaymentRequestId_fkey" FOREIGN KEY ("sellerWithdrawnPaymentRequestId") REFERENCES "PaymentRequest"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UnitValue" ADD CONSTRAINT "UnitValue_buyerWithdrawnPaymentRequestId_fkey" FOREIGN KEY ("buyerWithdrawnPaymentRequestId") REFERENCES "PaymentRequest"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UnitValue" ADD CONSTRAINT "UnitValue_sellerWithdrawnPurchaseRequestId_fkey" FOREIGN KEY ("sellerWithdrawnPurchaseRequestId") REFERENCES "PurchaseRequest"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UnitValue" ADD CONSTRAINT "UnitValue_buyerWithdrawnPurchaseRequestId_fkey" FOREIGN KEY ("buyerWithdrawnPurchaseRequestId") REFERENCES "PurchaseRequest"("id") ON DELETE SET NULL ON UPDATE CASCADE;
