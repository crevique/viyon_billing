import React, { useState } from 'react';
import { Store, Printer, Shield, Save, Check } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [storeName, setStoreName] = useState('VIYON');
  const [tagline, setTagline] = useState("MEN'S COLLECTIONS");
  const [address, setAddress] = useState('F6WR+R8W, South Rangasamuthram, Sathyamangalam, Tamil Nadu - 638402');
  const [phone, setPhone] = useState('082702 42681');
  const [gstin, setGstin] = useState('33AAAAA0000A1Z5');
  const [receiptFooter, setReceiptFooter] = useState('Thank you for shopping at VIYON! Visit again.');
  const [printerWidth, setPrinterWidth] = useState('58');
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
          Store & POS Settings
        </h2>
        <p className="text-xs text-zinc-500">
          Configure store business profile, billing receipt headers, and thermal print parameters.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Store Profile Card */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-100 pb-3">
            <Store className="h-5 w-5 text-amber-500" />
            <h3 className="text-sm font-bold text-zinc-900">Retail Store Profile</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">
                Store Name *
              </label>
              <input
                type="text"
                required
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs font-bold text-zinc-900 focus:border-amber-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">
                Tagline / Subtitle
              </label>
              <input
                type="text"
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-700 mb-1">
              Store Physical Address
            </label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">
                Contact Phone
              </label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">
                GSTIN Tax Identification
              </label>
              <input
                type="text"
                value={gstin}
                onChange={(e) => setGstin(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs font-mono focus:border-amber-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Thermal Receipt Settings */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-100 pb-3">
            <Printer className="h-5 w-5 text-amber-500" />
            <h3 className="text-sm font-bold text-zinc-900">58mm Thermal Print Configuration</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">
                Paper Width (mm)
              </label>
              <select
                value={printerWidth}
                onChange={(e) => setPrinterWidth(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs text-zinc-800"
              >
                <option value="58">58mm (32 Monospace Columns)</option>
                <option value="80">80mm (48 Monospace Columns)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">
                Receipt Footer Notice
              </label>
              <input
                type="text"
                value={receiptFooter}
                onChange={(e) => setReceiptFooter(e.target.value)}
                className="w-full rounded-xl border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900">
            <strong>Thermal Hardware Status:</strong> Physical ESC/POS Bluetooth/USB communication hardware test pending. Browser print layout is calibrated to 32 characters.
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          {saved && (
            <span className="flex items-center gap-1 text-xs font-bold text-emerald-600">
              <Check className="h-4 w-4" />
              <span>Settings saved!</span>
            </span>
          )}
          <button
            type="submit"
            className="flex items-center gap-2 rounded-xl bg-amber-500 px-6 py-2.5 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 active:scale-95"
          >
            <Save className="h-4 w-4" />
            <span>Save Settings</span>
          </button>
        </div>
      </form>
    </div>
  );
};
