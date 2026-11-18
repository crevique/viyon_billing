import React, { useState, useEffect } from 'react';
import {
  Package,
  Plus,
  Search,
  Archive,
  RotateCcw,
  Edit,
  Trash2,
  AlertTriangle,
  X,
  Boxes,
  Check,
} from 'lucide-react';
import { Category, Product, ProductCreatePayload, Subcategory } from '../../types';
import { productService } from '../../services/productService';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

export const ProductsPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';
  const canDelete = role === 'OWNER';

  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [subcategories, setSubcategories] = useState<Subcategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [includeArchived, setIncludeArchived] = useState(false);

  // Deletion & Notification State
  const [deletingProduct, setDeletingProduct] = useState<Product | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Form State
  const [productType, setProductType] = useState<'SIMPLE' | 'VARIANT'>('SIMPLE');
  const [productName, setProductName] = useState('');
  const [productCode, setProductCode] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [subcategoryId, setSubcategoryId] = useState('');
  const [brand, setBrand] = useState('VIYON');
  const [basePrice, setBasePrice] = useState('');
  const [costPrice, setCostPrice] = useState('');
  const [description, setDescription] = useState('');
  const [imageUrl, setImageUrl] = useState('');

  // Simple product fields
  const [sku, setSku] = useState('');
  const [barcode, setBarcode] = useState('');
  const [initialStock, setInitialStock] = useState('0');
  const [lowStockThreshold, setLowStockThreshold] = useState('5');

  // Variant product fields
  interface VariantRowItem {
    id?: string;
    size: string;
    color: string;
    sku: string;
    barcode?: string;
    price_override?: number;
    initial_stock: number;
    low_stock_threshold: number;
    isCustomInput?: boolean;
    isExisting?: boolean;
  }

  const PRESET_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL', '5XL', 'Free Size'];

  const generateVariantSku = (size: string, existingList: { sku: string }[]): string => {
    const sizeUpper = (size || '').trim().toUpperCase();
    const cleanSize = sizeUpper === 'FREE SIZE' ? 'FS' : sizeUpper.replace(/\s+/g, '').replace(/[^A-Z0-9]/g, '');
    const existingSet = new Set(existingList.map((v) => (v.sku || '').toUpperCase()));
    let candidate = '';
    let attempts = 0;
    do {
      const randomSuffix = Math.floor(1000 + Math.random() * 9000);
      candidate = `VIY-${cleanSize || 'VAR'}-${randomSuffix}`;
      attempts++;
    } while (existingSet.has(candidate) && attempts < 100);
    return candidate;
  };

  const [variantList, setVariantList] = useState<VariantRowItem[]>([
    { size: 'S', color: 'Standard', sku: '', initial_stock: 5, low_stock_threshold: 2 },
    { size: 'M', color: 'Standard', sku: '', initial_stock: 10, low_stock_threshold: 3 },
    { size: 'L', color: 'Standard', sku: '', initial_stock: 10, low_stock_threshold: 3 },
    { size: 'XL', color: 'Standard', sku: '', initial_stock: 5, low_stock_threshold: 2 },
  ]);

  useEffect(() => {
    loadData();
  }, [includeArchived, selectedCategory]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [prods, cats, subcats] = await Promise.all([
        productService.getProducts({
          page_size: 100,
          category_id: selectedCategory || undefined,
          include_archived: includeArchived,
        }),
        productService.getCategories(),
        productService.getSubcategories(),
      ]);
      setProducts(prods.items || []);
      setCategories(cats || []);
      setSubcategories(subcats || []);
    } catch (err) {
      console.error('Failed to load products', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingProduct(null);
    setProductName('');
    setProductCode('');
    setCategoryId(categories[0]?.id || '');
    setSubcategoryId('');
    setBrand('VIYON');
    setProductType('SIMPLE');
    setBasePrice('');
    setCostPrice('');
    setDescription('');
    setImageUrl('');
    setSku(`VIY-${Date.now().toString().slice(-6)}`);
    setBarcode('');
    setInitialStock('10');
    setLowStockThreshold('5');

    // Default sizes preserved: S, M, L, XL
    const defaultInit: VariantRowItem[] = [];
    const defaultSizes = ['S', 'M', 'L', 'XL'];
    const defaultQtys = [5, 10, 10, 5];
    const defaultThresholds = [2, 3, 3, 2];

    defaultSizes.forEach((s, idx) => {
      const generatedSku = generateVariantSku(s, defaultInit);
      defaultInit.push({
        size: s,
        color: 'Standard',
        sku: generatedSku,
        initial_stock: defaultQtys[idx],
        low_stock_threshold: defaultThresholds[idx],
        isExisting: false,
      });
    });

    setVariantList(defaultInit);
    setFormError(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = async (product: Product) => {
    setEditingProduct(product);
    setProductName(product.product_name);
    setProductCode(product.product_code || '');
    setCategoryId(product.category_id);
    setSubcategoryId(product.subcategory_id || '');
    setBrand(product.brand || 'VIYON');
    setProductType(product.product_type);
    setBasePrice(String(product.base_price));
    setCostPrice(product.cost_price ? String(product.cost_price) : '');
    setDescription(product.description || '');
    setImageUrl(product.product_image_url || '');
    setSku(product.sku || '');
    setBarcode(product.barcode || '');
    setInitialStock(String(product.current_stock || 0));
    setLowStockThreshold('5');

    if (product.product_type === 'VARIANT') {
      try {
        const fresh = await productService.getProductById(product.id);
        setVariantList(
          (fresh.variants || []).map((v) => ({
            id: v.id,
            size: v.size,
            color: v.color || 'Standard',
            sku: v.sku,
            barcode: v.barcode || '',
            initial_stock: v.current_stock ?? 0,
            low_stock_threshold: v.low_stock_threshold ?? 3,
            isExisting: true,
          }))
        );
      } catch {
        setVariantList(
          (product.variants || []).map((v) => ({
            id: v.id,
            size: v.size,
            color: v.color || 'Standard',
            sku: v.sku,
            barcode: v.barcode || '',
            initial_stock: v.current_stock ?? 0,
            low_stock_threshold: v.low_stock_threshold ?? 3,
            isExisting: true,
          }))
        );
      }
    } else {
      setVariantList([]);
    }

    setFormError(null);
    setIsModalOpen(true);
  };

  const handleAddSizeClick = (sizeToSelect?: string) => {
    setFormError(null);
    const existingSizesUpper = new Set(variantList.map((v) => v.size.trim().toUpperCase()));
    const candidateSizes = ['XXL', '3XL', 'XS', '4XL', '5XL', 'Free Size'];
    let chosenSize = sizeToSelect?.trim() || '';
    let isCustom = false;

    if (!chosenSize) {
      const found = candidateSizes.find((s) => !existingSizesUpper.has(s.toUpperCase()));
      if (found) {
        chosenSize = found;
      } else {
        chosenSize = '';
        isCustom = true;
      }
    } else if (chosenSize === 'CUSTOM') {
      chosenSize = '';
      isCustom = true;
    } else {
      if (existingSizesUpper.has(chosenSize.toUpperCase())) {
        setFormError(`Size "${chosenSize}" is already added to this product.`);
        return;
      }
    }

    const newSku = generateVariantSku(chosenSize || 'CUST', variantList);

    setVariantList((prev) => [
      ...prev,
      {
        size: chosenSize,
        color: 'Standard',
        sku: newSku,
        initial_stock: 0, // Newly added sizes default to quantity 0!
        low_stock_threshold: 3,
        isCustomInput: isCustom,
        isExisting: false,
      },
    ]);
  };

  const handleSizeChange = (index: number, newSize: string) => {
    const trimmed = newSize.trim();
    const existingSizesUpper = new Set(
      variantList.filter((_, idx) => idx !== index).map((v) => v.size.trim().toUpperCase())
    );

    if (trimmed && existingSizesUpper.has(trimmed.toUpperCase())) {
      setFormError(`Size "${trimmed}" is already used in another variation.`);
    } else {
      setFormError(null);
    }

    setVariantList((prev) => {
      const updated = [...prev];
      const current = { ...updated[index] };
      const oldSize = current.size;
      current.size = newSize;

      const oldClean = oldSize.trim().toUpperCase() === 'FREE SIZE' ? 'FS' : oldSize.trim().toUpperCase().replace(/\s+/g, '').replace(/[^A-Z0-9]/g, '');
      const isAutoSku = !current.sku || (current.sku.startsWith('VIY-') && (
        (oldClean && current.sku.includes(`-${oldClean}-`)) ||
        current.sku.includes('-VAR-') ||
        current.sku.includes('-CUST-')
      ));
      if (isAutoSku && trimmed) {
        current.sku = generateVariantSku(trimmed, updated.filter((_, idx) => idx !== index));
      }

      updated[index] = current;
      return updated;
    });
  };

  const handleToggleCustomInput = (index: number, isCustom: boolean) => {
    setVariantList((prev) => {
      const updated = [...prev];
      updated[index] = {
        ...updated[index],
        isCustomInput: isCustom,
        size: isCustom ? '' : (updated[index].size || 'M'),
      };
      return updated;
    });
  };

  const handleSkuChange = (index: number, newSku: string) => {
    setVariantList((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], sku: newSku };
      return updated;
    });
  };

  const handleQtyChange = (index: number, newQty: number) => {
    setVariantList((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], initial_stock: Math.max(0, newQty) };
      return updated;
    });
  };

  const handleRemoveVariant = (index: number) => {
    setVariantList((prev) => prev.filter((_, idx) => idx !== index));
    setFormError(null);
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!productName.trim()) {
      setFormError('Product Name is required.');
      return;
    }
    if (!categoryId) {
      setFormError('Category must be selected.');
      return;
    }
    if (!basePrice || parseFloat(basePrice) < 0) {
      setFormError('Base price must be a valid non-negative number.');
      return;
    }
    if (subcategoryId) {
      const validSubcat = subcategories.find(
        (s) => s.id === subcategoryId && s.category_id === categoryId
      );
      if (!validSubcat) {
        setFormError('Selected subcategory does not belong to the selected category.');
        return;
      }
    }

    // Validate Variations if product is VARIANT type
    if (productType === 'VARIANT') {
      if (variantList.length === 0) {
        setFormError('At least one size variation is required for variant products.');
        return;
      }
      const seenSizes = new Set<string>();
      const seenSkus = new Set<string>();

      for (let i = 0; i < variantList.length; i++) {
        const v = variantList[i];
        const s = v.size.trim();
        const k = v.sku.trim();

        if (!s) {
          setFormError(`Variation #${i + 1}: Size cannot be empty.`);
          return;
        }
        if (!k) {
          setFormError(`Variation #${i + 1} (${s}): SKU cannot be empty.`);
          return;
        }

        const sUpper = s.toUpperCase();
        if (seenSizes.has(sUpper)) {
          setFormError(`Duplicate size "${s}" detected. Each variation must have a unique size.`);
          return;
        }
        seenSizes.add(sUpper);

        const kUpper = k.toUpperCase();
        if (seenSkus.has(kUpper)) {
          setFormError(`Duplicate SKU "${k}" detected in variation rows.`);
          return;
        }
        seenSkus.add(kUpper);
      }
    }

    setIsSaving(true);
    try {
      if (editingProduct) {
        // 1. Update product details
        await productService.updateProduct(editingProduct.id, {
          product_name: productName.trim(),
          product_code: productCode.trim() || undefined,
          category_id: categoryId,
          subcategory_id: subcategoryId || undefined,
          brand: brand.trim() || undefined,
          base_price: parseFloat(basePrice),
          cost_price: costPrice ? parseFloat(costPrice) : undefined,
          description: description.trim() || undefined,
          product_image_url: imageUrl.trim() || undefined,
          sku: productType === 'SIMPLE' ? sku.trim() : undefined,
          barcode: productType === 'SIMPLE' ? barcode.trim() || undefined : undefined,
        });

        // 2. Add newly added variants (if any)
        if (productType === 'VARIANT') {
          const newVariants = variantList.filter((v) => !v.id && !v.isExisting);
          for (const nv of newVariants) {
            await productService.addVariant(editingProduct.id, {
              size: nv.size.trim(),
              color: nv.color.trim() || 'Standard',
              sku: nv.sku.trim(),
              barcode: nv.barcode?.trim() || undefined,
              initial_stock: nv.initial_stock || 0,
              low_stock_threshold: nv.low_stock_threshold || 3,
            });
          }
        }
      } else {
        // Create new product
        const payload: ProductCreatePayload = {
          product_name: productName.trim(),
          product_code: productCode.trim() || undefined,
          category_id: categoryId,
          subcategory_id: subcategoryId || undefined,
          brand: brand.trim() || undefined,
          product_type: productType,
          base_price: parseFloat(basePrice),
          cost_price: costPrice ? parseFloat(costPrice) : undefined,
          description: description.trim() || undefined,
          product_image_url: imageUrl.trim() || undefined,
          sku: productType === 'SIMPLE' ? sku.trim() : undefined,
          barcode: productType === 'SIMPLE' ? barcode.trim() || undefined : undefined,
          initial_stock: productType === 'SIMPLE' ? parseInt(initialStock) || 0 : undefined,
          low_stock_threshold: productType === 'SIMPLE' ? parseInt(lowStockThreshold) || 5 : undefined,
          variants:
            productType === 'VARIANT'
              ? variantList.map((v) => ({
                  size: v.size.trim(),
                  color: v.color.trim() || 'Standard',
                  sku: v.sku.trim(),
                  barcode: v.barcode?.trim() || undefined,
                  price_override: v.price_override,
                  initial_stock: v.initial_stock || 0,
                  low_stock_threshold: v.low_stock_threshold || 3,
                }))
              : undefined,
        };

        await productService.createProduct(payload);
      }

      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || err.message || 'Failed to save product.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleArchiveToggle = async (product: Product) => {
    try {
      if (product.is_archived) {
        await productService.restoreProduct(product.id);
      } else {
        await productService.archiveProduct(product.id);
      }
      loadData();
    } catch (err: any) {
      alert(`Action failed: ${err.message || 'Unknown error'}`);
    }
  };

  const handleConfirmDeleteProduct = async () => {
    if (!deletingProduct) return;
    setIsDeleting(true);
    try {
      const res = await productService.deleteProduct(deletingProduct.id);
      setNotification({
        type: 'success',
        message: res?.message || `Product "${deletingProduct.product_name}" removed successfully.`,
      });
      setDeletingProduct(null);
      await loadData();
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.response?.data?.detail || err.message || 'Failed to delete product.',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const filteredProducts = products.filter((p) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      p.product_name.toLowerCase().includes(s) ||
      (p.sku && p.sku.toLowerCase().includes(s)) ||
      (p.barcode && p.barcode.toLowerCase().includes(s)) ||
      (p.product_code && p.product_code.toLowerCase().includes(s))
    );
  });

  const totalVariantStock = variantList.reduce(
    (acc, v) => acc + (parseInt(String(v.initial_stock), 10) || 0),
    0
  );

  return (
    <div className="space-y-5">
      {/* Title & Add Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Product Catalogue
          </h2>
          <p className="text-xs text-zinc-500">
            Manage simple items, size variations, retail prices, style codes, and barcode mappings.
          </p>
        </div>

        {isOwner && (
          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
          >
            <Plus className="h-4 w-4" />
            <span>Add New Product</span>
          </button>
        )}
      </div>

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

      {/* Filter & Search Bar */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search products by title, SKU, or barcode..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 py-2 text-xs focus:border-amber-500 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700 focus:border-amber-500 focus:outline-none"
            >
              <option value="">All Categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>

            <label className="flex items-center gap-1.5 text-xs text-zinc-600 cursor-pointer">
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={(e) => setIncludeArchived(e.target.checked)}
                className="rounded border-zinc-300 text-amber-500 focus:ring-amber-500"
              />
              <span>Archived</span>
            </label>
          </div>
        </div>
      </div>

      {/* Products Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading catalog...</p>
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center text-center p-6">
            <Package className="h-10 w-10 text-zinc-300 mb-2" />
            <p className="text-sm font-semibold text-zinc-700">No products found</p>
            <p className="text-xs text-zinc-400">Add your first product or clear filters</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Product Name</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">SKU / Code</th>
                  <th className="py-3 px-4 text-right">Retail Price</th>
                  {isOwner && <th className="py-3 px-4 text-right">Cost Price</th>}
                  <th className="py-3 px-4 text-right">Available Stock</th>
                  <th className="py-3 px-4">Status</th>
                  {isOwner && <th className="py-3 px-4 text-center">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filteredProducts.map((p) => (
                  <tr key={p.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">
                      <div className="flex items-center gap-2.5">
                        <div className="h-9 w-9 rounded-lg bg-zinc-100 border border-zinc-200 shrink-0 overflow-hidden flex items-center justify-center">
                          {p.product_image_url ? (
                            <img src={p.product_image_url} alt="" className="h-full w-full object-cover" />
                          ) : (
                            <Package className="h-4 w-4 text-zinc-400" />
                          )}
                        </div>
                        <div>
                          <span>{p.product_name}</span>
                          {p.brand && <p className="text-[10px] text-zinc-400 font-normal">{p.brand}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-zinc-600">{p.category_name || '—'}</td>
                    <td className="py-3 px-4">
                      <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-bold text-zinc-700">
                        {p.product_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-500">
                      {p.sku || p.product_code || '—'}
                    </td>
                    <td className="py-3 px-4 text-right font-bold text-zinc-900">
                      {formatCurrency(p.base_price)}
                    </td>
                    {isOwner && (
                      <td className="py-3 px-4 text-right text-zinc-500">
                        {p.cost_price ? formatCurrency(p.cost_price) : '—'}
                      </td>
                    )}
                    <td className="py-3 px-4 text-right">
                      {p.product_type === 'VARIANT' ? (
                        <span className="rounded bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                          {p.variants.length} Sizes
                        </span>
                      ) : (
                        <span
                          className={`font-bold ${
                            (p.current_stock || 0) <= 0
                              ? 'text-rose-600'
                              : 'text-zinc-900'
                          }`}
                        >
                          {p.current_stock || 0}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {p.is_archived ? (
                        <span className="rounded bg-zinc-100 text-zinc-500 font-semibold px-2 py-0.5 text-[10px]">
                          Archived
                        </span>
                      ) : (
                        <span className="rounded bg-emerald-50 border border-emerald-200 text-emerald-700 font-bold px-2 py-0.5 text-[10px]">
                          Active
                        </span>
                      )}
                    </td>
                    {isOwner && (
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => handleOpenEditModal(p)}
                            className="rounded p-1 text-zinc-400 hover:text-amber-600 hover:bg-amber-50"
                            title="Edit Product & Sizes"
                          >
                            <Edit className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleArchiveToggle(p)}
                            className="rounded p-1 text-zinc-400 hover:text-zinc-700"
                            title={p.is_archived ? 'Restore' : 'Archive'}
                          >
                            {p.is_archived ? <RotateCcw className="h-4 w-4" /> : <Archive className="h-4 w-4" />}
                          </button>
                          {canDelete && (
                            <button
                              onClick={() => setDeletingProduct(p)}
                              className="rounded p-1 text-zinc-400 hover:text-rose-600"
                              title="Delete Product"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add / Edit Product Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <h3 className="text-base font-bold text-zinc-900">
                {editingProduct ? 'Edit Product' : 'Add New Product'}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSaveProduct} className="flex-1 overflow-y-auto p-6 space-y-4">
              {formError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                  {formError}
                </div>
              )}

              {/* Product Type (Simple vs Variant) */}
              {!editingProduct && (
                <div>
                  <label className="block text-xs font-bold text-zinc-700 mb-1">
                    Product Structure
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => setProductType('SIMPLE')}
                      className={`rounded-xl border p-3 text-left transition-all ${
                        productType === 'SIMPLE'
                          ? 'border-amber-500 bg-amber-50/60 font-bold text-amber-950'
                          : 'border-zinc-200 hover:bg-zinc-50 text-zinc-600'
                      }`}
                    >
                      <p className="text-xs">Simple Product</p>
                      <p className="text-[10px] text-zinc-400 font-normal">Single size, standalone SKU (e.g. Cap, Tie)</p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setProductType('VARIANT')}
                      className={`rounded-xl border p-3 text-left transition-all ${
                        productType === 'VARIANT'
                          ? 'border-amber-500 bg-amber-50/60 font-bold text-amber-950'
                          : 'border-zinc-200 hover:bg-zinc-50 text-zinc-600'
                      }`}
                    >
                      <p className="text-xs">Variant Product</p>
                      <p className="text-[10px] text-zinc-400 font-normal">Multi-size clothing (e.g. Shirts S/M/L/XL)</p>
                    </button>
                  </div>
                </div>
              )}

              {/* Basic Details */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Product Title *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Linen Slim Fit Shirt"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Product / Style Code
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. VYN-SH-101"
                    value={productCode}
                    onChange={(e) => setProductCode(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Category & Subcategory */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Category *
                  </label>
                  <select
                    required
                    value={categoryId}
                    onChange={(e) => {
                      const newCatId = e.target.value;
                      setCategoryId(newCatId);
                      setSubcategoryId('');
                    }}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                  >
                    <option value="">Select Category</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Subcategory (Optional)
                  </label>
                  {categoryId ? (
                    subcategories.filter((s) => s.category_id === categoryId).length > 0 ? (
                      <select
                        value={subcategoryId}
                        onChange={(e) => setSubcategoryId(e.target.value)}
                        className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                      >
                        <option value="">Select Subcategory</option>
                        {subcategories
                          .filter((s) => s.category_id === categoryId)
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                      </select>
                    ) : (
                      <div className="w-full rounded-lg border border-dashed border-zinc-300 px-3 py-2 text-xs text-zinc-400 bg-zinc-50 italic">
                        No subcategories available
                      </div>
                    )
                  ) : (
                    <div className="w-full rounded-lg border border-dashed border-zinc-200 px-3 py-2 text-xs text-zinc-400 bg-zinc-50">
                      Select a category first
                    </div>
                  )}
                </div>
              </div>

              {/* Brand */}
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Brand
                </label>
                <input
                  type="text"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              {/* Pricing */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Retail Selling Price (₹) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="e.g. 1499.00"
                    value={basePrice}
                    onChange={(e) => setBasePrice(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-semibold focus:border-amber-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Cost Price (₹) (Optional)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="e.g. 750.00"
                    value={costPrice}
                    onChange={(e) => setCostPrice(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Simple Product Identifiers */}
              {productType === 'SIMPLE' && (
                <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-3">
                  <h4 className="text-xs font-bold text-zinc-800">Inventory & Identifiers</h4>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">
                        SKU *
                      </label>
                      <input
                        type="text"
                        required
                        value={sku}
                        onChange={(e) => setSku(e.target.value)}
                        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-mono focus:border-amber-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-zinc-700 mb-1">
                        Barcode (EAN/UPC)
                      </label>
                      <input
                        type="text"
                        value={barcode}
                        onChange={(e) => setBarcode(e.target.value)}
                        className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs font-mono focus:border-amber-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  {!editingProduct && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-zinc-700 mb-1">
                          Initial Stock Quantity
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={initialStock}
                          onChange={(e) => setInitialStock(e.target.value)}
                          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-zinc-700 mb-1">
                          Low Stock Alert Threshold
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={lowStockThreshold}
                          onChange={(e) => setLowStockThreshold(e.target.value)}
                          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Variant Product Configuration */}
              {productType === 'VARIANT' && (
                <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3.5 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-zinc-200/80 pb-2.5">
                    <div>
                      <h4 className="text-xs font-bold text-zinc-800">
                        {editingProduct ? 'Product Variations' : 'Initial Variations'}
                      </h4>
                      <p className="text-[11px] text-zinc-500">
                        Total Stock:{' '}
                        <span className="font-bold text-zinc-800">{totalVariantStock} units</span> across{' '}
                        <span className="font-semibold text-zinc-700">{variantList.length} sizes</span>
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <select
                        onChange={(e) => {
                          if (e.target.value) {
                            handleAddSizeClick(e.target.value);
                            e.target.value = '';
                          }
                        }}
                        defaultValue=""
                        className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs font-semibold text-zinc-700 hover:border-amber-500 focus:outline-none"
                      >
                        <option value="" disabled>
                          + Quick Add Size...
                        </option>
                        {['XS', 'XXL', '3XL', '4XL', '5XL', 'Free Size'].map((sz) => {
                          const isAdded = variantList.some(
                            (v) => v.size.trim().toUpperCase() === sz.toUpperCase()
                          );
                          return (
                            <option key={sz} value={sz} disabled={isAdded}>
                              {sz} {isAdded ? '(added)' : ''}
                            </option>
                          );
                        })}
                        <option value="CUSTOM">+ Custom Size...</option>
                      </select>

                      <button
                        type="button"
                        onClick={() => handleAddSizeClick()}
                        className="flex items-center gap-1 rounded-lg bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold px-2.5 py-1 text-xs shadow-xs transition-all active:scale-95"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        <span>Add Size</span>
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                    {variantList.map((v, i) => (
                      <div
                        key={v.id || i}
                        className={`flex items-center gap-2 rounded-lg bg-white p-2 border text-xs shadow-2xs ${
                          v.isExisting ? 'border-zinc-200 bg-zinc-50/50' : 'border-zinc-200'
                        }`}
                      >
                        {/* Size Selection */}
                        <div className="w-28 shrink-0">
                          {v.isExisting ? (
                            <span className="inline-flex items-center justify-center font-bold text-xs rounded-md bg-zinc-900 text-white min-w-8 h-6 px-2">
                              {v.size}
                            </span>
                          ) : v.isCustomInput ? (
                            <div className="flex items-center gap-1">
                              <input
                                type="text"
                                placeholder="Size"
                                value={v.size}
                                autoFocus
                                onChange={(e) => handleSizeChange(i, e.target.value)}
                                className="w-full rounded border border-amber-400 bg-amber-50/20 px-1.5 py-1 text-xs font-bold text-zinc-900 focus:outline-none"
                              />
                              <button
                                type="button"
                                onClick={() => handleToggleCustomInput(i, false)}
                                className="text-[10px] text-zinc-400 hover:text-zinc-700 px-0.5"
                                title="Switch to size presets"
                              >
                                ✕
                              </button>
                            </div>
                          ) : (
                            <select
                              value={PRESET_SIZES.includes(v.size) ? v.size : 'CUSTOM'}
                              onChange={(e) => {
                                if (e.target.value === 'CUSTOM') {
                                  handleToggleCustomInput(i, true);
                                } else {
                                  handleSizeChange(i, e.target.value);
                                }
                              }}
                              className="w-full rounded border border-zinc-300 bg-white px-1.5 py-1 text-xs font-bold text-zinc-800 focus:border-amber-500 focus:outline-none"
                            >
                              {!PRESET_SIZES.includes(v.size) && v.size && (
                                <option value={v.size}>{v.size}</option>
                              )}
                              <optgroup label="Standard Sizes">
                                {['XS', 'S', 'M', 'L', 'XL'].map((s) => (
                                  <option
                                    key={s}
                                    value={s}
                                    disabled={
                                      v.size.trim().toUpperCase() !== s.toUpperCase() &&
                                      variantList.some(
                                        (other, oIdx) =>
                                          oIdx !== i && other.size.trim().toUpperCase() === s.toUpperCase()
                                      )
                                    }
                                  >
                                    {s}
                                  </option>
                                ))}
                              </optgroup>
                              <optgroup label="Plus Sizes">
                                {['XXL', '3XL', '4XL', '5XL'].map((s) => (
                                  <option
                                    key={s}
                                    value={s}
                                    disabled={
                                      v.size.trim().toUpperCase() !== s.toUpperCase() &&
                                      variantList.some(
                                        (other, oIdx) =>
                                          oIdx !== i && other.size.trim().toUpperCase() === s.toUpperCase()
                                      )
                                    }
                                  >
                                    {s}
                                  </option>
                                ))}
                              </optgroup>
                              <optgroup label="Other">
                                <option
                                  value="Free Size"
                                  disabled={
                                    v.size.trim().toUpperCase() !== 'FREE SIZE' &&
                                    variantList.some(
                                      (other, oIdx) =>
                                        oIdx !== i && other.size.trim().toUpperCase() === 'FREE SIZE'
                                    )
                                  }
                                >
                                  Free Size
                                </option>
                                <option value="CUSTOM">+ Custom...</option>
                              </optgroup>
                            </select>
                          )}
                        </div>

                        {/* SKU */}
                        <div className="flex-1 min-w-[120px]">
                          <input
                            type="text"
                            placeholder="SKU"
                            value={v.sku}
                            disabled={v.isExisting}
                            onChange={(e) => handleSkuChange(i, e.target.value)}
                            className="w-full rounded border border-zinc-300 bg-white px-2 py-1 font-mono text-[11px] text-zinc-700 focus:border-amber-500 focus:outline-none disabled:bg-zinc-100 disabled:text-zinc-500"
                          />
                        </div>

                        {/* Quantity */}
                        <div className="flex items-center gap-1 shrink-0">
                          <span className="text-[10px] text-zinc-400 font-medium">Qty:</span>
                          <input
                            type="number"
                            min="0"
                            value={v.initial_stock}
                            disabled={v.isExisting}
                            onChange={(e) => handleQtyChange(i, parseInt(e.target.value) || 0)}
                            className="w-14 rounded border border-zinc-300 bg-white px-1.5 py-1 text-right text-xs font-semibold focus:border-amber-500 focus:outline-none disabled:bg-zinc-100 disabled:text-zinc-600"
                          />
                        </div>

                        {/* Remove Action */}
                        {!v.isExisting ? (
                          <button
                            type="button"
                            onClick={() => handleRemoveVariant(i)}
                            className="p-1 rounded text-zinc-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                            title="Remove this size"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        ) : (
                          <span className="text-[10px] text-zinc-400 px-1 italic">Saved</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

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
                  {isSaving ? 'Saving...' : editingProduct ? 'Update Product' : 'Create Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Product Deletion Confirmation Modal */}
      {deletingProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600 mb-3">
              <div className="rounded-full bg-rose-50 p-2.5 border border-rose-100">
                <Trash2 className="h-6 w-6 text-rose-600" />
              </div>
              <div>
                <h3 className="text-base font-bold text-zinc-900">Delete Product</h3>
                <p className="text-xs text-zinc-500">Confirm product removal</p>
              </div>
            </div>

            <p className="text-sm text-zinc-700 font-medium mb-3">
              Are you sure you want to delete <span className="font-bold text-zinc-900">"{deletingProduct.product_name}"</span>?
            </p>

            <p className="text-xs text-zinc-500 mb-6 bg-zinc-50 p-3 rounded-xl border border-zinc-200 leading-relaxed">
              If this product has historical sales or inventory transactions, it will be safely archived to protect bill records. If it has no dependent records, it will be permanently deleted.
            </p>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setDeletingProduct(null)}
                disabled={isDeleting}
                className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDeleteProduct}
                disabled={isDeleting}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white shadow-md hover:bg-rose-500 disabled:opacity-50"
              >
                {isDeleting ? 'Deleting...' : 'Delete Product'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
