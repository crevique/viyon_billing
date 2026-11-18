import React, { useState, useEffect } from 'react';
import { Truck, Plus, Search, Phone, Mail, Building, Edit, X, RefreshCw } from 'lucide-react';
import { Supplier } from '../../types';
import { supplierService, CreateSupplierPayload } from '../../services/supplierService';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

export const SuppliersPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';

  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form
  const [companyName, setCompanyName] = useState('');
  const [contactPerson, setContactPerson] = useState('');
  const [phone, setPhone] = useState('');
  const [alternatePhone, setAlternatePhone] = useState('');
  const [email, setEmail] = useState('');
  const [gstin, setGstin] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('Sathyamangalam');
  const [state, setState] = useState('Tamil Nadu');
  const [pincode, setPincode] = useState('638402');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    loadSuppliers();
  }, []);

  const loadSuppliers = async () => {
    setLoading(true);
    try {
      const res = await supplierService.getSuppliers({ search: search.trim() || undefined });
      setSuppliers(res.items || []);
    } catch (err) {
      console.error('Failed to load suppliers', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateModal = (supp?: Supplier) => {
    if (supp) {
      setEditingSupplier(supp);
      setCompanyName(supp.company_name);
      setContactPerson(supp.contact_person || '');
      setPhone(supp.phone);
      setAlternatePhone(supp.alternate_phone || '');
      setEmail(supp.email || '');
      setGstin(supp.gstin || '');
      setAddress(supp.address || '');
      setCity(supp.city || '');
      setState(supp.state || '');
      setPincode(supp.pincode || '');
      setNotes(supp.notes || '');
    } else {
      setEditingSupplier(null);
      setCompanyName('');
      setContactPerson('');
      setPhone('');
      setAlternatePhone('');
      setEmail('');
      setGstin('');
      setAddress('');
      setCity('Sathyamangalam');
      setState('Tamil Nadu');
      setPincode('638402');
      setNotes('');
    }
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleSaveSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!companyName.trim()) {
      setFormError('Company name is required.');
      return;
    }
    if (!phone.trim() || phone.trim().length < 7) {
      setFormError('Valid phone number (minimum 7 digits) is required.');
      return;
    }
    if (gstin && gstin.trim().length !== 15) {
      setFormError('GSTIN must be exactly 15 characters.');
      return;
    }

    setIsSaving(true);
    try {
      const payload: CreateSupplierPayload = {
        company_name: companyName.trim(),
        contact_person: contactPerson.trim() || undefined,
        phone: phone.trim(),
        alternate_phone: alternatePhone.trim() || undefined,
        email: email.trim() || undefined,
        gstin: gstin.trim().toUpperCase() || undefined,
        address: address.trim() || undefined,
        city: city.trim() || undefined,
        state: state.trim() || undefined,
        pincode: pincode.trim() || undefined,
        notes: notes.trim() || undefined,
      };

      if (editingSupplier) {
        await supplierService.updateSupplier(editingSupplier.id, payload);
      } else {
        await supplierService.createSupplier(payload);
      }

      setIsModalOpen(false);
      loadSuppliers();
    } catch (err: any) {
      setFormError(err.message || 'Failed to save supplier.');
    } finally {
      setIsSaving(false);
    }
  };

  const filteredSuppliers = suppliers.filter((s) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      s.company_name.toLowerCase().includes(term) ||
      (s.contact_person && s.contact_person.toLowerCase().includes(term)) ||
      s.phone.includes(term) ||
      (s.gstin && s.gstin.toLowerCase().includes(term))
    );
  });

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Supplier & Vendor Directory
          </h2>
          <p className="text-xs text-zinc-500">
            Manage fabric mills, garment manufacturers, contact details, GSTIN, and outstanding balances.
          </p>
        </div>

        {isOwner && (
          <button
            onClick={() => handleOpenCreateModal()}
            className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
          >
            <Plus className="h-4 w-4" />
            <span>Add Supplier</span>
          </button>
        )}
      </div>

      {/* Filter and Search */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder="Search suppliers by company name, contact, phone, or GSTIN..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 py-2 text-xs focus:border-amber-500 focus:bg-white focus:outline-none"
          />
        </div>
      </div>

      {/* Suppliers Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading suppliers...</p>
          </div>
        ) : filteredSuppliers.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No suppliers found. Click "Add Supplier" to register your vendor contacts.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Supplier / Vendor</th>
                  <th className="py-3 px-4">Contact Person</th>
                  <th className="py-3 px-4">Phone & Email</th>
                  <th className="py-3 px-4">GSTIN</th>
                  <th className="py-3 px-4 text-right">Goods Received</th>
                  <th className="py-3 px-4 text-right">Total Paid</th>
                  <th className="py-3 px-4 text-right">Outstanding Liability</th>
                  {isOwner && <th className="py-3 px-4 text-center">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filteredSuppliers.map((s) => (
                  <tr key={s.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">
                      <div>
                        <span>{s.company_name}</span>
                        {s.city && <p className="text-[11px] text-zinc-400 font-normal">{s.city}, {s.state}</p>}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-zinc-700">{s.contact_person || '—'}</td>
                    <td className="py-3 px-4 text-zinc-600">
                      <div className="space-y-0.5">
                        <p className="flex items-center gap-1">
                          <Phone className="h-3 w-3 text-zinc-400" />
                          <span>{s.phone}</span>
                        </p>
                        {s.email && (
                          <p className="flex items-center gap-1 text-[11px] text-zinc-400">
                            <Mail className="h-3 w-3 text-zinc-400" />
                            <span>{s.email}</span>
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-500">{s.gstin || '—'}</td>
                    <td className="py-3 px-4 text-right font-medium text-zinc-900">
                      {formatCurrency(s.total_goods_received_value)}
                    </td>
                    <td className="py-3 px-4 text-right font-medium text-emerald-600">
                      {formatCurrency(s.total_paid)}
                    </td>
                    <td className="py-3 px-4 text-right font-bold text-amber-700">
                      {formatCurrency(s.outstanding_balance)}
                    </td>
                    {isOwner && (
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => handleOpenCreateModal(s)}
                          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
                          title="Edit Supplier"
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Supplier Create / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[92vh] w-full max-w-xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <h3 className="text-base font-bold text-zinc-900">
                {editingSupplier ? 'Edit Supplier' : 'Register New Supplier'}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSaveSupplier} className="flex-1 overflow-y-auto p-6 space-y-4">
              {formError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Supplier / Company Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Tirupur Cotton Mills Pvt Ltd"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Contact Person Name
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Ramesh Kumar"
                    value={contactPerson}
                    onChange={(e) => setContactPerson(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Primary Contact Phone *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 9842100000"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    placeholder="e.g. orders@tirupurtextiles.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    GSTIN (15 Characters)
                  </label>
                  <input
                    type="text"
                    maxLength={15}
                    placeholder="e.g. 33AAAAA0000A1Z5"
                    value={gstin}
                    onChange={(e) => setGstin(e.target.value.toUpperCase())}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-mono focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Street Address
                </label>
                <textarea
                  rows={2}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[11px] font-semibold text-zinc-700 mb-1">City</label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-zinc-700 mb-1">State</label>
                  <input
                    type="text"
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-zinc-700 mb-1">PIN Code</label>
                  <input
                    type="text"
                    value={pincode}
                    onChange={(e) => setPincode(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-2.5 py-1.5 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex gap-2 border-t border-zinc-200 pt-4">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={isSaving}
                  className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 rounded-xl bg-amber-500 py-2.5 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 disabled:opacity-50"
                >
                  {isSaving ? 'Saving...' : editingSupplier ? 'Update Supplier' : 'Save Supplier'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
