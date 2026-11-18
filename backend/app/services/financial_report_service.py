"""Financial reporting service for daily sales summaries, P&L statements, overview, and PDF/Excel exports."""

import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_, or_, desc, asc, text
from sqlalchemy.orm import Session, joinedload

from app.models.bill import Bill, BillItem
from app.models.payment import Payment
from app.models.expense import Expense
from app.models.product import Product
from app.models.customer import Customer
from app.models.cash_register import DailyCashRegister, CashMovement
from app.schemas.finance import (
    DailySalesSummaryOut,
    CashFlowSummaryOut,
    ProfitLossReportOut,
    FinancialOverviewOut,
    SalesReportOut,
    SalesBillItemOut,
    ExpenseReportOut,
    ExpenseCategorySummary,
    ExpenseOut,
)
from app.services.expense_service import ExpenseService

STORE_TZ = ZoneInfo("Asia/Kolkata")

STORE_NAME = "VIYON"
STORE_TAGLINE = "MEN'S | KID'S WEAR"
STORE_ADDRESS = "F6WR+R8W, South Rangasamuthram, North Rangasamuthram, Sathyamangalam, Tamil Nadu 638402"
STORE_PHONE = "082702 42681"


class FinancialReportService:
    """Service generating real-time financial summaries, P&L statements, and exports."""

    @classmethod
    def resolve_date_range(
        cls,
        preset: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Tuple[date, date, str]:
        """Convert a period preset ('today', 'yesterday', 'this_week', etc.) into start/end dates in Asia/Kolkata."""
        today = datetime.now(STORE_TZ).date()

        preset_clean = (preset or "today").strip().lower()

        if preset_clean == "today":
            return today, today, "today"
        elif preset_clean == "yesterday":
            y = today - timedelta(days=1)
            return y, y, "yesterday"
        elif preset_clean == "this_week":
            # Monday is index 0
            start_wk = today - timedelta(days=today.weekday())
            return start_wk, today, "this_week"
        elif preset_clean == "this_month":
            start_mo = today.replace(day=1)
            return start_mo, today, "this_month"
        elif preset_clean == "previous_month":
            # First day of this month minus 1 day = last day of previous month
            first_this_mo = today.replace(day=1)
            last_prev_mo = first_this_mo - timedelta(days=1)
            first_prev_mo = last_prev_mo.replace(day=1)
            return first_prev_mo, last_prev_mo, "previous_month"
        elif preset_clean == "custom":
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date and end_date are required for 'custom' period preset.",
                )
            if start_date > end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="start_date cannot be after end_date.",
                )
            return start_date, end_date, "custom"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown period preset '{preset}'. Allowed: today, yesterday, this_week, this_month, previous_month, custom",
            )

    @staticmethod
    def get_datetime_bounds(start_d: date, end_d: date) -> Tuple[datetime, datetime]:
        """Convert start/end dates to timezone-aware UTC datetime bounds."""
        start_dt = datetime.combine(start_d, datetime.min.time(), tzinfo=STORE_TZ)
        end_dt = datetime.combine(end_d, datetime.max.time(), tzinfo=STORE_TZ)
        return start_dt, end_dt

    @classmethod
    def get_daily_sales_summary(
        cls,
        db: Session,
        business_date: Optional[date] = None,
    ) -> DailySalesSummaryOut:
        """Calculate complete daily sales summary adhering to all strict financial isolation rules."""
        target_date = business_date or datetime.now(STORE_TZ).date()
        start_dt, end_dt = cls.get_datetime_bounds(target_date, target_date)

        # 1. Bills counts
        total_bills_stmt = select(func.count(Bill.id)).where(
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
        )
        total_bills = db.scalar(total_bills_stmt) or 0

        completed_bills_stmt = select(func.count(Bill.id)).where(
            Bill.bill_status == "COMPLETED",
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
        )
        completed_bills_count = db.scalar(completed_bills_stmt) or 0

        cancelled_bills_stmt = select(func.count(Bill.id)).where(
            Bill.bill_status == "CANCELLED",
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
        )
        cancelled_bills_count = db.scalar(cancelled_bills_stmt) or 0

        # 2. Aggregations across COMPLETED bills only (exclude cancelled bills)
        sales_agg_stmt = select(
            func.coalesce(func.sum(Bill.subtotal), Decimal("0.00")).label("gross_sales"),
            func.coalesce(func.sum(Bill.discount_amount), Decimal("0.00")).label("bill_discounts"),
            func.coalesce(func.sum(Bill.tax_amount), Decimal("0.00")).label("total_tax"),
            func.coalesce(func.sum(Bill.total_amount), Decimal("0.00")).label("net_sales"),
            func.coalesce(func.sum(Bill.balance_amount), Decimal("0.00")).label("outstanding_balance"),
        ).where(
            Bill.bill_status == "COMPLETED",
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
        )
        row = db.execute(sales_agg_stmt).one()
        gross_sales = row.gross_sales
        bill_discounts = row.bill_discounts
        total_tax = row.total_tax
        net_sales = row.net_sales
        outstanding_customer_balance = row.outstanding_balance

        # Item-level discounts on completed bills
        item_discount_stmt = (
            select(func.coalesce(func.sum(BillItem.discount_amount), Decimal("0.00")))
            .join(Bill, Bill.id == BillItem.bill_id)
            .where(
                Bill.bill_status == "COMPLETED",
                Bill.created_at >= start_dt,
                Bill.created_at <= end_dt,
            )
        )
        item_discounts = db.scalar(item_discount_stmt) or Decimal("0.00")
        total_discounts = item_discounts + bill_discounts

        # 3. Confirmed Collections (Cash & UPI from completed bills)
        cash_coll_stmt = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_method == "CASH",
                Payment.payment_status == "CONFIRMED",
                Bill.bill_status != "CANCELLED",
                Payment.received_at >= start_dt,
                Payment.received_at <= end_dt,
            )
        )
        confirmed_cash = db.scalar(cash_coll_stmt) or Decimal("0.00")

        upi_coll_stmt = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_method == "UPI",
                Payment.payment_status == "CONFIRMED",
                Bill.bill_status != "CANCELLED",
                Payment.received_at >= start_dt,
                Payment.received_at <= end_dt,
            )
        )
        confirmed_upi = db.scalar(upi_coll_stmt) or Decimal("0.00")
        total_confirmed = confirmed_cash + confirmed_upi

        # 4. Pending UPI Payments (Shown separately, NEVER counted in revenue/collections)
        pending_upi_stmt = (
            select(
                func.coalesce(func.sum(Payment.amount), Decimal("0.00")),
                func.count(Payment.id),
            )
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_method == "UPI",
                Payment.payment_status == "PENDING",
                Bill.bill_status != "CANCELLED",
                Payment.created_at >= start_dt,
                Payment.created_at <= end_dt,
            )
        )
        pending_upi_row = db.execute(pending_upi_stmt).one()
        pending_upi_amount = pending_upi_row[0]
        pending_upi_count = pending_upi_row[1]

        # 5. Rejected Payments (Excluded from revenue)
        rejected_stmt = (
            select(
                func.coalesce(func.sum(Payment.amount), Decimal("0.00")),
                func.count(Payment.id),
            )
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_status.in_(["FAILED", "REJECTED"]),
                Bill.bill_status != "CANCELLED",
                Payment.created_at >= start_dt,
                Payment.created_at <= end_dt,
            )
        )
        rejected_row = db.execute(rejected_stmt).one()
        rejected_amount = rejected_row[0]
        rejected_count = rejected_row[1]

        return DailySalesSummaryOut(
            business_date=target_date,
            total_bills=total_bills,
            completed_bills_count=completed_bills_count,
            cancelled_bills_count=cancelled_bills_count,
            gross_sales=gross_sales,
            total_item_discounts=item_discounts,
            total_bill_discounts=bill_discounts,
            total_discounts=total_discounts,
            net_sales=net_sales,
            total_tax=total_tax,
            confirmed_cash_collections=confirmed_cash,
            confirmed_upi_collections=confirmed_upi,
            total_confirmed_collections=total_confirmed,
            pending_upi_amount=pending_upi_amount,
            pending_upi_count=pending_upi_count,
            rejected_payment_amount=rejected_amount,
            rejected_payment_count=rejected_count,
            outstanding_customer_balance=outstanding_customer_balance,
        )

    @classmethod
    def get_profit_loss(
        cls,
        db: Session,
        start_date: date,
        end_date: date,
        preset: Optional[str] = None,
    ) -> ProfitLossReportOut:
        """Calculate Gross and Net Operating Profit with strict COGS verification."""
        start_dt, end_dt = cls.get_datetime_bounds(start_date, end_date)

        # 1. Revenue (Net sales from non-cancelled bills)
        revenue_stmt = select(func.coalesce(func.sum(Bill.total_amount), Decimal("0.00"))).where(
            Bill.bill_status == "COMPLETED",
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
        )
        revenue = db.scalar(revenue_stmt) or Decimal("0.00")

        # 2. Inspect sold items and their catalogue cost_price
        items_stmt = (
            select(BillItem)
            .join(Bill, Bill.id == BillItem.bill_id)
            .options(joinedload(BillItem.product))
            .where(
                Bill.bill_status == "COMPLETED",
                Bill.created_at >= start_dt,
                Bill.created_at <= end_dt,
            )
        )
        items = db.execute(items_stmt).scalars().all()

        total_items_sold = len(items)
        items_with_cost = 0
        items_missing_cost = 0
        total_cogs = Decimal("0.00")

        for item in items:
            product = item.product
            if product is not None and product.cost_price is not None:
                items_with_cost += 1
                total_cogs += item.quantity * product.cost_price
            else:
                items_missing_cost += 1

        # Determine COGS and Profit availability
        if total_items_sold == 0:
            cogs_status = "COMPLETE"
            profit_status = "AVAILABLE"
            cogs = Decimal("0.00")
            gross_profit = Decimal("0.00")
            explanation = "No sales recorded in the selected period."
        elif items_missing_cost == 0:
            cogs_status = "COMPLETE"
            profit_status = "AVAILABLE"
            cogs = total_cogs
            gross_profit = revenue - cogs
            explanation = "All sold products have verified purchase cost prices in catalogue."
        elif items_with_cost > 0:
            cogs_status = "PARTIAL"
            profit_status = "PARTIAL"
            cogs = total_cogs
            gross_profit = revenue - cogs
            explanation = (
                f"{items_missing_cost} of {total_items_sold} sold item(s) lack cost_price in the product catalogue. "
                "COGS and Profit figures are partial and strictly indicative."
            )
        else:
            cogs_status = "UNAVAILABLE"
            profit_status = "UNAVAILABLE"
            cogs = None
            gross_profit = None
            explanation = (
                "None of the sold products have cost_price configured in the catalogue. "
                "Profit calculation is unavailable to prevent misleading financial figures."
            )

        # 3. Operating Expenses (Active, non-voided)
        expenses_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
            Expense.is_voided == False,
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
        )
        operating_expenses = db.scalar(expenses_stmt) or Decimal("0.00")

        # 4. Net Operating Profit = Gross Profit - Operating Expenses
        if gross_profit is not None:
            net_operating_profit = gross_profit - operating_expenses
        else:
            net_operating_profit = None

        # Margins
        gross_margin = None
        if revenue > Decimal("0.00") and gross_profit is not None:
            gross_margin = (gross_profit / revenue * Decimal("100")).quantize(Decimal("0.01"))

        net_margin = None
        if revenue > Decimal("0.00") and net_operating_profit is not None:
            net_margin = (net_operating_profit / revenue * Decimal("100")).quantize(Decimal("0.01"))

        return ProfitLossReportOut(
            period_start=start_date,
            period_end=end_date,
            preset=preset,
            revenue=revenue,
            cogs=cogs,
            cogs_status=cogs_status,
            gross_profit=gross_profit,
            gross_profit_margin_pct=gross_margin,
            operating_expenses=operating_expenses,
            net_operating_profit=net_operating_profit,
            net_profit_margin_pct=net_margin,
            profit_status=profit_status,
            explanation_note=explanation,
            items_sold_count=total_items_sold,
            items_with_cost_count=items_with_cost,
            items_missing_cost_count=items_missing_cost,
        )

    @classmethod
    def get_financial_overview(
        cls,
        db: Session,
        preset: str = "today",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverviewOut:
        """Top-level executive summary cards for dashboard."""
        p_start, p_end, resolved_preset = cls.resolve_date_range(preset, start_date, end_date)
        start_dt, end_dt = cls.get_datetime_bounds(p_start, p_end)

        # Sales & Collections
        completed_stmt = select(
            func.coalesce(func.sum(Bill.total_amount), Decimal("0.00")).label("net_sales"),
            func.count(Bill.id).label("completed_cnt"),
        ).where(
            Bill.bill_status == "COMPLETED",
            Bill.created_at >= start_dt,
            Bill.created_at <= end_dt,
        )
        sales_row = db.execute(completed_stmt).one()
        net_sales = sales_row.net_sales
        completed_cnt = sales_row.completed_cnt

        cancelled_cnt = (
            db.scalar(
                select(func.count(Bill.id)).where(
                    Bill.bill_status == "CANCELLED",
                    Bill.created_at >= start_dt,
                    Bill.created_at <= end_dt,
                )
            )
            or 0
        )

        # Cash & UPI Collections
        cash_stmt = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_method == "CASH",
                Payment.payment_status == "CONFIRMED",
                Bill.bill_status != "CANCELLED",
                Payment.received_at >= start_dt,
                Payment.received_at <= end_dt,
            )
        )
        cash_collections = db.scalar(cash_stmt) or Decimal("0.00")

        upi_stmt = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_method == "UPI",
                Payment.payment_status == "CONFIRMED",
                Bill.bill_status != "CANCELLED",
                Payment.received_at >= start_dt,
                Payment.received_at <= end_dt,
            )
        )
        upi_collections = db.scalar(upi_stmt) or Decimal("0.00")
        total_confirmed = cash_collections + upi_collections

        pending_upi_stmt = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_method == "UPI",
                Payment.payment_status == "PENDING",
                Bill.bill_status != "CANCELLED",
                Payment.created_at >= start_dt,
                Payment.created_at <= end_dt,
            )
        )
        pending_upi = db.scalar(pending_upi_stmt) or Decimal("0.00")

        # Operating Expenses
        exp_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
            Expense.is_voided == False,
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
        )
        total_operating_expenses = db.scalar(exp_stmt) or Decimal("0.00")

        # Cash Flow (Confirmed Cash collections minus active Cash expenses)
        cash_exp_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
            Expense.payment_method == "CASH",
            Expense.is_voided == False,
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
        )
        cash_expenses = db.scalar(cash_exp_stmt) or Decimal("0.00")
        net_cash_flow = cash_collections - cash_expenses

        # P&L Report
        p_l = cls.get_profit_loss(db, p_start, p_end, resolved_preset)

        # Check today's register status
        today_reg = (
            db.execute(
                select(DailyCashRegister).where(DailyCashRegister.business_date == p_end)
            )
            .scalars()
            .first()
        )
        reg_status = "CLOSED" if (today_reg and today_reg.is_closed) else ("OPEN" if today_reg else "UNINITIALIZED")

        return FinancialOverviewOut(
            period_start=p_start,
            period_end=p_end,
            preset=resolved_preset,
            net_sales=net_sales,
            completed_bills_count=completed_cnt,
            cancelled_bills_count=cancelled_cnt,
            total_confirmed_collections=total_confirmed,
            cash_collections=cash_collections,
            upi_collections=upi_collections,
            pending_upi_amount=pending_upi,
            total_operating_expenses=total_operating_expenses,
            net_cash_flow=net_cash_flow,
            profit_loss=p_l,
            cash_register_status=reg_status,
        )

    @classmethod
    def get_sales_report(
        cls,
        db: Session,
        preset: str = "today",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> SalesReportOut:
        """Detailed sales report with daily trends and category breakdown."""
        p_start, p_end, resolved_preset = cls.resolve_date_range(preset, start_date, end_date)
        start_dt, end_dt = cls.get_datetime_bounds(p_start, p_end)

        summary = cls.get_daily_sales_summary(db, p_end if p_start == p_end else None)

        # Daily trend
        trend_stmt = (
            select(
                func.date_trunc("day", Bill.created_at).label("day"),
                func.count(Bill.id).label("bill_count"),
                func.coalesce(func.sum(Bill.total_amount), Decimal("0.00")).label("net_sales"),
            )
            .where(
                Bill.bill_status == "COMPLETED",
                Bill.created_at >= start_dt,
                Bill.created_at <= end_dt,
            )
            .group_by(text("1"))
            .order_by(asc("day"))
        )
        trend_rows = db.execute(trend_stmt).all()
        daily_trend = [
            {"date": r.day.strftime("%Y-%m-%d") if r.day else "", "bill_count": r.bill_count, "net_sales": float(r.net_sales)}
            for r in trend_rows
        ]

        # Category breakdown
        cat_stmt = (
            select(
                Product.product_type,
                func.count(BillItem.id).label("items_sold"),
                func.coalesce(func.sum(BillItem.line_total), Decimal("0.00")).label("sales_amount"),
            )
            .join(BillItem, BillItem.product_id == Product.id)
            .join(Bill, Bill.id == BillItem.bill_id)
            .where(
                Bill.bill_status == "COMPLETED",
                Bill.created_at >= start_dt,
                Bill.created_at <= end_dt,
            )
            .group_by(Product.product_type)
        )
        cat_rows = db.execute(cat_stmt).all()
        category_breakdown = [
            {"product_type": r.product_type, "items_sold": r.items_sold, "sales_amount": float(r.sales_amount)}
            for r in cat_rows
        ]

        # Line-by-line completed bills (exclude cancelled bills, ordered newest first)
        bills_stmt = (
            select(Bill)
            .options(joinedload(Bill.items), joinedload(Bill.payments))
            .where(
                Bill.bill_status == "COMPLETED",
                Bill.created_at >= start_dt,
                Bill.created_at <= end_dt,
            )
            .order_by(desc(Bill.created_at))
        )
        bills_entities = db.execute(bills_stmt).unique().scalars().all()

        bills_list: List[SalesBillItemOut] = []
        total_sales = Decimal("0.00")
        for b in bills_entities:
            total_sales += b.total_amount
            items_qty = sum(item.quantity for item in b.items) if b.items else 0

            # Determine payment method
            has_cash = any(p.payment_method == "CASH" for p in b.payments)
            has_upi = any(p.payment_method == "UPI" for p in b.payments)
            if has_cash and has_upi:
                p_method = "Cash + UPI"
            elif has_upi:
                p_method = "UPI"
            elif has_cash:
                p_method = "Cash"
            else:
                p_method = "Cash"

            bills_list.append(
                SalesBillItemOut(
                    id=b.id,
                    bill_number=b.bill_number,
                    created_at=b.created_at,
                    items_count=items_qty,
                    payment_method=p_method,
                    total_amount=b.total_amount,
                )
            )

        return SalesReportOut(
            period_start=p_start,
            period_end=p_end,
            preset=resolved_preset,
            total_sales=total_sales,
            completed_bills_count=len(bills_list),
            bills=bills_list,
            summary=summary,
            daily_trend=daily_trend,
            category_breakdown=category_breakdown,
        )

    @classmethod
    def get_expense_report(
        cls,
        db: Session,
        preset: str = "today",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ExpenseReportOut:
        """Detailed expense report with category breakdown, payment methods, and ledger."""
        p_start, p_end, resolved_preset = cls.resolve_date_range(preset, start_date, end_date)
        start_dt, end_dt = cls.get_datetime_bounds(p_start, p_end)

        by_cat = ExpenseService.get_category_summary(db, start_dt, end_dt)

        # Summary totals
        tot_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
            Expense.is_voided == False,
            Expense.expense_date >= start_dt,
            Expense.expense_date <= end_dt,
        )
        total_expenses = db.scalar(tot_stmt) or Decimal("0.00")

        act_cnt = (
            db.scalar(
                select(func.count(Expense.id)).where(
                    Expense.is_voided == False,
                    Expense.expense_date >= start_dt,
                    Expense.expense_date <= end_dt,
                )
            )
            or 0
        )

        void_cnt = (
            db.scalar(
                select(func.count(Expense.id)).where(
                    Expense.is_voided == True,
                    Expense.expense_date >= start_dt,
                    Expense.expense_date <= end_dt,
                )
            )
            or 0
        )

        # Payment methods breakdown
        pm_stmt = (
            select(
                Expense.payment_method,
                func.coalesce(func.sum(Expense.amount), Decimal("0.00")),
            )
            .where(
                Expense.is_voided == False,
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt,
            )
            .group_by(Expense.payment_method)
        )
        by_pm = {r[0]: r[1] for r in db.execute(pm_stmt).all()}

        # Active expenses in range (exclude voided, newest first)
        active_exp_stmt = (
            select(Expense)
            .where(
                Expense.is_voided == False,
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt,
            )
            .order_by(desc(Expense.expense_date))
        )
        active_expenses = db.execute(active_exp_stmt).scalars().all()
        exp_items = [ExpenseOut.model_validate(e) for e in active_expenses]

        return ExpenseReportOut(
            period_start=p_start,
            period_end=p_end,
            preset=resolved_preset,
            total_expenses=total_expenses,
            active_expenses_count=act_cnt,
            voided_expenses_count=void_cnt,
            by_category=by_cat,
            by_payment_method=by_pm,
            expenses=exp_items,
        )

    @classmethod
    def get_cash_flow(
        cls,
        db: Session,
        preset: str = "today",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> CashFlowSummaryOut:
        """Cash flow report tracking opening, cash sales, inflows, outflows, and variance."""
        p_start, p_end, _ = cls.resolve_date_range(preset, start_date, end_date)
        start_dt, end_dt = cls.get_datetime_bounds(p_start, p_end)

        # Opening cash from the start date register
        start_reg = (
            db.execute(
                select(DailyCashRegister).where(DailyCashRegister.business_date == p_start)
            )
            .scalars()
            .first()
        )
        opening_cash = start_reg.opening_cash if start_reg else Decimal("0.00")

        # Cash sales
        cash_sales = (
            db.scalar(
                select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
                .join(Bill, Bill.id == Payment.bill_id)
                .where(
                    Payment.payment_method == "CASH",
                    Payment.payment_status == "CONFIRMED",
                    Bill.bill_status != "CANCELLED",
                    Payment.received_at >= start_dt,
                    Payment.received_at <= end_dt,
                )
            )
            or Decimal("0.00")
        )

        # Auxiliary Inflows
        other_inflow = (
            db.scalar(
                select(func.coalesce(func.sum(CashMovement.amount), Decimal("0.00"))).where(
                    CashMovement.movement_type == "INFLOW",
                    CashMovement.created_at >= start_dt,
                    CashMovement.created_at <= end_dt,
                )
            )
            or Decimal("0.00")
        )
        total_inflow = cash_sales + other_inflow

        # Cash Expenses
        cash_expenses = (
            db.scalar(
                select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
                    Expense.payment_method == "CASH",
                    Expense.is_voided == False,
                    Expense.expense_date >= start_dt,
                    Expense.expense_date <= end_dt,
                )
            )
            or Decimal("0.00")
        )

        # Auxiliary Outflows
        other_outflow = (
            db.scalar(
                select(func.coalesce(func.sum(CashMovement.amount), Decimal("0.00"))).where(
                    CashMovement.movement_type == "OUTFLOW",
                    CashMovement.created_at >= start_dt,
                    CashMovement.created_at <= end_dt,
                )
            )
            or Decimal("0.00")
        )
        total_outflow = cash_expenses + other_outflow

        net_flow = total_inflow - total_outflow
        expected_closing = opening_cash + net_flow

        # End date register for actual closing
        end_reg = (
            db.execute(
                select(DailyCashRegister).where(DailyCashRegister.business_date == p_end)
            )
            .scalars()
            .first()
        )
        actual_closing = end_reg.actual_closing_cash if end_reg else None
        diff = (actual_closing - expected_closing) if actual_closing is not None else None

        if actual_closing is None or diff is None:
            recon_status = "PENDING_CLOSE"
        elif diff == Decimal("0.00"):
            recon_status = "BALANCED"
        elif diff > Decimal("0.00"):
            recon_status = "SURPLUS"
        else:
            recon_status = "SHORTAGE"

        return CashFlowSummaryOut(
            period_start=p_start,
            period_end=p_end,
            opening_cash=opening_cash,
            cash_sales=cash_sales,
            other_cash_inflow=other_inflow,
            total_cash_inflow=total_inflow,
            cash_expenses=cash_expenses,
            other_cash_outflow=other_outflow,
            total_cash_outflow=total_outflow,
            net_cash_flow=net_flow,
            expected_closing_cash=expected_closing,
            actual_closing_cash=actual_closing,
            cash_difference=diff,
            reconciliation_status=recon_status,
        )

    # ==============================================================================
    # Export Generators (PDF and Excel)
    # ==============================================================================

    @classmethod
    def generate_pdf_report(
        cls,
        db: Session,
        preset: str = "today",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> bytes:
        """Generate professional A4 PDF Sales & Expenses report using ReportLab."""
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            HRFlowable,
            KeepTogether,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        class NumberedCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.draw_page_decorations(num_pages)
                    super().showPage()
                super().save()

            def draw_page_decorations(self, page_count):
                self.saveState()
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#6B7280"))
                self.drawString(36, 25, "Generated by VIYON Store Billing System")
                page_str = f"Page {self._pageNumber} of {page_count}"
                self.drawRightString(595.275 - 36, 25, page_str)
                self.setStrokeColor(colors.HexColor("#E5E7EB"))
                self.setLineWidth(0.5)
                self.line(36, 35, 595.275 - 36, 35)
                self.restoreState()

        sales_data = cls.get_sales_report(db, preset, start_date, end_date)
        expenses_data = cls.get_expense_report(db, preset, start_date, end_date)

        p_start = sales_data.period_start
        p_end = sales_data.period_end
        total_sales = sales_data.total_sales
        total_expenses = expenses_data.total_expenses
        net_balance = total_sales - total_expenses

        # Dynamic Report Title based on filter
        preset_clean = (preset or "today").strip().lower()
        if preset_clean in ("today", "yesterday"):
            report_title = "Daily Sales & Expenses Report"
        elif preset_clean == "this_week":
            report_title = "Weekly Sales & Expenses Report"
        elif preset_clean == "this_month":
            report_title = "Monthly Sales & Expenses Report"
        elif preset_clean == "previous_month":
            report_title = "Previous Month Sales & Expenses Report"
        else:
            report_title = "Sales & Expenses Report"

        # Reporting Period string
        if p_start == p_end:
            period_str = f"Reporting Period: {p_start.strftime('%d %B %Y')}"
        else:
            period_str = f"Reporting Period: {p_start.strftime('%d %B %Y')} - {p_end.strftime('%d %B %Y')}"

        gen_str = f"Generated: {datetime.now(STORE_TZ).strftime('%d %B %Y, %I:%M %p')}"

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=45,
        )

        styles = getSampleStyleSheet()

        brand_title_style = ParagraphStyle(
            "BrandTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=1,
            textColor=colors.HexColor("#18181B"),
        )
        brand_tagline_style = ParagraphStyle(
            "BrandTagline",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=1,
            textColor=colors.HexColor("#D97706"),
        )
        store_meta_style = ParagraphStyle(
            "StoreMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=1,
            textColor=colors.HexColor("#4B5563"),
        )
        report_title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            alignment=1,
            textColor=colors.HexColor("#18181B"),
            spaceBefore=6,
            spaceAfter=3,
        )
        period_style = ParagraphStyle(
            "PeriodStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            alignment=1,
            textColor=colors.HexColor("#B45309"),
        )
        meta_sub_style = ParagraphStyle(
            "MetaSub",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            alignment=1,
            textColor=colors.HexColor("#6B7280"),
        )
        section_h2 = ParagraphStyle(
            "SectionH2",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#18181B"),
            spaceBefore=12,
            spaceAfter=6,
        )
        th_style = ParagraphStyle(
            "THStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.white,
        )
        th_style_right = ParagraphStyle(
            "THStyleRight",
            parent=th_style,
            alignment=2,
        )
        th_style_center = ParagraphStyle(
            "THStyleCenter",
            parent=th_style,
            alignment=1,
        )
        td_style = ParagraphStyle(
            "TDStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1F2937"),
        )
        td_style_bold = ParagraphStyle(
            "TDBold",
            parent=td_style,
            fontName="Helvetica-Bold",
        )
        td_style_right = ParagraphStyle(
            "TDRight",
            parent=td_style,
            alignment=2,
        )
        td_style_right_bold = ParagraphStyle(
            "TDRightBold",
            parent=td_style_bold,
            alignment=2,
        )
        td_style_center = ParagraphStyle(
            "TDCenter",
            parent=td_style,
            alignment=1,
        )
        empty_style = ParagraphStyle(
            "EmptyStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            alignment=1,
            textColor=colors.HexColor("#9CA3AF"),
        )

        story: List[Any] = []

        # 1. Header
        story.append(Paragraph(STORE_NAME, brand_title_style))
        story.append(Paragraph(STORE_TAGLINE, brand_tagline_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(STORE_ADDRESS, store_meta_style))
        story.append(Paragraph(f"Phone: {STORE_PHONE}", store_meta_style))
        story.append(Spacer(1, 5))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#D97706")))
        story.append(Spacer(1, 4))
        story.append(Paragraph(report_title, report_title_style))
        story.append(Paragraph(period_str, period_style))
        story.append(Paragraph(gen_str, meta_sub_style))
        story.append(Spacer(1, 8))

        # 2. Sales Section
        story.append(Paragraph("SALES REPORT", section_h2))
        sales_table_data = [
            [
                Paragraph("Bill No.", th_style),
                Paragraph("Date & Time", th_style),
                Paragraph("Items", th_style_center),
                Paragraph("Payment Method", th_style),
                Paragraph("Amount (INR)", th_style_right),
            ]
        ]

        if sales_data.bills:
            for b in sales_data.bills:
                dt_str = b.created_at.astimezone(STORE_TZ).strftime("%d-%b-%Y %I:%M %p")
                sales_table_data.append([
                    Paragraph(b.bill_number, td_style_bold),
                    Paragraph(dt_str, td_style),
                    Paragraph(str(b.items_count), td_style_center),
                    Paragraph(b.payment_method, td_style),
                    Paragraph(f"₹{b.total_amount:,.2f}", td_style_right),
                ])
        else:
            sales_table_data.append([
                Paragraph("No sales recorded for this period.", empty_style),
                Paragraph("", td_style),
                Paragraph("", td_style),
                Paragraph("", td_style),
                Paragraph("", td_style),
            ])

        # Total Sales footer row
        sales_table_data.append([
            Paragraph("<b>Total Sales:</b>", td_style_bold),
            Paragraph("", td_style),
            Paragraph(f"<b>{sales_data.completed_bills_count} bills</b>", td_style_center),
            Paragraph("", td_style),
            Paragraph(f"<b>₹{total_sales:,.2f}</b>", td_style_right_bold),
        ])

        sales_table = Table(sales_table_data, colWidths=[110, 120, 55, 105, 133], repeatRows=1)
        sales_table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18181B")),
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F4F4F5")),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#18181B")),
        ]
        if not sales_data.bills:
            sales_table_style.append(("SPAN", (0, 1), (-1, 1)))
        sales_table.setStyle(TableStyle(sales_table_style))
        story.append(sales_table)
        story.append(Spacer(1, 14))

        # 3. Expenses Section
        story.append(Paragraph("EXPENSES REPORT", section_h2))
        exp_table_data = [
            [
                Paragraph("Date & Time", th_style),
                Paragraph("Expense Category", th_style),
                Paragraph("Description", th_style),
                Paragraph("Amount (INR)", th_style_right),
            ]
        ]

        if expenses_data.expenses:
            for e in expenses_data.expenses:
                dt_str = e.expense_date.astimezone(STORE_TZ).strftime("%d-%b-%Y %I:%M %p")
                desc_str = e.description or e.expense_title or "-"
                exp_table_data.append([
                    Paragraph(dt_str, td_style),
                    Paragraph(e.category, td_style_bold),
                    Paragraph(desc_str, td_style),
                    Paragraph(f"₹{e.amount:,.2f}", td_style_right),
                ])
        else:
            exp_table_data.append([
                Paragraph("No expenses recorded for this period.", empty_style),
                Paragraph("", td_style),
                Paragraph("", td_style),
                Paragraph("", td_style),
            ])

        # Total Expenses footer row
        exp_table_data.append([
            Paragraph("<b>Total Expenses:</b>", td_style_bold),
            Paragraph(f"<b>{expenses_data.active_expenses_count} items</b>", td_style),
            Paragraph("", td_style),
            Paragraph(f"<b>₹{total_expenses:,.2f}</b>", td_style_right_bold),
        ])

        exp_table = Table(exp_table_data, colWidths=[120, 115, 155, 133], repeatRows=1)
        exp_table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18181B")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F4F4F5")),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#18181B")),
        ]
        if not expenses_data.expenses:
            exp_table_style.append(("SPAN", (0, 1), (-1, 1)))
        exp_table.setStyle(TableStyle(exp_table_style))
        story.append(exp_table)
        story.append(Spacer(1, 14))

        # 4. Summary Section (KeepTogether)
        summary_story: List[Any] = []
        summary_story.append(Paragraph("PERIOD FINANCIAL SUMMARY", section_h2))

        net_text_color = "#15803D" if net_balance >= 0 else "#DC2626"
        summary_rows = [
            [
                Paragraph("<b>Total Sales</b>", td_style),
                Paragraph(f"₹{total_sales:,.2f}", td_style_right_bold),
            ],
            [
                Paragraph("<b>Total Expenses</b>", td_style),
                Paragraph(f"₹{total_expenses:,.2f}", td_style_right_bold),
            ],
            [
                Paragraph("<b>NET BALANCE (Total Sales - Total Expenses)</b>", ParagraphStyle(
                    "NetLabel",
                    parent=td_style_bold,
                    fontSize=10,
                    textColor=colors.HexColor("#92400E"),
                )),
                Paragraph(f"<b>₹{net_balance:,.2f}</b>", ParagraphStyle(
                    "NetVal",
                    parent=td_style_right_bold,
                    fontSize=11,
                    textColor=colors.HexColor(net_text_color),
                )),
            ],
        ]

        summary_table = Table(summary_rows, colWidths=[360, 163])
        summary_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#FAFAFA")),
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FEF3C7")),
            ("BOX", (0, 2), (-1, 2), 1.5, colors.HexColor("#D97706")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        summary_story.append(summary_table)

        story.append(KeepTogether(summary_story))

        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

    @classmethod
    def generate_excel_report(
        cls,
        db: Session,
        preset: str = "today",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> bytes:
        """Generate structured multi-sheet Excel report using OpenPyXL."""
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        overview = cls.get_financial_overview(db, preset, start_date, end_date)
        start_dt, end_dt = cls.get_datetime_bounds(overview.period_start, overview.period_end)

        wb = Workbook()

        # Styles
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
        bold_font = Font(name="Calibri", size=11, bold=True)
        thin_border = Border(
            left=Side(style="thin", color="D1D5DB"),
            right=Side(style="thin", color="D1D5DB"),
            top=Side(style="thin", color="D1D5DB"),
            bottom=Side(style="thin", color="D1D5DB"),
        )

        # -------------------------------------------------------------
        # Sheet 1: Financial Summary
        # -------------------------------------------------------------
        ws_sum = wb.active
        if ws_sum is None:
            ws_sum = wb.create_sheet(title="Financial Summary")
        else:
            ws_sum.title = "Financial Summary"
        ws_sum.views.sheetView[0].showGridLines = True

        ws_sum["A1"] = f"{STORE_NAME} - FINANCIAL REPORT"
        ws_sum["A1"].font = title_font
        ws_sum["A2"] = f"Period: {overview.period_start} to {overview.period_end} ({overview.preset.upper()})"
        ws_sum["A3"] = f"Generated: {datetime.now(STORE_TZ).strftime('%Y-%m-%d %H:%M:%S')} (Asia/Kolkata)"

        ws_sum.append([])
        ws_sum.append(["Key Financial Indicator", "Value", "Notes"])
        header_row = ws_sum.max_row
        for col_idx in range(1, 4):
            cell = ws_sum.cell(row=header_row, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font

        kpis = [
            ("Total Net Sales", float(overview.net_sales), f"{overview.completed_bills_count} completed bills"),
            ("Cancelled Bills Count", overview.cancelled_bills_count, "Excluded from sales"),
            ("Confirmed Collections", float(overview.total_confirmed_collections), f"Cash: {overview.cash_collections} | UPI: {overview.upi_collections}"),
            ("Cash Collections", float(overview.cash_collections), "Confirmed cash from active bills"),
            ("UPI Collections", float(overview.upi_collections), "Confirmed UPI from active bills"),
            ("Pending UPI Collections", float(overview.pending_upi_amount), "NOT counted in collections or revenue"),
            ("Total Operating Expenses", float(overview.total_operating_expenses), "Active non-voided business expenses"),
            ("Net Cash Flow", float(overview.net_cash_flow), "Cash sales minus cash expenses"),
            ("Cost of Goods Sold (COGS)", float(overview.profit_loss.cogs) if overview.profit_loss.cogs is not None else "UNAVAILABLE", overview.profit_loss.cogs_status),
            ("Gross Profit", float(overview.profit_loss.gross_profit) if overview.profit_loss.gross_profit is not None else "UNAVAILABLE", overview.profit_loss.profit_status),
            ("Net Operating Profit", float(overview.profit_loss.net_operating_profit) if overview.profit_loss.net_operating_profit is not None else "UNAVAILABLE", overview.profit_loss.explanation_note),
        ]

        for kpi, val, note in kpis:
            ws_sum.append([kpi, val, note])
            curr_row = ws_sum.max_row
            ws_sum.cell(row=curr_row, column=1).font = bold_font
            for c in range(1, 4):
                ws_sum.cell(row=curr_row, column=c).border = thin_border

        for col_idx, col in enumerate(ws_sum.columns, start=1):
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col_idx)
            ws_sum.column_dimensions[col_letter].width = max(max_len + 3, 14)

        # -------------------------------------------------------------
        # Sheet 2: Sales Transactions
        # -------------------------------------------------------------
        ws_bills = wb.create_sheet(title="Sales Transactions")
        ws_bills.views.sheetView[0].showGridLines = True
        ws_bills.append([
            "Bill Number", "Date & Time", "Customer Name", "Subtotal", "Discount", "Tax",
            "Total Amount", "Amount Paid", "Balance Amount", "Payment Status", "Bill Status"
        ])
        for col_idx in range(1, 12):
            cell = ws_bills.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font

        bills_stmt = (
            select(Bill)
            .options(joinedload(Bill.customer))
            .where(Bill.created_at >= start_dt, Bill.created_at <= end_dt)
            .order_by(desc(Bill.created_at))
        )
        bills = db.execute(bills_stmt).scalars().all()
        for b in bills:
            cust_name = b.customer.customer_name if b.customer else "Walk-in Customer"
            ws_bills.append([
                b.bill_number,
                b.created_at.astimezone(STORE_TZ).strftime("%Y-%m-%d %H:%M"),
                cust_name,
                float(b.subtotal),
                float(b.discount_amount),
                float(b.tax_amount),
                float(b.total_amount),
                float(b.amount_paid),
                float(b.balance_amount),
                b.payment_status,
                b.bill_status,
            ])
            curr_row = ws_bills.max_row
            for c in range(1, 12):
                ws_bills.cell(row=curr_row, column=c).border = thin_border

        for col_idx, col in enumerate(ws_bills.columns, start=1):
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col_idx)
            ws_bills.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # -------------------------------------------------------------
        # Sheet 3: Expense Ledger
        # -------------------------------------------------------------
        ws_exp = wb.create_sheet(title="Expense Ledger")
        ws_exp.views.sheetView[0].showGridLines = True
        ws_exp.append([
            "Title", "Category", "Amount", "Payment Method", "Date",
            "Reference #", "Status", "Void Reason"
        ])
        for col_idx in range(1, 9):
            cell = ws_exp.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font

        exp_stmt = (
            select(Expense)
            .where(Expense.expense_date >= start_dt, Expense.expense_date <= end_dt)
            .order_by(desc(Expense.expense_date))
        )
        expenses = db.execute(exp_stmt).scalars().all()
        for e in expenses:
            ws_exp.append([
                e.expense_title,
                e.category,
                float(e.amount),
                e.payment_method,
                e.expense_date.astimezone(STORE_TZ).strftime("%Y-%m-%d"),
                e.reference_number or "",
                "VOIDED" if e.is_voided else "ACTIVE",
                e.void_reason or "",
            ])
            curr_row = ws_exp.max_row
            for c in range(1, 9):
                ws_exp.cell(row=curr_row, column=c).border = thin_border

        for col_idx, col in enumerate(ws_exp.columns, start=1):
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col_idx)
            ws_exp.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # -------------------------------------------------------------
        # Sheet 4: Cash Registers
        # -------------------------------------------------------------
        ws_reg = wb.create_sheet(title="Cash Registers")
        ws_reg.views.sheetView[0].showGridLines = True
        ws_reg.append([
            "Business Date", "Opening Cash", "Cash Sales", "Cash Expenses",
            "Inflow", "Outflow", "Expected Closing", "Actual Closing",
            "Difference", "Status"
        ])
        for col_idx in range(1, 11):
            cell = ws_reg.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font

        reg_stmt = (
            select(DailyCashRegister)
            .where(
                DailyCashRegister.business_date >= overview.period_start,
                DailyCashRegister.business_date <= overview.period_end,
            )
            .order_by(desc(DailyCashRegister.business_date))
        )
        registers = db.execute(reg_stmt).scalars().all()
        for r in registers:
            ws_reg.append([
                r.business_date.strftime("%Y-%m-%d"),
                float(r.opening_cash),
                float(r.cash_sales),
                float(r.cash_expenses),
                float(r.other_cash_inflow),
                float(r.other_cash_outflow),
                float(r.expected_closing_cash),
                float(r.actual_closing_cash) if r.actual_closing_cash is not None else "",
                float(r.cash_difference) if r.cash_difference is not None else "",
                "CLOSED" if r.is_closed else "OPEN",
            ])
            curr_row = ws_reg.max_row
            for c in range(1, 11):
                ws_reg.cell(row=curr_row, column=c).border = thin_border

        for col_idx, col in enumerate(ws_reg.columns, start=1):
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col_idx)
            ws_reg.column_dimensions[col_letter].width = max(max_len + 3, 12)

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
