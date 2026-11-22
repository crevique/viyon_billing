"""Receipt generation service for 58mm thermal printing (SEZNIK Veer).

Retrieves authoritative stored bill snapshots, builds structured receipt models,
formats 32-column monospace thermal print text, and logs immutable print audit entries.
"""

from datetime import datetime, timezone
from decimal import Decimal
import html
from typing import List, Optional
from uuid import UUID, uuid4
import textwrap

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.bill import Bill, BillItem
from app.models.payment import Payment
from app.models.store_settings import StoreSettings
from app.schemas.receipt import (
    ReceiptStoreInfo,
    ReceiptCustomerInfo,
    ReceiptCashierInfo,
    ReceiptItemInfo,
    ReceiptPaymentItem,
    ReceiptPaymentBreakdown,
    ReceiptCancellationDetails,
    ReceiptOut,
    ReceiptPreviewOut,
)


class ReceiptService:
    """Service providing read-only receipt retrieval and 58mm thermal print generation."""

    DEFAULT_STORE_NAME = "VIYON"
    DEFAULT_TAGLINE = "MEN'S COLLECTIONS"
    DEFAULT_ADDRESS = "F6WR+R8W, South Rangasamuthram, North Rangasamuthram, Sathyamangalam, Tamil Nadu 638402"
    DEFAULT_PHONE = "082702 42681"
    DEFAULT_FOOTER = "Thank you for shopping at VIYON! Visit again."
    DEFAULT_CURRENCY = "INR"
    DEFAULT_WIDTH_MM = 58
    THERMAL_COLUMNS = 32  # Standard character width for 58mm paper at 203 DPI (Font A 12x24)

    # --------------------------------------------------------------------------
    # Retrieval Methods
    # --------------------------------------------------------------------------
    @classmethod
    def get_receipt_data(
        cls,
        db: Session,
        bill_id: UUID,
        is_reprint: bool = False,
    ) -> ReceiptOut:
        """Fetch bill and return complete, structured receipt data."""
        bill = db.scalar(
            select(Bill)
            .where(Bill.id == bill_id)
            .options(
                joinedload(Bill.customer),
                joinedload(Bill.staff_user),
                joinedload(Bill.cancelled_by_user),
                joinedload(Bill.items),
                joinedload(Bill.payments),
            )
        )
        if not bill:
            raise ValueError(f"Bill with ID '{bill_id}' was not found.")

        return cls._build_receipt_out(db, bill, is_reprint=is_reprint)

    @classmethod
    def get_receipt_data_by_number(
        cls,
        db: Session,
        bill_number: str,
        is_reprint: bool = False,
    ) -> ReceiptOut:
        """Fetch bill by its unique human-readable bill number."""
        clean_number = bill_number.strip()
        bill = db.scalar(
            select(Bill)
            .where(Bill.bill_number == clean_number)
            .options(
                joinedload(Bill.customer),
                joinedload(Bill.staff_user),
                joinedload(Bill.cancelled_by_user),
                joinedload(Bill.items),
                joinedload(Bill.payments),
            )
        )
        if not bill:
            raise ValueError(f"Bill with number '{clean_number}' was not found.")

        return cls._build_receipt_out(db, bill, is_reprint=is_reprint)

    @classmethod
    def get_receipt_preview(
        cls,
        db: Session,
        bill_id: UUID,
        is_reprint: bool = False,
    ) -> ReceiptPreviewOut:
        """Return structured receipt data plus pre-rendered thermal text and HTML preview."""
        receipt = cls.get_receipt_data(db, bill_id, is_reprint=is_reprint)
        html_preview = cls.generate_html_receipt(receipt)
        return ReceiptPreviewOut(
            receipt_data=receipt,
            formatted_text=receipt.raw_text,
            html_preview=html_preview,
        )

    # --------------------------------------------------------------------------
    # Audit Logging
    # --------------------------------------------------------------------------
    @classmethod
    def record_print_audit(
        cls,
        db: Session,
        bill_id: UUID,
        user_id: UUID,
        is_reprint: bool = False,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Record receipt print or reprint event into immutable audit trail."""
        bill = db.scalar(select(Bill).where(Bill.id == bill_id))
        if not bill:
            raise ValueError(f"Bill with ID '{bill_id}' was not found.")

        now_utc = datetime.now(timezone.utc)
        action_name = "RECEIPT_REPRINTED" if is_reprint else "RECEIPT_PRINTED"

        audit = AuditLog(
            id=uuid4(),
            user_id=user_id,
            action=action_name,
            entity_type="BILL",
            entity_id=bill.id,
            old_values=None,
            new_values={
                "bill_number": bill.bill_number,
                "is_reprint": is_reprint,
                "printed_at": now_utc.isoformat(),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit

    # --------------------------------------------------------------------------
    # Receipt Builder
    # --------------------------------------------------------------------------
    @classmethod
    def _build_receipt_out(
        cls,
        db: Session,
        bill: Bill,
        is_reprint: bool = False,
    ) -> ReceiptOut:
        """Assemble authoritative ReceiptOut instance from frozen bill records."""
        # 1. Store settings
        store_settings = db.scalar(
            select(StoreSettings).where(StoreSettings.is_active_config.is_(True))
        )
        store_info = ReceiptStoreInfo(
            store_name=store_settings.store_name if store_settings else cls.DEFAULT_STORE_NAME,
            tagline=store_settings.tagline if (store_settings and store_settings.tagline) else cls.DEFAULT_TAGLINE,
            address=store_settings.address if store_settings else cls.DEFAULT_ADDRESS,
            phone=store_settings.phone if store_settings else cls.DEFAULT_PHONE,
            email=store_settings.email if store_settings else None,
            gstin=store_settings.gstin if store_settings else None,
            receipt_footer=store_settings.receipt_footer if (store_settings and store_settings.receipt_footer) else cls.DEFAULT_FOOTER,
            currency_code=store_settings.currency_code if store_settings else cls.DEFAULT_CURRENCY,
            receipt_width_mm=store_settings.receipt_width_mm if store_settings else cls.DEFAULT_WIDTH_MM,
        )

        # 2. Customer
        customer_info: Optional[ReceiptCustomerInfo] = None
        if bill.customer:
            customer_info = ReceiptCustomerInfo(
                id=bill.customer.id,
                full_name=bill.customer.customer_name,
                phone_number=bill.customer.phone,
            )

        # 3. Cashier
        cashier_info = ReceiptCashierInfo(
            id=bill.staff_user.id,
            full_name=bill.staff_user.full_name,
            email=bill.staff_user.email,
        )

        # 4. Line items (from frozen snapshot records)
        items: List[ReceiptItemInfo] = []
        item_discount_sum = Decimal("0.00")
        for item in bill.items:
            item_discount_sum += item.discount_amount
            items.append(
                ReceiptItemInfo(
                    id=item.id,
                    product_name=item.product_name_snapshot,
                    sku=item.sku_snapshot,
                    size=item.size_snapshot,
                    color=item.color_snapshot,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount_amount=item.discount_amount,
                    tax_amount=item.tax_amount,
                    line_total=item.line_total,
                )
            )

        # 5. Financial breakdown
        subtotal = bill.subtotal
        bill_discount = max(Decimal("0.00"), bill.discount_amount - item_discount_sum)
        total_discount = bill.discount_amount
        tax_amount = bill.tax_amount
        grand_total = bill.total_amount

        # 6. Payment breakdown
        confirmed_cash = Decimal("0.00")
        confirmed_upi = Decimal("0.00")
        pending_upi = Decimal("0.00")
        payment_items: List[ReceiptPaymentItem] = []

        sorted_payments = sorted(bill.payments, key=lambda p: p.created_at)
        for p in sorted_payments:
            if p.payment_status == "CONFIRMED":
                if p.payment_method == "CASH":
                    confirmed_cash += p.amount
                elif p.payment_method == "UPI":
                    confirmed_upi += p.amount
            elif p.payment_status == "PENDING" and p.payment_method == "UPI":
                pending_upi += p.amount

            payment_items.append(
                ReceiptPaymentItem(
                    id=p.id,
                    payment_method=p.payment_method,
                    amount=p.amount,
                    payment_status=p.payment_status,
                    transaction_reference=p.transaction_reference,
                    created_at=p.created_at,
                )
            )

        has_pending_upi = (pending_upi > Decimal("0.00"))
        confirmed_paid = confirmed_cash + confirmed_upi
        balance = max(Decimal("0.00"), grand_total - confirmed_paid)

        # Determine readable payment method label
        if confirmed_cash > Decimal("0.00") and confirmed_upi > Decimal("0.00"):
            method_label = "SPLIT (CASH + UPI)"
        elif confirmed_cash > Decimal("0.00"):
            method_label = "CASH"
        elif confirmed_upi > Decimal("0.00"):
            method_label = "UPI"
        elif has_pending_upi:
            method_label = "UPI"
        else:
            method_label = "UNPAID"

        payment_breakdown = ReceiptPaymentBreakdown(
            confirmed_cash=confirmed_cash,
            confirmed_upi=confirmed_upi,
            pending_upi=pending_upi,
            has_pending_upi=has_pending_upi,
            payments=payment_items,
        )

        # 7. Cancellation details
        is_cancelled = (bill.bill_status == "CANCELLED")
        cancellation_details: Optional[ReceiptCancellationDetails] = None
        if is_cancelled:
            canceller_name = (
                bill.cancelled_by_user.full_name if bill.cancelled_by_user else "Store Owner"
            )
            cancellation_details = ReceiptCancellationDetails(
                cancelled_at=bill.cancelled_at,
                cancelled_by_user=canceller_name,
                cancellation_reason=bill.cancellation_reason,
                refund_review_amount=confirmed_paid,
            )

        receipt = ReceiptOut(
            bill_id=bill.id,
            bill_number=bill.bill_number,
            bill_date=bill.bill_date,
            created_at=bill.created_at,
            store=store_info,
            customer=customer_info,
            cashier=cashier_info,
            items=items,
            subtotal=subtotal,
            item_discount_total=item_discount_sum,
            bill_discount_amount=bill_discount,
            discount_amount=total_discount,
            tax_amount=tax_amount,
            grand_total=grand_total,
            amount_paid=confirmed_paid,
            balance=balance,
            payment_method=method_label,
            payment_status="PAID" if bill.payment_status in ("PAID", "CONFIRMED") else (bill.payment_status or "PAID"),
            bill_status=bill.bill_status,
            payment_breakdown=payment_breakdown,
            is_cancelled=is_cancelled,
            cancellation_details=cancellation_details,
            is_reprint=is_reprint,
            raw_text="",
        )

        receipt.raw_text = cls.format_thermal_receipt_58mm(receipt, width=cls.THERMAL_COLUMNS)
        return receipt

    # --------------------------------------------------------------------------
    # Thermal Monospace Formatter (58mm / 32 Columns)
    # --------------------------------------------------------------------------
    @classmethod
    def format_thermal_receipt_58mm(cls, receipt: ReceiptOut, width: int = 32) -> str:
        """Format 32-column monospace thermal receipt text suitable for ESC/POS SEZNIK Veer."""
        lines: List[str] = []

        def center(text: str) -> str:
            return text.strip().center(width)[:width]

        def row(left: str, right: str) -> str:
            total_spaces = width - len(left) - len(right)
            if total_spaces < 1:
                return f"{left[:width - len(right) - 1]} {right}"
            return f"{left}{' ' * total_spaces}{right}"

        def divider(char: str = "-") -> str:
            return char * width

        def wrap_lines(text: str) -> List[str]:
            return textwrap.wrap(text, width=width)

        # 1. Header Banner
        lines.append(divider("="))
        lines.append(center(receipt.store.store_name))
        if receipt.store.tagline:
            lines.append(center(receipt.store.tagline))

        # Store Address & Phone
        for addr_line in wrap_lines(receipt.store.address):
            lines.append(center(addr_line))
        lines.append(center(f"Phone: {receipt.store.phone}"))
        if receipt.store.gstin:
            lines.append(center(f"GSTIN: {receipt.store.gstin}"))
        lines.append(divider("="))

        # 2. Reprint Badge
        if receipt.is_reprint:
            lines.append(center("*** DUPLICATE / REPRINT ***"))
            lines.append(divider("-"))

        # 3. Cancellation Warning Banner
        if receipt.is_cancelled:
            lines.append(divider("*"))
            lines.append(center("*** BILL CANCELLED ***"))
            if receipt.cancellation_details and receipt.cancellation_details.cancelled_at:
                c_dt = receipt.cancellation_details.cancelled_at.strftime("%d/%m/%Y %I:%M %p")
                lines.append(center(f"Cancelled: {c_dt}"))
            if receipt.cancellation_details and receipt.cancellation_details.cancelled_by_user:
                lines.append(center(f"By: {receipt.cancellation_details.cancelled_by_user}"))
            if receipt.cancellation_details and receipt.cancellation_details.cancellation_reason:
                lines.append(center(f"Reason: {receipt.cancellation_details.cancellation_reason}"))
            lines.append(divider("*"))

        # 4. Bill Metadata
        dt_str = receipt.bill_date.strftime("%d/%m/%Y  %I:%M %p")
        lines.append(row("Bill No:", receipt.bill_number))
        lines.append(row("Date & Time:", dt_str))
        lines.append(row("Cashier:", receipt.cashier.full_name[:18]))

        if receipt.customer and receipt.customer.full_name:
            lines.append(row("Customer:", receipt.customer.full_name[:18]))
            if receipt.customer.phone_number:
                lines.append(row("Phone:", receipt.customer.phone_number))
        else:
            lines.append(row("Customer:", "Walk-in Retail"))

        # 5. Product Table Header
        lines.append(divider("-"))
        lines.append(row("Item", "Total"))
        lines.append(divider("-"))

        # 6. Items
        for item in receipt.items:
            # Item Name (wrapped if exceeds width)
            item_name = item.product_name
            for name_chunk in wrap_lines(item_name):
                lines.append(name_chunk)

            # Details: SKU / Variant
            details = []
            if item.sku:
                details.append(f"SKU:{item.sku}")
            if item.size:
                details.append(f"Size:{item.size}")
            if item.color:
                details.append(f"Col:{item.color}")

            if details:
                detail_str = " | ".join(details)
                for det_line in wrap_lines(f"  {detail_str}"):
                    lines.append(det_line)

            # Qty x Unit Price -> Line Total
            qty_calc = f"  {item.quantity} x {item.unit_price:.2f}"
            line_tot = f"{item.line_total:.2f}"
            lines.append(row(qty_calc, line_tot))

            # Item Discount if present
            if item.discount_amount > Decimal("0.00"):
                disc_str = f"  Item Disc: -{item.discount_amount:.2f}"
                lines.append(disc_str)

        lines.append(divider("-"))

        # 7. Price Summary
        lines.append(row("Subtotal:", f"Rs. {receipt.subtotal:.2f}"))

        if receipt.item_discount_total > Decimal("0.00"):
            lines.append(row("Item Discounts:", f"-Rs. {receipt.item_discount_total:.2f}"))

        if receipt.bill_discount_amount > Decimal("0.00"):
            lines.append(row("Bill Discount:", f"-Rs. {receipt.bill_discount_amount:.2f}"))

        if receipt.tax_amount > Decimal("0.00"):
            lines.append(row("Tax:", f"Rs. {receipt.tax_amount:.2f}"))

        lines.append(divider("-"))
        lines.append(row("GRAND TOTAL:", f"Rs. {receipt.grand_total:.2f}"))
        lines.append(divider("="))

        # 8. Payment Breakdown
        lines.append(row("PAYMENT STATUS:", receipt.payment_status if receipt.payment_status else "PAID"))
        lines.append(row("Payment Method:", receipt.payment_method))

        if receipt.payment_breakdown.confirmed_cash > Decimal("0.00"):
            lines.append(row("  Cash Paid:", f"Rs. {receipt.payment_breakdown.confirmed_cash:.2f}"))

        if receipt.payment_breakdown.confirmed_upi > Decimal("0.00"):
            lines.append(row("  UPI Paid:", f"Rs. {receipt.payment_breakdown.confirmed_upi:.2f}"))

        if receipt.payment_breakdown.has_pending_upi:
            lines.append(divider("-"))
            lines.append(center("*** UPI PAYMENT PENDING ***"))
            lines.append(row("Pending UPI:", f"Rs. {receipt.payment_breakdown.pending_upi:.2f}"))

        lines.append(divider("-"))
        lines.append(row("Amount Paid:", f"Rs. {receipt.amount_paid:.2f}"))
        lines.append(row("Balance Due:", f"Rs. {receipt.balance:.2f}"))

        # 10. Refund Review on Cancelled Bill
        if receipt.is_cancelled and receipt.cancellation_details and receipt.cancellation_details.refund_review_amount:
            if receipt.cancellation_details.refund_review_amount > Decimal("0.00"):
                lines.append(divider("-"))
                lines.append(row("Refund Review:", f"Rs. {receipt.cancellation_details.refund_review_amount:.2f}"))

        # 11. Footer
        lines.append(divider("="))
        if receipt.store.receipt_footer:
            for footer_line in wrap_lines(receipt.store.receipt_footer):
                lines.append(center(footer_line))
        lines.append(center("Visit again!"))
        lines.append(divider("="))

        # Feed lines for tear-off
        lines.append("\n\n")

        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # Clean 58mm HTML Preview & Native Print Template (SEZNIK Veer Optimized)
    # --------------------------------------------------------------------------
    @classmethod
    def generate_html_receipt(cls, receipt: ReceiptOut) -> str:
        """Generate high-contrast 58mm HTML receipt layout optimized for SEZNIK Veer thermal printing."""
        items_rows = []
        for it in receipt.items:
            variants = []
            if it.sku:
                variants.append(f"SKU: {it.sku}")
            if it.size:
                variants.append(f"Size: {it.size}")
            if it.color and it.color != "Standard":
                variants.append(f"Col: {it.color}")
            variant_badge = f"<div style='font-size: 11px; font-weight: normal; color: #000;'>{' | '.join(variants)}</div>" if variants else ""

            item_disc_html = ""
            if it.discount_amount > Decimal("0.00"):
                item_disc_html = f"<div style='font-size: 11px; font-weight: bold; color: #000;'>Item Disc: -â‚¹{it.discount_amount:.2f}</div>"

            items_rows.append(f"""
            <tr style="border-bottom: 1px dashed #000;">
                <td style="padding: 4px 0; text-align: left;">
                    <div style="font-weight: 800; font-size: 14px; color: #000;">{it.product_name}</div>
                    {variant_badge}
                    <div style="font-size: 12px; font-weight: 700; color: #000;">{it.quantity} &times; â‚¹{it.unit_price:.2f}</div>
                    {item_disc_html}
                </td>
                <td style="padding: 4px 0; text-align: right; vertical-align: bottom; font-weight: 800; font-size: 13px; color: #000;">
                    â‚¹{it.line_total:.2f}
                </td>
            </tr>
            """)

        items_tbody = "".join(items_rows)

        reprint_badge_html = (
            "<div style='border: 2px solid #000; padding: 4px; margin: 6px 0; font-weight: 800; font-size: 12px; text-align: center; letter-spacing: 1px; color: #000;'>*** DUPLICATE / REPRINT ***</div>"
            if receipt.is_reprint
            else ""
        )

        cancellation_html = ""
        if receipt.is_cancelled:
            c_dt = (
                receipt.cancellation_details.cancelled_at.strftime("%d/%m/%Y %I:%M %p")
                if receipt.cancellation_details and receipt.cancellation_details.cancelled_at
                else ""
            )
            c_by = (
                receipt.cancellation_details.cancelled_by_user
                if receipt.cancellation_details and receipt.cancellation_details.cancelled_by_user
                else "Owner"
            )
            c_rs = (
                receipt.cancellation_details.cancellation_reason
                if receipt.cancellation_details and receipt.cancellation_details.cancellation_reason
                else "No reason provided"
            )
            cancellation_html = f"""
            <div style="border: 2px dashed #000; color: #000; padding: 6px; margin: 8px 0; font-size: 12px; text-align: center;">
                <div style="font-weight: 800; font-size: 14px;">*** BILL CANCELLED ***</div>
                <div>At: {c_dt}</div>
                <div>By: {c_by}</div>
                <div>Reason: {c_rs}</div>
            </div>
            """

        pending_upi_html = ""
        if receipt.payment_breakdown and receipt.payment_breakdown.has_pending_upi:
            pending_upi_html = f"""
            <div style="border: 2px dashed #000000; color: #000000; padding: 4px; margin: 6px 0; font-size: 11px; text-align: center;">
                <div style="font-weight: 800; font-size: 12px; letter-spacing: 0.5px;">*** UPI PAYMENT PENDING ***</div>
                <div style="font-weight: 700;">Amount: â‚¹{receipt.payment_breakdown.pending_upi:.2f}</div>
            </div>
            """

        refund_review_html = ""
        if receipt.is_cancelled and receipt.cancellation_details and receipt.cancellation_details.refund_review_amount:
            if receipt.cancellation_details.refund_review_amount > Decimal("0.00"):
                refund_review_html = f"""
                <tr style="color: #000; font-weight: 800;">
                    <td style="padding: 2px 0;">Refund Review:</td>
                    <td style="text-align: right; padding: 2px 0;">â‚¹{receipt.cancellation_details.refund_review_amount:.2f}</td>
                </tr>
                """

        customer_line = (
            f"<div><strong>Customer:</strong> {receipt.customer.full_name}</div>"
            if receipt.customer and receipt.customer.full_name
            else "<div><strong>Customer:</strong> Walk-in Retail</div>"
        )
        if receipt.customer and receipt.customer.phone_number:
            customer_line += f"<div><strong>Phone:</strong> {receipt.customer.phone_number}</div>"

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Receipt - {receipt.bill_number}</title>
<style>
  @page {{
    size: 58mm auto;
    margin: 0;
  }}
  @media print {{
    body {{
      margin: 0;
      padding: 0 1mm 4mm 1mm;
      background: white !important;
    }}
    .no-print {{
      display: none !important;
    }}
  }}
  body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 12px;
    line-height: 1.25;
    color: #000000;
    background: #ffffff;
    margin: 0 auto;
    padding: 0 1mm 4mm 1mm;
    max-width: 58mm;
    box-sizing: border-box;
  }}
  .center {{ text-align: center; }}
  .right {{ text-align: right; }}
  .bold {{ font-weight: 800; }}
  .divider {{ border-top: 1px dashed #000000; margin: 4px 0; }}
  .double-divider {{ border-top: 2px solid #000000; margin: 4px 0; }}
  table {{ width: 100%; border-collapse: collapse; }}
</style>
</head>
<body>
  <div class="center bold" style="font-size: 21px; letter-spacing: 1px; color: #000000;">{receipt.store.store_name}</div>
  <div class="center bold" style="font-size: 13px; color: #000000;">{receipt.store.tagline}</div>
  <div class="center" style="font-size: 11px; margin-top: 2px; color: #000000;">{receipt.store.address}</div>
  <div class="center bold" style="font-size: 12px; color: #000000;">Phone: {receipt.store.phone}</div>
  {f'<div class="center bold" style="font-size: 11px; color: #000000;">GSTIN: {receipt.store.gstin}</div>' if receipt.store.gstin else ''}

  <div class="double-divider"></div>

  {reprint_badge_html}
  {cancellation_html}
  {pending_upi_html}

  <div style="font-size: 12px; color: #000000; line-height: 1.3;">
    <div><strong>Bill No:</strong> {receipt.bill_number}</div>
    <div><strong>Date:</strong> {receipt.bill_date.strftime("%d/%m/%Y %I:%M %p")}</div>
    <div><strong>Cashier:</strong> {receipt.cashier.full_name}</div>
    {customer_line}
  </div>

  <div class="divider"></div>

  <table>
    <thead>
      <tr style="border-bottom: 2px solid #000000; font-size: 12px; font-weight: 800; color: #000000;">
        <th style="text-align: left; padding-bottom: 2px;">ITEM</th>
        <th style="text-align: right; padding-bottom: 2px;">TOTAL</th>
      </tr>
    </thead>
    <tbody>
      {items_tbody}
    </tbody>
  </table>

  <div class="divider"></div>

  <table style="font-size: 12px; font-weight: 700; color: #000000;">
    <tr>
      <td style="padding: 2px 0;">Subtotal:</td>
      <td style="text-align: right; padding: 2px 0; font-weight: 800;">â‚¹{receipt.subtotal:.2f}</td>
    </tr>
    {f'<tr><td style="padding: 2px 0;">Item Discounts:</td><td style="text-align: right; padding: 2px 0; font-weight: 800;">-â‚¹{receipt.item_discount_total:.2f}</td></tr>' if receipt.item_discount_total > Decimal("0.00") else ''}
    {f'<tr><td style="padding: 2px 0;">Bill Discount:</td><td style="text-align: right; padding: 2px 0; font-weight: 800;">-â‚¹{receipt.bill_discount_amount:.2f}</td></tr>' if receipt.bill_discount_amount > Decimal("0.00") else ''}
    {f'<tr><td style="padding: 2px 0;">Tax:</td><td style="text-align: right; padding: 2px 0; font-weight: 800;">â‚¹{receipt.tax_amount:.2f}</td></tr>' if receipt.tax_amount > Decimal("0.00") else ''}
    <tr class="bold" style="font-size: 16px; border-top: 2px solid #000000; border-bottom: 2px solid #000000;">
      <td style="padding: 4px 0;">GRAND TOTAL:</td>
      <td style="text-align: right; padding: 4px 0; font-size: 18px; font-weight: 900;">â‚¹{receipt.grand_total:.2f}</td>
    </tr>
  </table>

  <div class="double-divider"></div>

  <table style="font-size: 12px; color: #000000;">
    <tr class="bold">
      <td style="padding: 2px 0;">Amount Paid:</td>
      <td style="text-align: right; padding: 2px 0; font-weight: 800;">â‚¹{receipt.amount_paid:.2f}</td>
    </tr>
    {f'<tr class="bold"><td style="padding: 2px 0;">Balance Due:</td><td style="text-align: right; padding: 2px 0; font-weight: 800;">â‚¹{receipt.balance:.2f}</td></tr>' if receipt.balance > Decimal("0.00") else ''}
    <tr class="bold">
      <td style="padding: 2px 0;">Payment Method:</td>
      <td style="text-align: right; padding: 2px 0;">{receipt.payment_method}</td>
    </tr>
    <tr class="bold">
      <td style="padding: 2px 0;">PAYMENT STATUS:</td>
      <td style="text-align: right; padding: 2px 0;">{receipt.payment_status}</td>
    </tr>
    {f'<tr><td style="padding: 2px 0; padding-left: 8px; font-weight: 700;">- Cash Paid:</td><td style="text-align: right; padding: 2px 0; font-weight: 800;">â‚¹{receipt.payment_breakdown.confirmed_cash:.2f}</td></tr>' if receipt.payment_breakdown.confirmed_cash > Decimal("0.00") else ''}
    {f'<tr><td style="padding: 2px 0; padding-left: 8px; font-weight: 700;">- UPI Paid:</td><td style="text-align: right; padding: 2px 0; font-weight: 800;">â‚¹{receipt.payment_breakdown.confirmed_upi:.2f}</td></tr>' if receipt.payment_breakdown.confirmed_upi > Decimal("0.00") else ''}
    {refund_review_html}
  </table>

  <div class="double-divider"></div>

  <div class="center bold" style="font-size: 12px; margin-top: 4px; color: #000000;">{receipt.store.receipt_footer}</div>
  <div class="center" style="font-size: 11px; margin-top: 2px; color: #000000;">Goods once sold can be exchanged within 7 days with original receipt.</div>
  <div class="center bold" style="font-size: 12px; margin-top: 2px; color: #000000;">*** HAVE A GREAT DAY ***</div>
  <div class="double-divider"></div>
</body>
</html>"""
        return html

    # --------------------------------------------------------------------------
    # 58mm Continuous Thermal Receipt PDF Generator (SEZNIK Veer 58mm Optimized)
    # --------------------------------------------------------------------------
    @classmethod
    def generate_receipt_pdf(cls, receipt: ReceiptOut) -> bytes:
        """Generate a single-page continuous 58mm thermal receipt PDF with dynamic height.

        Tailored for SEZNIK Veer 58mm portable Bluetooth thermal receipt printer.
        Implements high-contrast, large-typography thermal styling with solid black rendering
        and zero blank whitespace at the top.
        """
        from io import BytesIO
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        page_width = 58 * mm
        margin = 2.0 * mm
        content_width = page_width - (2 * margin)

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "PDFReceiptTitle",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            alignment=1,  # Center
            textColor=colors.black,
        )
        tagline_style = ParagraphStyle(
            "PDFReceiptTagline",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            alignment=1,
            textColor=colors.black,
        )
        address_style = ParagraphStyle(
            "PDFReceiptAddress",
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            alignment=1,
            textColor=colors.black,
        )
        phone_style = ParagraphStyle(
            "PDFReceiptPhone",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            alignment=1,
            textColor=colors.black,
        )
        gstin_style = ParagraphStyle(
            "PDFReceiptGSTIN",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            alignment=1,
            textColor=colors.black,
        )
        badge_style = ParagraphStyle(
            "PDFReceiptBadge",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            alignment=1,
            textColor=colors.black,
        )
        header_left = ParagraphStyle(
            "PDFHeaderLeft",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11.5,
            alignment=0,
            textColor=colors.black,
        )
        header_right = ParagraphStyle(
            "PDFHeaderRight",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11.5,
            alignment=2,
            textColor=colors.black,
        )
        item_title = ParagraphStyle(
            "PDFItemTitle",
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=12.5,
            alignment=0,  # Left
            textColor=colors.black,
        )
        item_sub = ParagraphStyle(
            "PDFItemSub",
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            alignment=0,
            textColor=colors.black,
        )
        calc_left = ParagraphStyle(
            "PDFCalcLeft",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=0,  # Left
            textColor=colors.black,
        )
        item_total_style = ParagraphStyle(
            "PDFItemTotal",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=2,  # Right
            textColor=colors.black,
        )
        item_disc_style = ParagraphStyle(
            "PDFItemDisc",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
            alignment=0,
            textColor=colors.black,
        )
        meta_left = ParagraphStyle(
            "PDFLeftMeta",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=0,
            textColor=colors.black,
        )
        meta_right = ParagraphStyle(
            "PDFRightMeta",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=2,  # Right
            textColor=colors.black,
        )
        subtotal_lbl = ParagraphStyle(
            "PDFSubtotalLbl",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            alignment=0,
            textColor=colors.black,
        )
        subtotal_val = ParagraphStyle(
            "PDFSubtotalVal",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=2,
            textColor=colors.black,
        )
        grand_total_style = ParagraphStyle(
            "PDFGrandTot",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14.5,
            alignment=2,
            textColor=colors.black,
        )
        grand_total_label = ParagraphStyle(
            "PDFGrandLbl",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13.5,
            alignment=0,
            textColor=colors.black,
        )
        pay_lbl = ParagraphStyle(
            "PDFPayLbl",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            alignment=0,
            textColor=colors.black,
        )
        pay_val = ParagraphStyle(
            "PDFPayVal",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=2,
            textColor=colors.black,
        )
        pay_sub = ParagraphStyle(
            "PDFPaySub",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
            alignment=0,
            textColor=colors.black,
        )
        pay_sub_val = ParagraphStyle(
            "PDFPaySubVal",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
            alignment=2,
            textColor=colors.black,
        )
        footer_bold = ParagraphStyle(
            "PDFFooterBold",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11.5,
            alignment=1,
            textColor=colors.black,
        )
        footer_normal = ParagraphStyle(
            "PDFFooterNormal",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=1,
            textColor=colors.black,
        )

        def esc(val: Optional[str]) -> str:
            """Safely escape dynamic user strings for ReportLab Paragraph XML parsing."""
            if val is None:
                return ""
            return html.escape(str(val), quote=False)

        def build_story():
            story = []

            # 1. Store Header
            story.append(Paragraph(esc(receipt.store.store_name), title_style))
            if receipt.store.tagline:
                story.append(Paragraph(esc(receipt.store.tagline), tagline_style))
            story.append(Paragraph(esc(receipt.store.address), address_style))
            story.append(Paragraph(f"Phone: {esc(receipt.store.phone)}", phone_style))
            if receipt.store.gstin:
                story.append(Paragraph(f"GSTIN: {esc(receipt.store.gstin)}", gstin_style))

            if receipt.is_reprint:
                story.append(Spacer(1, 1.5 * mm))
                story.append(Paragraph("*** DUPLICATE / REPRINT ***", badge_style))

            if receipt.is_cancelled:
                story.append(Spacer(1, 1.5 * mm))
                story.append(Paragraph("*** BILL CANCELLED ***", badge_style))
                if receipt.cancellation_details:
                    if receipt.cancellation_details.cancelled_at:
                        c_dt = receipt.cancellation_details.cancelled_at.strftime("%d/%m/%Y %I:%M %p")
                        story.append(Paragraph(f"At: {c_dt}", address_style))
                    if receipt.cancellation_details.cancelled_by_user:
                        story.append(Paragraph(f"By: {esc(receipt.cancellation_details.cancelled_by_user)}", address_style))
                    if receipt.cancellation_details.cancellation_reason:
                        story.append(Paragraph(f"Reason: {esc(receipt.cancellation_details.cancellation_reason)}", address_style))

            if receipt.payment_breakdown and receipt.payment_breakdown.has_pending_upi:
                story.append(Spacer(1, 1.5 * mm))
                story.append(Paragraph("*** UPI PAYMENT PENDING ***", badge_style))
                story.append(Paragraph(f"Pending UPI: Rs. {receipt.payment_breakdown.pending_upi:.2f}", address_style))

            # Divider
            story.append(Spacer(1, 1 * mm))
            story.append(HRFlowable(width="100%", thickness=1.0, color=colors.black, spaceAfter=2, spaceBefore=2, hAlign="CENTER"))

            # 2. Bill Meta
            dt_str = receipt.bill_date.strftime("%d/%m/%Y %I:%M %p")
            meta_rows = [
                [Paragraph("Bill No:", meta_left), Paragraph(esc(receipt.bill_number), meta_right)],
                [Paragraph("Date:", meta_left), Paragraph(dt_str, meta_right)],
                [Paragraph("Cashier:", meta_left), Paragraph(esc(receipt.cashier.full_name), meta_right)],
            ]
            if receipt.customer and receipt.customer.full_name:
                meta_rows.append([Paragraph("Customer:", meta_left), Paragraph(esc(receipt.customer.full_name), meta_right)])
                if receipt.customer.phone_number:
                    meta_rows.append([Paragraph("Phone:", meta_left), Paragraph(esc(receipt.customer.phone_number), meta_right)])
            else:
                meta_rows.append([Paragraph("Customer:", meta_left), Paragraph("Walk-in Retail", meta_right)])

            meta_table = Table(meta_rows, colWidths=[18 * mm, content_width - (18 * mm)])
            meta_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(meta_table)

            story.append(HRFlowable(width="100%", thickness=1.0, color=colors.black, spaceAfter=2, spaceBefore=2, hAlign="CENTER"))

            # 3. Items Header
            header_table = Table(
                [[Paragraph("ITEM", header_left), Paragraph("TOTAL", header_right)]],
                colWidths=[content_width * 0.65, content_width * 0.35]
            )
            header_table.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, -1), 1.0, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(header_table)

            # 4. Items List
            item_rows = []
            item_table_styles = [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
            curr_row = 0
            for it in receipt.items:
                item_rows.append([Paragraph(esc(it.product_name), item_title), ""])
                item_table_styles.append(("SPAN", (0, curr_row), (1, curr_row)))
                curr_row += 1

                var_parts = []
                if it.size:
                    var_parts.append(f"Size: {esc(it.size)}")
                if it.sku:
                    var_parts.append(f"({esc(it.sku)})")
                if it.color and it.color != "Standard":
                    var_parts.append(f"{esc(it.color)}")
                if var_parts:
                    var_desc = " ".join(var_parts)
                    item_rows.append([Paragraph(var_desc, item_sub), ""])
                    item_table_styles.append(("SPAN", (0, curr_row), (1, curr_row)))
                    curr_row += 1

                calc_str = f"{it.quantity} Ã— Rs. {it.unit_price:.2f}"
                tot_str = f"Rs. {it.line_total:.2f}"
                item_rows.append([
                    Paragraph(calc_str, calc_left),
                    Paragraph(tot_str, item_total_style)
                ])
                curr_row += 1

                if it.discount_amount and it.discount_amount > Decimal("0.00"):
                    item_rows.append([
                        Paragraph(f"Item Disc: -Rs. {it.discount_amount:.2f}", item_disc_style),
                        ""
                    ])
                    item_table_styles.append(("SPAN", (0, curr_row), (1, curr_row)))
                    curr_row += 1

            items_table = Table(
                item_rows,
                colWidths=[content_width * 0.65, content_width * 0.35]
            )
            items_table.setStyle(TableStyle(item_table_styles))
            story.append(items_table)

            story.append(HRFlowable(width="100%", thickness=1.0, color=colors.black, spaceAfter=2, spaceBefore=2, hAlign="CENTER"))

            # 5. Financial Totals
            tot_rows = [
                [Paragraph("Subtotal:", subtotal_lbl), Paragraph(f"Rs. {receipt.subtotal:.2f}", subtotal_val)],
            ]
            if receipt.item_discount_total and receipt.item_discount_total > Decimal("0.00"):
                tot_rows.append([Paragraph("Item Discounts:", subtotal_lbl), Paragraph(f"-Rs. {receipt.item_discount_total:.2f}", subtotal_val)])
            if receipt.bill_discount_amount and receipt.bill_discount_amount > Decimal("0.00"):
                tot_rows.append([Paragraph("Bill Discount:", subtotal_lbl), Paragraph(f"-Rs. {receipt.bill_discount_amount:.2f}", subtotal_val)])
            if receipt.tax_amount and receipt.tax_amount > Decimal("0.00"):
                tot_rows.append([Paragraph("GST:", subtotal_lbl), Paragraph(f"Rs. {receipt.tax_amount:.2f}", subtotal_val)])

            tot_rows.append([Paragraph("GRAND TOTAL:", grand_total_label), Paragraph(f"Rs. {receipt.grand_total:.2f}", grand_total_style)])

            totals_table = Table(tot_rows, colWidths=[content_width * 0.57, content_width * 0.43])
            totals_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEABOVE", (0, -1), (-1, -1), 1.5, colors.black),
                ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.black),
            ]))
            story.append(totals_table)

            story.append(HRFlowable(width="100%", thickness=1.0, color=colors.black, spaceAfter=2, spaceBefore=2, hAlign="CENTER"))

            # 6. Payment Breakdown
            pay_rows = [
                [Paragraph("Amount Paid:", pay_lbl), Paragraph(f"Rs. {receipt.amount_paid:.2f}", pay_val)],
            ]
            if receipt.balance and receipt.balance > Decimal("0.00"):
                pay_rows.append([Paragraph("Balance Due:", pay_lbl), Paragraph(f"Rs. {receipt.balance:.2f}", pay_val)])
            pay_rows.append([Paragraph("Payment Method:", pay_lbl), Paragraph(esc(receipt.payment_method), pay_val)])
            pay_rows.append([Paragraph("Payment Status:", pay_lbl), Paragraph(esc(receipt.payment_status or "PAID"), pay_val)])

            if receipt.payment_breakdown:
                if receipt.payment_breakdown.confirmed_cash > Decimal("0.00") and receipt.payment_breakdown.confirmed_upi > Decimal("0.00"):
                    pay_rows.append([
                        Paragraph("- Cash Paid:", pay_sub),
                        Paragraph(f"Rs. {receipt.payment_breakdown.confirmed_cash:.2f}", pay_sub_val)
                    ])
                    pay_rows.append([
                        Paragraph("- UPI Paid:", pay_sub),
                        Paragraph(f"Rs. {receipt.payment_breakdown.confirmed_upi:.2f}", pay_sub_val)
                    ])
                elif receipt.payment_breakdown.payments and len(receipt.payment_breakdown.payments) > 1:
                    for p in receipt.payment_breakdown.payments:
                        pay_rows.append([
                            Paragraph(f"- {esc(p.payment_method)} Paid:", pay_sub),
                            Paragraph(f"Rs. {p.amount:.2f}", pay_sub_val)
                        ])

            if receipt.is_cancelled and receipt.cancellation_details and receipt.cancellation_details.refund_review_amount:
                if receipt.cancellation_details.refund_review_amount > Decimal("0.00"):
                    pay_rows.append([
                        Paragraph("Refund Review:", pay_lbl),
                        Paragraph(f"Rs. {receipt.cancellation_details.refund_review_amount:.2f}", pay_val)
                    ])

            pay_table = Table(pay_rows, colWidths=[content_width * 0.54, content_width * 0.46])
            pay_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(pay_table)

            story.append(HRFlowable(width="100%", thickness=1.0, color=colors.black, spaceAfter=2, spaceBefore=2, hAlign="CENTER"))

            # 7. Footer
            story.append(Spacer(1, 1 * mm))
            if receipt.store.receipt_footer:
                story.append(Paragraph(esc(receipt.store.receipt_footer), footer_bold))
            story.append(Paragraph("Goods once sold can be exchanged within 7 days with original receipt.", footer_normal))
            story.append(Paragraph("*** HAVE A GREAT DAY ***", footer_bold))

            return story

        # Pass 1: Measure exact height required
        dummy_height = 10000 * mm
        class MeasuringDoc(SimpleDocTemplate):
            def afterFlowable(self, flowable):
                super().afterFlowable(flowable)
                self.used_y = self.frame._y

        doc_measure = MeasuringDoc(
            BytesIO(),
            pagesize=(page_width, dummy_height),
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
        )
        doc_measure.build(build_story())
        exact_height = dummy_height - doc_measure.used_y + (2 * margin) + (2 * mm)

        # Pass 2: Build single-page continuous PDF
        pdf_buf = BytesIO()
        doc = SimpleDocTemplate(
            pdf_buf,
            pagesize=(page_width, exact_height),
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin,
        )
        doc.build(build_story())
        return pdf_buf.getvalue()
