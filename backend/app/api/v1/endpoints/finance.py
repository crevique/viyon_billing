"""API endpoints for store financial analytics, daily sales summaries, cash register management, and reports export."""

import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, get_db
from app.models.user import User
from app.schemas.finance import (
    DailySalesSummaryOut,
    FinancialOverviewOut,
    SalesReportOut,
    ExpenseReportOut,
    ProfitLossReportOut,
    CashFlowSummaryOut,
    CashOpeningRequest,
    CashMovementCreate,
    CashMovementOut,
    CashClosingRequest,
    CashCorrectionRequest,
    DailyCashRegisterOut,
    DailyCashRegisterListResponse,
)
from app.services.cash_management_service import CashManagementService
from app.services.financial_report_service import FinancialReportService

router = APIRouter(tags=["Finance & Reports"])


# ==============================================================================
# 1. Executive Dashboards & Analytics
# ==============================================================================

@router.get(
    "/overview",
    response_model=FinancialOverviewOut,
    summary="Get financial overview cards for executive dashboard",
)
def get_financial_overview(
    preset: str = Query("today", description="Period preset: today, yesterday, this_week, this_month, previous_month, custom"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD) for custom preset"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD) for custom preset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> FinancialOverviewOut:
    """Owner dashboard summary covering sales, collections, expenses, cash flow, and P&L."""
    return FinancialReportService.get_financial_overview(
        db=db,
        preset=preset,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/daily-summary",
    response_model=DailySalesSummaryOut,
    summary="Get daily sales and collections summary for a calendar day",
)
def get_daily_sales_summary(
    business_date: Optional[date] = Query(None, alias="date", description="Business date (YYYY-MM-DD, defaults to today in Asia/Kolkata)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> DailySalesSummaryOut:
    """Detailed reconciliation of completed sales, confirmed collections, discounts, and tax."""
    return FinancialReportService.get_daily_sales_summary(db=db, business_date=business_date)


@router.get(
    "/sales-report",
    response_model=SalesReportOut,
    summary="Get detailed sales report with daily trends and category breakdown",
)
def get_sales_report(
    preset: str = Query("today", description="Period preset"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SalesReportOut:
    """Sales analysis across time and product types."""
    return FinancialReportService.get_sales_report(
        db=db,
        preset=preset,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/expense-report",
    response_model=ExpenseReportOut,
    summary="Get detailed operational expense breakdown and audit ledger",
)
def get_expense_report(
    preset: str = Query("today", description="Period preset"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ExpenseReportOut:
    """Expense report categorized by operational buckets with payment method breakdowns."""
    return FinancialReportService.get_expense_report(
        db=db,
        preset=preset,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/profit-loss",
    response_model=ProfitLossReportOut,
    summary="Get Profit & Loss statement with strict COGS validation",
)
def get_profit_loss(
    preset: str = Query("today", description="Period preset"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ProfitLossReportOut:
    """Gross and Net Operating Profit report. Explicitly marks profit unavailable if cost data is absent."""
    p_start, p_end, resolved = FinancialReportService.resolve_date_range(preset, start_date, end_date)
    return FinancialReportService.get_profit_loss(
        db=db,
        start_date=p_start,
        end_date=p_end,
        preset=resolved,
    )


@router.get(
    "/cash-flow",
    response_model=CashFlowSummaryOut,
    summary="Get cash flow report tracking opening, cash sales, inflows, outflows, and variance",
)
def get_cash_flow(
    preset: str = Query("today", description="Period preset"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> CashFlowSummaryOut:
    """Physical cash flow reconciliation across the requested window."""
    return FinancialReportService.get_cash_flow(
        db=db,
        preset=preset,
        start_date=start_date,
        end_date=end_date,
    )


# ==============================================================================
# 2. Daily Cash Register Management
# ==============================================================================

@router.post(
    "/cash/opening",
    response_model=DailyCashRegisterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record opening cash balance for a business day",
)
def open_cash_register(
    data: CashOpeningRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> DailyCashRegisterOut:
    """Open cash drawer for the day (Blocks duplicate opening for the same date)."""
    return CashManagementService.open_register(db, data, current_user.id)


@router.get(
    "/cash/history",
    response_model=DailyCashRegisterListResponse,
    summary="List historical cash registers with pagination and filtering",
)
def list_cash_registers(
    start_date: Optional[date] = Query(None, description="Filter start business date"),
    end_date: Optional[date] = Query(None, description="Filter end business date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> DailyCashRegisterListResponse:
    """Audit log of all daily cash registers."""
    return CashManagementService.list_register_history(
        db=db,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/cash/{business_date}",
    response_model=DailyCashRegisterOut,
    summary="Get cash register status and live reconciliation for a date",
)
def get_cash_register(
    business_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> DailyCashRegisterOut:
    """Live cash balance, cash sales, cash expenses, and auxiliary movements."""
    return CashManagementService.get_register_by_date(db, business_date)


@router.post(
    "/cash/{register_id}/movements",
    response_model=CashMovementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record auxiliary cash movement (Inflow or Outflow)",
)
def add_cash_movement(
    register_id: uuid.UUID,
    data: CashMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> CashMovementOut:
    """Record petty cash injection or owner withdrawal while register is open."""
    return CashManagementService.add_movement(db, register_id, data, current_user.id)


@router.post(
    "/cash/{register_id}/close",
    response_model=DailyCashRegisterOut,
    summary="Close daily cash register with actual physical cash count",
)
def close_cash_register(
    register_id: uuid.UUID,
    data: CashClosingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> DailyCashRegisterOut:
    """Lock day's register, compute cash variance, and finalize closing figures."""
    return CashManagementService.close_register(db, register_id, data, current_user.id)


@router.post(
    "/cash/{register_id}/correct",
    response_model=DailyCashRegisterOut,
    summary="Owner correction workflow for an already-closed register",
)
def correct_cash_register(
    register_id: uuid.UUID,
    data: CashCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> DailyCashRegisterOut:
    """Apply audited correction to physical count on closed register."""
    return CashManagementService.correct_closed_register(db, register_id, data, current_user.id)


# ==============================================================================
# 3. Export Reports (PDF & Excel)
# ==============================================================================

@router.get(
    "/reports/export/pdf",
    summary="Download professional PDF financial report",
)
def export_pdf_report(
    preset: str = Query("today", description="Period preset"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> Response:
    """Generate printable PDF report with store branding, executive summary, and tables."""
    pdf_bytes = FinancialReportService.generate_pdf_report(
        db=db,
        preset=preset,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"VIYON-Sales-Expenses-Report-{preset}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/reports/export/excel",
    summary="Download structured Excel financial workbook",
)
def export_excel_report(
    preset: str = Query("today", description="Period preset"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> Response:
    """Generate multi-tab Excel workbook with summary, sales, expenses, and cash registers."""
    excel_bytes = FinancialReportService.generate_excel_report(
        db=db,
        preset=preset,
        start_date=start_date,
        end_date=end_date,
    )
    filename = f"VIYON-Financial-Report-{preset}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
