import React, { useState, useEffect } from 'react';
import { DailyCashRegister, formatINR } from './types';

interface CashManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export const CashManagementModal: React.FC<CashManagementModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [activeTab, setActiveTab] = useState<'REGISTER' | 'MOVEMENT' | 'CLOSE' | 'CORRECT'>('REGISTER');
  const [register, setRegister] = useState<DailyCashRegister | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Opening Form
  const [openingCash, setOpeningCash] = useState('');
  const [openingNotes, setOpeningNotes] = useState('');

  // Movement Form
  const [moveType, setMoveType] = useState<'INFLOW' | 'OUTFLOW'>('INFLOW');
  const [moveAmount, setMoveAmount] = useState('');
  const [moveReason, setMoveReason] = useState('');

  // Closing Form
  const [closingCash, setClosingCash] = useState('');
  const [closingNotes, setClosingNotes] = useState('');

  // Correction Form
  const [correctCash, setCorrectCash] = useState('');
  const [correctReason, setCorrectReason] = useState('');

  const todayStr = new Date().toISOString().split('T')[0];

  const fetchTodayRegister = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/finance/cash/${todayStr}`);
      if (res.ok) {
        const data = await res.json();
        setRegister(data);
        if (data.is_closed) {
          setCorrectCash(String(data.actual_closing_cash || ''));
        }
      } else {
        setRegister(null);
      }
    } catch (err) {
      console.error(err);
      setRegister(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchTodayRegister();
    }
  }, [isOpen]);

  const handleOpenRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const res = await fetch('/api/v1/finance/cash/opening', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_date: todayStr,
          opening_cash: parseFloat(openingCash || '0'),
          opening_notes: openingNotes.trim() || null,
        }),
      });
      if (res.ok) {
        fetchTodayRegister();
        if (onSuccess) onSuccess();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to open register.');
      }
    } catch {
      alert('Error connecting to server.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddMovement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!register) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/v1/finance/cash/${register.id}/movements`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          movement_type: moveType,
          amount: parseFloat(moveAmount),
          reason: moveReason.trim(),
        }),
      });
      if (res.ok) {
        setMoveAmount('');
        setMoveReason('');
        setActiveTab('REGISTER');
        fetchTodayRegister();
        if (onSuccess) onSuccess();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to record movement.');
      }
    } catch {
      alert('Error connecting to server.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!register) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/v1/finance/cash/${register.id}/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actual_closing_cash: parseFloat(closingCash),
          closing_notes: closingNotes.trim() || null,
        }),
      });
      if (res.ok) {
        fetchTodayRegister();
        setActiveTab('REGISTER');
        if (onSuccess) onSuccess();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to close register.');
      }
    } catch {
      alert('Error connecting to server.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCorrectRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!register || !correctReason.trim()) return;
    setActionLoading(true);
    try {
      const res = await fetch(`/api/v1/finance/cash/${register.id}/correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          actual_closing_cash: parseFloat(correctCash),
          correction_reason: correctReason.trim(),
        }),
      });
      if (res.ok) {
        fetchTodayRegister();
        setActiveTab('REGISTER');
        if (onSuccess) onSuccess();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to apply correction.');
      }
    } catch {
      alert('Error connecting to server.');
    } finally {
      setActionLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Modal Header */}
        <div className="flex justify-between items-center pb-4 border-b border-gray-100">
          <div>
            <h3 className="text-xl font-bold text-gray-900">Daily Cash Register</h3>
            <p className="text-xs text-gray-500">Business Date: {todayStr} (Asia/Kolkata)</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 rounded-lg p-1 text-lg font-bold"
          >
            &times;
          </button>
        </div>

        {/* Tab Navigation if register is active */}
        {register && (
          <div className="flex border-b border-gray-200 mt-4 text-xs font-semibold">
            <button
              onClick={() => setActiveTab('REGISTER')}
              className={`py-2 px-4 border-b-2 ${
                activeTab === 'REGISTER'
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Overview
            </button>
            {!register.is_closed && (
              <>
                <button
                  onClick={() => setActiveTab('MOVEMENT')}
                  className={`py-2 px-4 border-b-2 ${
                    activeTab === 'MOVEMENT'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Cash In / Out
                </button>
                <button
                  onClick={() => setActiveTab('CLOSE')}
                  className={`py-2 px-4 border-b-2 ${
                    activeTab === 'CLOSE'
                      ? 'border-indigo-600 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Close Day
                </button>
              </>
            )}
            {register.is_closed && (
              <button
                onClick={() => setActiveTab('CORRECT')}
                className={`py-2 px-4 border-b-2 ${
                  activeTab === 'CORRECT'
                    ? 'border-indigo-600 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                Owner Correction
              </button>
            )}
          </div>
        )}

        {/* Body Content */}
        <div className="mt-5">
          {loading ? (
            <div className="py-12 text-center text-gray-500 text-sm">Loading cash drawer state...</div>
          ) : !register ? (
            /* Uninitialized - Prompt to Open */
            <div className="text-center py-6">
              <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h4 className="text-base font-bold text-gray-900">Cash Drawer Not Initialized</h4>
              <p className="text-xs text-gray-500 max-w-sm mx-auto mt-1 mb-5">
                Record the physical opening cash balance to start billing and track daily cash reconciliation.
              </p>

              <form onSubmit={handleOpenRegister} className="max-w-xs mx-auto space-y-3 text-left">
                <div>
                  <label className="block text-xs font-medium text-gray-700">Opening Balance (INR) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="e.g. 5000.00"
                    value={openingCash}
                    onChange={(e) => setOpeningCash(e.target.value)}
                    className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700">Opening Notes</label>
                  <input
                    type="text"
                    placeholder="e.g. Verified by Store Manager"
                    value={openingNotes}
                    onChange={(e) => setOpeningNotes(e.target.value)}
                    className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2"
                  />
                </div>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="w-full mt-2 py-2 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm"
                >
                  {actionLoading ? 'Initializing...' : 'Open Cash Drawer'}
                </button>
              </form>
            </div>
          ) : activeTab === 'REGISTER' ? (
            /* Register Overview */
            <div className="space-y-4">
              <div className="flex justify-between items-center bg-gray-50 p-3 rounded-lg border border-gray-200">
                <div>
                  <span className="text-xs font-semibold text-gray-500 uppercase">Register Status</span>
                  <p className="text-sm font-bold text-gray-900 mt-0.5">{register.status}</p>
                </div>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold ${
                    register.is_closed ? 'bg-gray-200 text-gray-800' : 'bg-emerald-100 text-emerald-800'
                  }`}
                >
                  {register.is_closed ? 'CLOSED' : 'OPEN'}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <span className="text-gray-500">Opening Cash</span>
                  <p className="text-base font-bold text-gray-900 mt-1">{formatINR(register.opening_cash)}</p>
                </div>
                <div className="p-3 bg-emerald-50/50 rounded-lg border border-emerald-100">
                  <span className="text-emerald-700 font-medium">+ Cash Sales</span>
                  <p className="text-base font-bold text-emerald-800 mt-1">{formatINR(register.cash_sales)}</p>
                </div>
                <div className="p-3 bg-blue-50/50 rounded-lg border border-blue-100">
                  <span className="text-blue-700 font-medium">+ Cash Inflow</span>
                  <p className="text-base font-bold text-blue-800 mt-1">{formatINR(register.other_cash_inflow)}</p>
                </div>
                <div className="p-3 bg-red-50/50 rounded-lg border border-red-100">
                  <span className="text-red-700 font-medium">- Cash Outflow</span>
                  <p className="text-base font-bold text-red-800 mt-1">
                    {formatINR(Number(register.cash_expenses) + Number(register.other_cash_outflow))}
                  </p>
                </div>
              </div>

              <div className="p-4 bg-indigo-50 border border-indigo-100 rounded-xl flex justify-between items-center">
                <div>
                  <span className="text-xs font-bold text-indigo-900 uppercase tracking-wider">
                    Expected Drawer Cash
                  </span>
                  <p className="text-2xl font-black text-indigo-950 mt-0.5">
                    {formatINR(register.expected_closing_cash)}
                  </p>
                </div>
                {register.is_closed && (
                  <div className="text-right">
                    <span className="text-xs font-semibold text-gray-600">Counted Cash: {formatINR(register.actual_closing_cash)}</span>
                    <p className={`text-sm font-bold mt-0.5 ${Number(register.cash_difference || 0) < 0 ? 'text-red-600' : 'text-emerald-700'}`}>
                      Variance: {formatINR(register.cash_difference)}
                    </p>
                  </div>
                )}
              </div>

              {/* Auxiliary Movements List */}
              <div>
                <h5 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Auxiliary Movements</h5>
                {register.movements.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">No manual cash injections or withdrawals recorded today.</p>
                ) : (
                  <div className="space-y-1.5 max-h-36 overflow-y-auto">
                    {register.movements.map((m) => (
                      <div key={m.id} className="flex justify-between items-center text-xs p-2 bg-gray-50 rounded border border-gray-100">
                        <div>
                          <span className={`font-bold mr-2 ${m.movement_type === 'INFLOW' ? 'text-emerald-700' : 'text-red-600'}`}>
                            {m.movement_type}
                          </span>
                          <span className="text-gray-700">{m.reason}</span>
                        </div>
                        <span className="font-bold text-gray-900">{formatINR(m.amount)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : activeTab === 'MOVEMENT' ? (
            /* Record Cash In / Out */
            <form onSubmit={handleAddMovement} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700">Movement Direction *</label>
                <div className="grid grid-cols-2 gap-3 mt-1">
                  <button
                    type="button"
                    onClick={() => setMoveType('INFLOW')}
                    className={`py-2 text-xs font-bold rounded-lg border ${
                      moveType === 'INFLOW' ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-white text-gray-700 border-gray-300'
                    }`}
                  >
                    + Cash Inflow (Top-up)
                  </button>
                  <button
                    type="button"
                    onClick={() => setMoveType('OUTFLOW')}
                    className={`py-2 text-xs font-bold rounded-lg border ${
                      moveType === 'OUTFLOW' ? 'bg-red-600 text-white border-red-600' : 'bg-white text-gray-700 border-gray-300'
                    }`}
                  >
                    - Cash Outflow (Draw)
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Amount (INR) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  placeholder="0.00"
                  value={moveAmount}
                  onChange={(e) => setMoveAmount(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Reason / Reference *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Owner bank withdrawal for cash change"
                  value={moveReason}
                  onChange={(e) => setMoveReason(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setActiveTab('REGISTER')}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg font-semibold shadow-sm"
                >
                  {actionLoading ? 'Saving...' : 'Record Movement'}
                </button>
              </div>
            </form>
          ) : activeTab === 'CLOSE' ? (
            /* Close Drawer */
            <form onSubmit={handleCloseRegister} className="space-y-4">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                Expected physical closing cash: <span className="font-bold">{formatINR(register.expected_closing_cash)}</span>.
                Count all currency in the physical cash drawer and enter below.
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Actual Counted Cash (INR) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  placeholder="0.00"
                  value={closingCash}
                  onChange={(e) => setClosingCash(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 font-bold text-lg text-gray-900"
                />
                {closingCash && (
                  <p className="text-xs mt-1 text-gray-500">
                    Calculated Variance:{' '}
                    <span
                      className={`font-bold ${
                        parseFloat(closingCash) - Number(register.expected_closing_cash) < 0
                          ? 'text-red-600'
                          : 'text-emerald-700'
                      }`}
                    >
                      {formatINR(parseFloat(closingCash) - Number(register.expected_closing_cash))}
                    </span>
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Closing Notes</label>
                <textarea
                  rows={2}
                  placeholder="Notes on discrepancy, coin shortages, etc..."
                  value={closingNotes}
                  onChange={(e) => setClosingNotes(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setActiveTab('REGISTER')}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || !closingCash}
                  className="px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg font-semibold shadow-sm"
                >
                  {actionLoading ? 'Closing...' : 'Confirm Closing'}
                </button>
              </div>
            </form>
          ) : (
            /* Owner Correction */
            <form onSubmit={handleCorrectRegister} className="space-y-4">
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">
                This register is closed. Corrections modify the recorded physical count and are strictly logged in the audit trail.
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Corrected Physical Cash Count *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={correctCash}
                  onChange={(e) => setCorrectCash(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 font-bold text-gray-900"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Mandatory Correction Reason *</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Explain why the physical count was corrected (e.g. Bundled notes misplaced in back drawer)..."
                  value={correctReason}
                  onChange={(e) => setCorrectReason(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setActiveTab('REGISTER')}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-lg"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || !correctReason.trim()}
                  className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg font-semibold shadow-sm"
                >
                  {actionLoading ? 'Saving...' : 'Apply Audited Correction'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
