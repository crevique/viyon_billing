import React, { useState, useEffect } from 'react';
import {
  Users,
  Plus,
  Search,
  KeyRound,
  ShieldCheck,
  ShieldAlert,
  Edit,
  Activity,
  Trash2,
  X,
  CheckCircle,
  AlertCircle,
  Receipt,
} from 'lucide-react';
import { User, StaffMetrics, StaffActivity, StaffCreatePayload } from '../../types';
import { staffService } from '../../services/staffService';
import { getErrorMessage } from '../../services/api';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

export const StaffManagementPage: React.FC = () => {
  const { role } = useAuthStore();
  const canRemove = role === 'OWNER';

  const [staffList, setStaffList] = useState<User[]>([]);
  const [metrics, setMetrics] = useState<StaffMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isResetPasswordModalOpen, setIsResetPasswordModalOpen] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState<User | null>(null);

  // Removal & Notification State
  const [removingStaff, setRemovingStaff] = useState<User | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Activity Drawer
  const [staffActivity, setStaffActivity] = useState<StaffActivity | null>(null);
  const [loadingActivity, setLoadingActivity] = useState(false);

  // Form states
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newConfirmPassword, setNewConfirmPassword] = useState('');

  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadStaffData();
  }, []);

  const loadStaffData = async () => {
    setLoading(true);
    try {
      const [list, met] = await Promise.all([
        staffService.listStaff({ search: search.trim() || undefined }),
        staffService.getMetrics(),
      ]);
      setStaffList(list || []);
      setMetrics(met);
    } catch (err) {
      console.error('Failed to load staff management', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateModal = () => {
    setFullName('');
    setUsername('');
    setEmail('');
    setPhone('');
    setPassword('');
    setConfirmPassword('');
    setFormError(null);
    setIsCreateModalOpen(true);
  };

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!fullName.trim() || !username.trim()) {
      setFormError('Full name and unique username are required.');
      return;
    }
    if (password.length < 8) {
      setFormError('Password must be at least 8 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setFormError('Password and confirmation password do not match.');
      return;
    }

    setIsSaving(true);
    try {
      const cleanEmail = email.trim();
      const cleanPhone = phone.trim();
      const payload: StaffCreatePayload = {
        full_name: fullName.trim(),
        username: username.trim().toLowerCase(),
        email: cleanEmail ? cleanEmail.toLowerCase() : undefined,
        phone: cleanPhone ? cleanPhone : undefined,
        password,
        confirm_password: confirmPassword,
        role: 'STAFF',
      };

      await staffService.createStaff(payload);
      alert('Staff account created successfully.');
      setIsCreateModalOpen(false);
      loadStaffData();
    } catch (err: any) {
      setFormError(getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleActive = async (user: User) => {
    const action = user.is_active ? 'deactivate' : 'activate';
    if (!window.confirm(`Are you sure you want to ${action} cashier account for ${user.full_name}?`)) {
      return;
    }

    try {
      if (user.is_active) {
        await staffService.deactivateStaff(user.id, 'Deactivated by store owner');
      } else {
        await staffService.activateStaff(user.id, 'Activated by store owner');
      }
      loadStaffData();
    } catch (err: any) {
      alert(`Status update failed: ${getErrorMessage(err)}`);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStaff) return;
    if (newPassword.length < 8) {
      setFormError('Password must be at least 8 characters.');
      return;
    }
    if (newPassword !== newConfirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }

    setIsSaving(true);
    try {
      await staffService.resetPassword(selectedStaff.id, newPassword);
      alert(`Password for ${selectedStaff.full_name} has been reset.`);
      setIsResetPasswordModalOpen(false);
      setSelectedStaff(null);
    } catch (err: any) {
      setFormError(getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  };

  const handleViewActivity = async (user: User) => {
    setSelectedStaff(user);
    setLoadingActivity(true);
    try {
      const act = await staffService.getActivity(user.id);
      setStaffActivity(act);
    } catch (err) {
      console.error('Failed to load staff activity', err);
    } finally {
      setLoadingActivity(false);
    }
  };

  const filteredStaff = staffList.filter((u) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      u.full_name.toLowerCase().includes(s) ||
      (u.username && u.username.toLowerCase().includes(s)) ||
      (u.email && u.email.toLowerCase().includes(s)) ||
      (u.phone && u.phone.includes(s))
    );
  });

  const handleConfirmRemoveStaff = async () => {
    if (!removingStaff || isRemoving) return;
    setIsRemoving(true);
    try {
      const res = await staffService.removeStaff(removingStaff.id);
      setNotification({
        type: 'success',
        message: res?.message || `Staff account '${removingStaff.full_name}' was removed successfully.`,
      });
      setRemovingStaff(null);
      await loadStaffData();
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: getErrorMessage(err) || 'Failed to remove staff account.',
      });
    } finally {
      setIsRemoving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Notification Banner */}
      {notification && (
        <div
          className={`flex items-center justify-between rounded-xl p-3.5 text-xs font-medium border ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          }`}
        >
          <span>{notification.message}</span>
          <button
            onClick={() => setNotification(null)}
            className="rounded p-1 text-zinc-500 hover:text-zinc-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Staff & Cashier Management
          </h2>
          <p className="text-xs text-zinc-500">
            Store Owner Control: Manage cashier accounts, configure security credentials, and audit sales activity.
          </p>
        </div>

        <button
          onClick={handleOpenCreateModal}
          className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
        >
          <Plus className="h-4 w-4" />
          <span>Create Staff Account</span>
        </button>
      </div>

      {/* Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
            <span className="text-xs font-semibold text-zinc-400">Total Staff</span>
            <p className="text-2xl font-bold text-zinc-900 mt-1">{metrics.total_staff}</p>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4 shadow-sm">
            <span className="text-xs font-semibold text-emerald-800">Active Cashiers</span>
            <p className="text-2xl font-bold text-emerald-700 mt-1">{metrics.active_staff}</p>
          </div>
          <div className="rounded-2xl border border-rose-200 bg-rose-50/50 p-4 shadow-sm">
            <span className="text-xs font-semibold text-rose-800">Inactive Accounts</span>
            <p className="text-2xl font-bold text-rose-600 mt-1">{metrics.inactive_staff}</p>
          </div>
          <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
            <span className="text-xs font-semibold text-zinc-400">Registered This Month</span>
            <p className="text-2xl font-bold text-zinc-900 mt-1">{metrics.created_this_month}</p>
          </div>
        </div>
      )}

      {/* Filter and Search */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search staff by full name, username, email, or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 py-2 text-xs focus:border-amber-500 focus:bg-white focus:outline-none"
          />
        </div>
      </div>

      {/* Staff Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading staff records...</p>
          </div>
        ) : filteredStaff.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No staff accounts found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Staff Member</th>
                  <th className="py-3 px-4">Username & Employee ID</th>
                  <th className="py-3 px-4">Contact</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Last Login</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filteredStaff.map((u) => (
                  <tr key={u.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">
                      <div>
                        <span>{u.full_name}</span>
                        {u.role === 'OWNER' && (
                          <span className="ml-1.5 rounded bg-amber-100 text-amber-800 px-1.5 py-0.2 text-[9px] font-bold">
                            OWNER
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <p className="font-semibold text-zinc-800 font-mono">{u.username || '—'}</p>
                      <p className="text-[10px] text-zinc-400 font-mono">{u.employee_id || '—'}</p>
                    </td>
                    <td className="py-3 px-4 text-zinc-600">
                      <p>{u.phone || 'No phone'}</p>
                      <p className="text-[11px] text-zinc-400">{u.email}</p>
                    </td>
                    <td className="py-3 px-4">
                      <span className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] font-bold text-zinc-700">
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-zinc-500">
                      {u.last_login_at ? formatDateTime(u.last_login_at) : 'Never'}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => u.role !== 'OWNER' && handleToggleActive(u)}
                        disabled={u.role === 'OWNER'}
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold transition-all ${
                          u.is_active
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                            : 'bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100'
                        } ${u.role === 'OWNER' ? 'cursor-default' : 'cursor-pointer'}`}
                      >
                        {u.is_active ? 'ACTIVE' : 'DEACTIVATED'}
                      </button>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => handleViewActivity(u)}
                          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
                          title="View Sales Activity & Performance"
                        >
                          <Activity className="h-4 w-4" />
                        </button>
                        {u.role !== 'OWNER' && (
                          <>
                            <button
                              onClick={() => {
                                setSelectedStaff(u);
                                setNewPassword('');
                                setNewConfirmPassword('');
                                setFormError(null);
                                setIsResetPasswordModalOpen(true);
                              }}
                              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-amber-600"
                              title="Reset Staff Password"
                            >
                              <KeyRound className="h-4 w-4" />
                            </button>
                            {canRemove && (
                              <button
                                onClick={() => setRemovingStaff(u)}
                                className="rounded-lg p-1.5 text-zinc-400 hover:bg-rose-50 hover:text-rose-600"
                                title="Remove Staff Account"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Staff Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="text-base font-bold text-zinc-900">Create Staff Cashier Account</h3>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateStaff} className="mt-4 space-y-3">
              {formError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Full Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Senthil Kumar"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Cashier Username *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. senthil"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. 9842100000"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Email Address (Optional)
                </label>
                <input
                  type="email"
                  placeholder="e.g. senthil@viyon.store"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Password (Min 8 chars) *
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Confirm Password *
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  disabled={isSaving}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 disabled:opacity-50"
                >
                  {isSaving ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {isResetPasswordModalOpen && selectedStaff && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-base font-bold text-zinc-900">
              Reset Password for {selectedStaff.full_name}
            </h3>
            <p className="text-xs text-zinc-500 mb-4">
              Enter a new secure password. Previously issued JWT sessions will be invalidated immediately.
            </p>

            {formError && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700 mb-3">
                {formError}
              </div>
            )}

            <form onSubmit={handleResetPassword} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  New Password (Min 8 chars) *
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Confirm New Password *
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newConfirmPassword}
                  onChange={(e) => setNewConfirmPassword(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsResetPasswordModalOpen(false)}
                  disabled={isSaving}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 disabled:opacity-50"
                >
                  {isSaving ? 'Updating...' : 'Set Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Staff Activity Modal */}
      {selectedStaff && staffActivity && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <div>
                <h3 className="text-base font-bold text-zinc-900">
                  Performance & Activity: {staffActivity.full_name}
                </h3>
                <p className="text-xs text-zinc-500">Employee ID: {staffActivity.employee_id}</p>
              </div>
              <button
                onClick={() => {
                  setSelectedStaff(null);
                  setStaffActivity(null);
                }}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="grid grid-cols-3 gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-center text-xs">
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Total Bills Attributed</span>
                  <p className="text-lg font-black text-zinc-900">{staffActivity.total_bills_count}</p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Completed Sales</span>
                  <p className="text-lg font-black text-emerald-600">{staffActivity.completed_bills_count}</p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Confirmed Sales Total</span>
                  <p className="text-lg font-black text-amber-600">
                    {formatCurrency(staffActivity.confirmed_sales_total)}
                  </p>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-bold text-zinc-900 mb-2">Recent Bills Generated</h4>
                <div className="rounded-xl border border-zinc-200 overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-600 border-b border-zinc-200 font-semibold">
                      <tr>
                        <th className="py-2 px-3">Bill Number</th>
                        <th className="py-2 px-3">Date</th>
                        <th className="py-2 px-3 text-right">Amount</th>
                        <th className="py-2 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {staffActivity.recent_bills?.map((b) => (
                        <tr key={b.id}>
                          <td className="py-2 px-3 font-bold text-zinc-900">{b.bill_number}</td>
                          <td className="py-2 px-3 text-zinc-500">{formatDateTime(b.created_at)}</td>
                          <td className="py-2 px-3 text-right font-bold text-zinc-900">
                            {formatCurrency(b.total_amount)}
                          </td>
                          <td className="py-2 px-3">
                            <span className="rounded bg-zinc-100 px-1.5 py-0.2 text-[10px] font-bold">
                              {b.bill_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="flex justify-end border-t border-zinc-200 bg-zinc-50 px-6 py-3">
              <button
                onClick={() => {
                  setSelectedStaff(null);
                  setStaffActivity(null);
                }}
                className="rounded-lg bg-zinc-900 px-4 py-1.5 text-xs font-bold text-white hover:bg-zinc-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Remove Staff Confirmation Modal */}
      {removingStaff && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600 mb-3">
              <div className="rounded-full bg-rose-50 p-2.5 border border-rose-100">
                <Trash2 className="h-6 w-6 text-rose-600" />
              </div>
              <div>
                <h3 className="text-base font-bold text-zinc-900">Delete Staff Account</h3>
                <p className="text-xs text-zinc-500">Confirm staff deletion</p>
              </div>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-1.5 text-xs mb-3">
              <div className="flex justify-between">
                <span className="text-zinc-500 font-medium">Full Name:</span>
                <span className="font-bold text-zinc-900">{removingStaff.full_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500 font-medium">Username:</span>
                <span className="font-mono font-semibold text-zinc-800">@{removingStaff.username}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500 font-medium">Email:</span>
                <span className="font-medium text-zinc-800">{removingStaff.email}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500 font-medium">Role:</span>
                <span className="font-bold text-zinc-800">{removingStaff.role}</span>
              </div>
              <div className="flex justify-between border-t border-zinc-200 pt-1.5">
                <span className="text-zinc-500 font-medium">Status:</span>
                <span className={`font-bold ${removingStaff.is_active ? 'text-emerald-700' : 'text-zinc-500'}`}>
                  {removingStaff.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            </div>

            <p className="text-xs text-zinc-500 mb-5 bg-zinc-50 p-3 rounded-xl border border-zinc-200 leading-relaxed">
              If this staff member has created historical bills, payments, expenses, or transactions, their account will be safely deactivated and session revoked to preserve sales and invoice history. If they have no transaction history, the account will be permanently deleted from the database.
            </p>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setRemovingStaff(null)}
                disabled={isRemoving}
                className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmRemoveStaff}
                disabled={isRemoving}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white shadow-md hover:bg-rose-500 disabled:opacity-50 transition-all"
              >
                {isRemoving ? (
                  <>
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Staff</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
