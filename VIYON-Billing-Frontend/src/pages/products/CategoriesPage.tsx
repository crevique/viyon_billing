import React, { useState, useEffect } from 'react';
import { FolderTree, Plus, Edit, Trash2, X, Check, Layers, AlertTriangle } from 'lucide-react';
import { Category, Subcategory } from '../../types';
import { productService } from '../../services/productService';
import { useAuthStore } from '../../stores/useAuthStore';

export const CategoriesPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';
  const canDelete = role === 'OWNER';

  const [categories, setCategories] = useState<Category[]>([]);
  const [subcategories, setSubcategories] = useState<Subcategory[]>([]);
  const [loading, setLoading] = useState(true);

  // Deletion & Notification State
  const [deletingCategory, setDeletingCategory] = useState<Category | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Category Modal
  const [isCatModalOpen, setIsCatModalOpen] = useState(false);
  const [catName, setCatName] = useState('');
  const [catDesc, setCatDesc] = useState('');
  const [editingCatId, setEditingCatId] = useState<string | null>(null);

  // Subcategory Modal
  const [isSubModalOpen, setIsSubModalOpen] = useState(false);
  const [subName, setSubName] = useState('');
  const [subCatParentId, setSubCatParentId] = useState('');

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    setLoading(true);
    try {
      const [cats, subcats] = await Promise.all([
        productService.getCategories(),
        productService.getSubcategories(),
      ]);
      setCategories(cats || []);
      setSubcategories(subcats || []);
    } catch (err) {
      console.error('Failed to load categories', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!catName.trim()) return;

    try {
      if (editingCatId) {
        await productService.updateCategory(editingCatId, {
          name: catName.trim(),
          description: catDesc.trim() || undefined,
        });
      } else {
        await productService.createCategory({
          name: catName.trim(),
          description: catDesc.trim() || undefined,
        });
      }
      setIsCatModalOpen(false);
      loadCategories();
    } catch (err: any) {
      alert(`Error saving category: ${err.message || 'Unknown error'}`);
    }
  };

  const handleSaveSubcategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subName.trim() || !subCatParentId) return;

    try {
      await productService.createSubcategory({
        category_id: subCatParentId,
        name: subName.trim(),
      });
      setIsSubModalOpen(false);
      setSubName('');
      loadCategories();
    } catch (err: any) {
      alert(`Error creating subcategory: ${err.message || 'Unknown error'}`);
    }
  };

  const handleConfirmDeleteCategory = async () => {
    if (!deletingCategory) return;
    setIsDeleting(true);
    setWarningMessage(null);
    try {
      const res = await productService.deleteCategory(deletingCategory.id);
      setNotification({
        type: 'success',
        message: res?.message || `Category "${deletingCategory.name}" was deleted successfully.`,
      });
      setDeletingCategory(null);
      await loadCategories();
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Failed to delete category.';
      setWarningMessage(detail);
    } finally {
      setIsDeleting(false);
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

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Categories & Subcategories
          </h2>
          <p className="text-xs text-zinc-500">
            Structure your clothing lines (Men's Formal, Casual, Ethnic, Kid's Wear, Accessories).
          </p>
        </div>

        {isOwner && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setSubName('');
                setSubCatParentId(categories[0]?.id || '');
                setIsSubModalOpen(true);
              }}
              className="flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3.5 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50"
            >
              <Layers className="h-4 w-4 text-zinc-500" />
              <span>Add Subcategory</span>
            </button>
            <button
              onClick={() => {
                setEditingCatId(null);
                setCatName('');
                setCatDesc('');
                setIsCatModalOpen(true);
              }}
              className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-3.5 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400"
            >
              <Plus className="h-4 w-4" />
              <span>Add Category</span>
            </button>
          </div>
        )}
      </div>

      {/* Categories Grid */}
      {loading ? (
        <div className="flex h-64 flex-col items-center justify-center gap-2">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
          <p className="text-xs text-zinc-400">Loading categories...</p>
        </div>
      ) : categories.length === 0 ? (
        <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center">
          <FolderTree className="h-10 w-10 text-zinc-300 mx-auto mb-2" />
          <p className="text-sm font-semibold text-zinc-700">No categories created</p>
          <p className="text-xs text-zinc-400">Create your primary product categories</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {categories.map((c) => {
            const childSubcats = subcategories.filter((s) => s.category_id === c.id);
            return (
              <div
                key={c.id}
                className="flex flex-col justify-between rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm hover:border-zinc-300 transition-all"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                        <FolderTree className="h-4 w-4" />
                      </div>
                      <h4 className="text-sm font-bold text-zinc-900">{c.name}</h4>
                    </div>
                    {isOwner && (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => {
                            setEditingCatId(c.id);
                            setCatName(c.name);
                            setCatDesc(c.description || '');
                            setIsCatModalOpen(true);
                          }}
                          className="rounded p-1 text-zinc-400 hover:text-zinc-700"
                          title="Edit Category"
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </button>
                        {canDelete && (
                          <button
                            onClick={() => {
                              setWarningMessage(null);
                              setDeletingCategory(c);
                            }}
                            className="rounded p-1 text-zinc-400 hover:text-rose-600"
                            title="Delete Category"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {c.description && (
                    <p className="text-xs text-zinc-500 mb-3">{c.description}</p>
                  )}

                  <div className="mt-3 border-t border-zinc-100 pt-3">
                    <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                      Subcategories ({childSubcats.length})
                    </span>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {childSubcats.length === 0 ? (
                        <span className="text-xs text-zinc-400 italic">None</span>
                      ) : (
                        childSubcats.map((s) => (
                          <span
                            key={s.id}
                            className="rounded-lg bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-700"
                          >
                            {s.name}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                <div className="mt-4 border-t border-zinc-100 pt-2 flex items-center justify-between text-xs text-zinc-400">
                  <span>Created {new Date(c.created_at).toLocaleDateString()}</span>
                  <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">
                    Active
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Category Modal */}
      {isCatModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="text-base font-bold text-zinc-900">
                {editingCatId ? 'Edit Category' : 'Create Category'}
              </h3>
              <button
                onClick={() => setIsCatModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSaveCategory} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Category Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Men's Shirts, Boys Trousers"
                  value={catName}
                  onChange={(e) => setCatName(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Description
                </label>
                <textarea
                  rows={2}
                  placeholder="Optional notes or details"
                  value={catDesc}
                  onChange={(e) => setCatDesc(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCatModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400"
                >
                  Save Category
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Subcategory Modal */}
      {isSubModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="text-base font-bold text-zinc-900">Add Subcategory</h3>
              <button
                onClick={() => setIsSubModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSaveSubcategory} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Parent Category *
                </label>
                <select
                  required
                  value={subCatParentId}
                  onChange={(e) => setSubCatParentId(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Subcategory Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Formal Shirts, Casual Polo"
                  value={subName}
                  onChange={(e) => setSubName(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsSubModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400"
                >
                  Add Subcategory
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Category Deletion Confirmation Modal */}
      {deletingCategory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600 mb-3">
              <div className="rounded-full bg-rose-50 p-2.5 border border-rose-100">
                <Trash2 className="h-6 w-6 text-rose-600" />
              </div>
              <div>
                <h3 className="text-base font-bold text-zinc-900">Delete Category</h3>
                <p className="text-xs text-zinc-500">Confirm category removal</p>
              </div>
            </div>

            <p className="text-sm text-zinc-700 font-medium mb-3">
              Are you sure you want to delete category <span className="font-bold text-zinc-900">"{deletingCategory.name}"</span>?
            </p>

            {warningMessage ? (
              <div className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 leading-relaxed">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-bold block mb-1">Deletion Blocked:</strong>
                    <span>{warningMessage}</span>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-zinc-500 mb-6 bg-zinc-50 p-3 rounded-xl border border-zinc-200 leading-relaxed">
                Categories can only be deleted if no products or subcategories reference them. If products exist, please reassign them first in Product Catalogue.
              </p>
            )}

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setDeletingCategory(null);
                  setWarningMessage(null);
                }}
                disabled={isDeleting}
                className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
              >
                {warningMessage ? 'Close' : 'Cancel'}
              </button>
              {!warningMessage && (
                <button
                  type="button"
                  onClick={handleConfirmDeleteCategory}
                  disabled={isDeleting}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white shadow-md hover:bg-rose-500 disabled:opacity-50"
                >
                  {isDeleting ? 'Deleting...' : 'Delete Category'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
