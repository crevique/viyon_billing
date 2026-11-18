import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  ShoppingCart,
  Receipt,
  Package,
  FolderTree,
  Boxes,
  History,
  Truck,
  FileSpreadsheet,
  PackageCheck,
  ClipboardList,
  CreditCard,
  Users,
  Wallet,
  BarChart3,
  Settings,
  ShieldCheck,
  LogOut,
  ChevronRight,
  Store,
  X,
} from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { cn } from '../../utils/cn';

interface SidebarProps {
  isOpen: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { user, role, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isOwner = role === 'OWNER' || role === 'ADMIN';

  // Navigation lists strictly defined by specification
  const ownerNavItems = [
    { label: 'Overview', to: '/', icon: LayoutDashboard },
    { label: 'POS Billing', to: '/pos', icon: ShoppingCart, highlight: true },
    { label: 'Bills & Transactions', to: '/bills', icon: Receipt },
    { label: 'Products', to: '/products', icon: Package },
    { label: 'Categories', to: '/categories', icon: FolderTree },
    { label: 'Inventory', to: '/inventory', icon: Boxes },
    { label: 'Stock Movements', to: '/inventory/movements', icon: History },
    { label: 'Suppliers', to: '/suppliers', icon: Truck },
    { label: 'Purchase Orders', to: '/purchases', icon: FileSpreadsheet },
    { label: 'Goods Receiving', to: '/purchases/receiving', icon: PackageCheck },
    { label: 'Goods Receipt History', to: '/purchases/receipts', icon: ClipboardList },
    { label: 'Supplier Payments', to: '/purchases/payments', icon: CreditCard },
    { label: 'Staff Management', to: '/staff-management', icon: Users },
    { label: 'Expenses', to: '/expenses', icon: Wallet },
    { label: 'Financial Reports', to: '/finance/reports', icon: BarChart3 },
    { label: 'Store Settings', to: '/settings', icon: Settings },
    { label: 'Audit History', to: '/audit-history', icon: ShieldCheck },
  ];

  const staffNavItems = [
    { label: 'POS Billing', to: '/pos', icon: ShoppingCart, highlight: true },
    { label: 'Staff Dashboard', to: '/staff-dashboard', icon: LayoutDashboard },
    { label: 'Products View', to: '/products', icon: Package },
    { label: 'Inventory View', to: '/inventory', icon: Boxes },
    { label: 'Bill History', to: '/bills', icon: Receipt },
  ];

  const navItems = isOwner ? ownerNavItems : staffNavItems;

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-zinc-950/60 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-zinc-950 text-zinc-100 transition-transform duration-300 ease-in-out lg:static lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand Header */}
        <div className="flex h-18 items-center justify-between border-b border-zinc-800/80 px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 text-zinc-950 shadow-md">
              <Store className="h-6 w-6 stroke-[2.2]" />
            </div>
            <div className="flex flex-col">
              <span className="font-serif text-lg font-bold tracking-widest text-white">VIYON</span>
              <span className="text-[10px] font-medium tracking-wider text-amber-400/90 uppercase">
                Billing & Retail POS
              </span>
            </div>
          </div>
          {/* Mobile Close Button */}
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="flex h-9 w-9 items-center justify-center rounded-lg text-zinc-400 hover:bg-zinc-800 hover:text-white lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* User Info Capsule */}
        <div className="mx-4 my-3 rounded-lg border border-zinc-800/60 bg-zinc-900/60 p-3">
          <div className="flex items-center justify-between">
            <div className="truncate">
              <p className="truncate text-xs font-semibold text-zinc-200">
                {user?.full_name || 'Staff Member'}
              </p>
              <p className="text-[11px] text-zinc-400">
                {user?.employee_id || user?.username || user?.email}
              </p>
            </div>
            <span
              className={cn(
                'rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                isOwner
                  ? 'bg-amber-400/10 text-amber-400 border border-amber-400/30'
                  : 'bg-emerald-400/10 text-emerald-400 border border-emerald-400/30'
              )}
            >
              {role || 'STAFF'}
            </span>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2 scrollbar-thin scrollbar-thumb-zinc-800">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center justify-between rounded-lg px-3 py-2.5 text-xs font-medium transition-all duration-150',
                    isActive
                      ? 'bg-amber-500 text-zinc-950 shadow-sm font-semibold'
                      : item.highlight
                        ? 'text-amber-400 hover:bg-zinc-900 hover:text-amber-300 font-semibold'
                        : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center gap-3">
                      <Icon
                        className={cn(
                          'h-4 w-4 transition-transform group-hover:scale-105',
                          isActive ? 'text-zinc-950' : item.highlight ? 'text-amber-400' : 'text-zinc-400'
                        )}
                      />
                      <span>{item.label}</span>
                    </div>
                    {isActive && <ChevronRight className="h-3.5 w-3.5 text-zinc-950" />}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Logout Footer */}
        <div className="border-t border-zinc-800/80 p-3">
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium text-rose-400 transition-colors hover:bg-rose-950/30 hover:text-rose-300"
          >
            <LogOut className="h-4 w-4" />
            <span>Logout Session</span>
          </button>
        </div>
      </aside>
    </>
  );
};
