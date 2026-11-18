// Currency, date, and string formatting utilities for VIYON Billing

export function formatCurrency(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return '₹0.00';
  }
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(d);
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }).format(d);
  } catch {
    return dateString;
  }
}

export function getStatusBadgeClass(status: string | null | undefined): string {
  const s = (status || '').toUpperCase();
  switch (s) {
    case 'PAID':
    case 'CONFIRMED':
    case 'COMPLETED':
    case 'ACTIVE':
    case 'IN_STOCK':
    case 'RECEIVED':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'PENDING':
    case 'PARTIAL':
    case 'PARTIALLY_RECEIVED':
    case 'LOW_STOCK':
    case 'DRAFT':
    case 'ORDERED':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'CANCELLED':
    case 'REJECTED':
    case 'VOIDED':
    case 'OUT_OF_STOCK':
    case 'FAILED':
    case 'INACTIVE':
      return 'bg-rose-50 text-rose-700 border-rose-200';
    default:
      return 'bg-zinc-100 text-zinc-700 border-zinc-200';
  }
}
