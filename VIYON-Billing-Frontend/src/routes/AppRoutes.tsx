import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { ProtectedRoute } from '../components/common/ProtectedRoute';

// Pages
import { LoginPage } from '../pages/auth/LoginPage';
import { OverviewPage } from '../pages/owner/OverviewPage';
import { StaffDashboardPage } from '../pages/staff/StaffDashboardPage';
import { POSPage } from '../pages/pos/POSPage';
import { BillsPage } from '../pages/bills/BillsPage';
import { ProductsPage } from '../pages/products/ProductsPage';
import { CategoriesPage } from '../pages/products/CategoriesPage';
import { InventoryPage } from '../pages/inventory/InventoryPage';
import { StockMovementsPage } from '../pages/inventory/StockMovementsPage';
import { SuppliersPage } from '../pages/purchases/SuppliersPage';
import { PurchaseOrdersPage } from '../pages/purchases/PurchaseOrdersPage';
import { GoodsReceivingPage } from '../pages/purchases/GoodsReceivingPage';
import { GoodsReceiptHistoryPage } from '../pages/purchases/GoodsReceiptHistoryPage';
import { SupplierPaymentsPage } from '../pages/purchases/SupplierPaymentsPage';
import { StaffManagementPage } from '../pages/staff-mgmt/StaffManagementPage';
import { ExpensesPage } from '../pages/finance/ExpensesPage';
import { FinancialReportsPage } from '../pages/finance/FinancialReportsPage';
import { SettingsPage } from '../pages/settings/SettingsPage';
import { AuditHistoryPage } from '../pages/settings/AuditHistoryPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Login Route */}
      <Route path="/login" element={<LoginPage />} />

      {/* Authenticated Application Shell */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        {/* Owner Executive Overview (Default) */}
        <Route
          index
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <OverviewPage />
            </ProtectedRoute>
          }
        />

        {/* POS Billing (Both Owner & Staff) */}
        <Route path="pos" element={<POSPage />} />

        {/* Staff Dashboard */}
        <Route path="staff-dashboard" element={<StaffDashboardPage />} />

        {/* Bills & Transactions (Both Owner & Staff) */}
        <Route path="bills" element={<BillsPage />} />

        {/* Products & Categories */}
        <Route path="products" element={<ProductsPage />} />
        <Route path="categories" element={<CategoriesPage />} />

        {/* Inventory & Ledger */}
        <Route path="inventory" element={<InventoryPage />} />
        <Route path="inventory/movements" element={<StockMovementsPage />} />

        {/* Supplier & Purchase Management */}
        <Route
          path="suppliers"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <SuppliersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="purchases"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <PurchaseOrdersPage />
            </ProtectedRoute>
          }
        />
        <Route path="purchases/receiving" element={<GoodsReceivingPage />} />
        <Route path="purchases/receipts" element={<GoodsReceiptHistoryPage />} />
        <Route
          path="purchases/payments"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <SupplierPaymentsPage />
            </ProtectedRoute>
          }
        />

        {/* Staff Management (Owner Only) */}
        <Route
          path="staff-management"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <StaffManagementPage />
            </ProtectedRoute>
          }
        />

        {/* Expenses & Daily Cash Register (Owner Only) */}
        <Route
          path="expenses"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <ExpensesPage />
            </ProtectedRoute>
          }
        />

        {/* Financial Reports & Analytics (Owner Only) */}
        <Route
          path="finance/reports"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <FinancialReportsPage />
            </ProtectedRoute>
          }
        />

        {/* Store Settings & Audit History (Owner Only) */}
        <Route
          path="settings"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="audit-history"
          element={
            <ProtectedRoute allowedRoles={['OWNER', 'ADMIN']}>
              <AuditHistoryPage />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};
