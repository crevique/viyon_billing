import React from 'react';
import { ReceiptPreview, ReceiptData } from './ReceiptPreview';

export interface ReceiptModalProps {
  isOpen: boolean;
  onClose: () => void;
  billId?: string;
  billNumber?: string;
  initialReceiptData?: ReceiptData | null;
  isReprint?: boolean;
}

export const ReceiptModal: React.FC<ReceiptModalProps> = ({
  isOpen,
  onClose,
  billId,
  billNumber,
  initialReceiptData,
  isReprint = false,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full p-4 overflow-hidden">
        <ReceiptPreview
          billId={billId}
          billNumber={billNumber}
          initialReceiptData={initialReceiptData}
          isReprint={isReprint}
          onClose={onClose}
        />
      </div>
    </div>
  );
};

export default ReceiptModal;
