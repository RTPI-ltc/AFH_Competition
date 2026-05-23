import { useState, useEffect } from 'react';
import { ArrowLeft, Package, Search, Plus, Trash2, X, Check, Loader2, Box } from 'lucide-react';
import { getProducts, addProduct, deleteProduct, type SkuProduct } from '../../services/api';

interface ProductPageProps {
  onBack: () => void;
}

const categoryColors: Record<string, string> = {
  '黄金': 'bg-amber-100 text-amber-700',
  '镶嵌': 'bg-blue-100 text-blue-700',
  '玉石': 'bg-green-100 text-green-700',
  '银饰': 'bg-gray-100 text-gray-700',
  '珍珠': 'bg-pink-100 text-pink-700',
  '铂金': 'bg-indigo-100 text-indigo-700',
};

const initialForm = {
  sku_id: '', product_name: '', brand: 'CTF', category_l1: '黄金', category_l2: '足金',
  pricing_model: 'fixed', weight_g: '', purity: '', tag_price_rmb: '', list_price_rmb: '', stock: '',
  review_rate: '0.98', factory_id: 'F-SZ-001',
};

export function ProductPage({ onBack }: ProductPageProps) {
  const [products, setProducts] = useState<SkuProduct[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [activeCategory, setActiveCategory] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [adding, setAdding] = useState(false);

  useEffect(() => { loadProducts(); }, [activeCategory]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const data = await getProducts(activeCategory || undefined, search || undefined);
      setProducts(data.products);
      setCategories(data.categories);
      setTotal(data.total);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const handleSearch = () => { loadProducts(); };

  const handleAdd = async () => {
    if (!form.sku_id.trim() || !form.product_name.trim()) return;
    setAdding(true);
    try {
      await addProduct({
        sku_id: form.sku_id.trim(),
        product_name: form.product_name.trim(),
        brand: form.brand, category_l1: form.category_l1, category_l2: form.category_l2,
        pricing_model: form.pricing_model,
        weight_g: form.weight_g ? parseFloat(form.weight_g) : null,
        purity: form.purity || null,
        tag_price_rmb: parseFloat(form.tag_price_rmb) || 0,
        list_price_rmb: form.list_price_rmb ? parseFloat(form.list_price_rmb) : null,
        stock: parseInt(form.stock) || 0,
        review_rate: parseFloat(form.review_rate) || 0,
        factory_id: form.factory_id,
        new_product: true, active_campaigns: [],
      });
      setForm(initialForm);
      setShowAdd(false);
      await loadProducts();
    } catch (e) { console.error(e); }
    finally { setAdding(false); }
  };

  const handleDelete = async (skuId: string) => {
    await deleteProduct(skuId);
    await loadProducts();
  };

  const formatPrice = (v: number | null) => v ? `¥${v.toLocaleString()}` : '—';
  const formatRate = (v: number) => `${(v * 100).toFixed(1)}%`;

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="border-b border-gray-200 px-6 py-4 shrink-0">
        <div className="flex items-center gap-3 max-w-7xl mx-auto">
          <button onClick={onBack} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"><ArrowLeft size={18} /></button>
          <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center"><Package size={16} className="text-blue-600" /></div>
          <h1 className="text-lg font-semibold text-gray-900 flex-1">商品数据库 · SKU Catalog</h1>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-colors shadow-sm">
            <Plus size={16} /> 添加商品
          </button>
          <div className="flex items-center gap-2 ml-3">
            <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input type="text" value={search} onChange={e => setSearch(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSearch(); }}
                placeholder="搜索SKU/商品/品牌..." className="pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg w-52 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <button onClick={handleSearch} className="px-4 py-2 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">搜索</button>
          </div>
        </div>
        <div className="flex gap-1 mt-3 max-w-7xl mx-auto">
          <button onClick={() => setActiveCategory('')} className={`px-3 py-1.5 text-xs rounded-lg ${!activeCategory ? 'bg-indigo-100 text-indigo-700 font-medium' : 'text-gray-500 hover:bg-gray-100'}`}>全部 ({total})</button>
          {categories.map(cat => (
            <button key={cat} onClick={() => setActiveCategory(cat)} className={`px-3 py-1.5 text-xs rounded-lg ${activeCategory === cat ? 'bg-indigo-100 text-indigo-700 font-medium' : 'text-gray-500 hover:bg-gray-100'}`}>{cat}</button>
          ))}
        </div>
      </div>

      {/* Add form modal */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">添加商品</h3>
              <button onClick={() => setShowAdd(false)} className="p-1 rounded hover:bg-gray-100"><X size={18} /></button>
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">SKU ID *</label>
                  <input value={form.sku_id} onChange={e => setForm({...form, sku_id: e.target.value})}
                    placeholder="CTF-XXX-001" className="w-full px-2 py-1.5 text-xs border rounded-lg focus:ring-1 focus:ring-indigo-500" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">品牌</label>
                  <select value={form.brand} onChange={e => setForm({...form, brand: e.target.value})}
                    className="w-full px-2 py-1.5 text-xs border rounded-lg">
                    {['CTF','CTF 传承','T MARK','SOINLOVE','MONOLOGUE'].map(b => <option key={b}>{b}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">商品名称 *</label>
                <input value={form.product_name} onChange={e => setForm({...form, product_name: e.target.value})}
                  placeholder="输入商品名称" className="w-full px-2 py-1.5 text-xs border rounded-lg focus:ring-1 focus:ring-indigo-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">一级类目</label>
                  <select value={form.category_l1} onChange={e => setForm({...form, category_l1: e.target.value})}
                    className="w-full px-2 py-1.5 text-xs border rounded-lg">
                    {categories.map(c => <option key={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">二级类目</label>
                  <input value={form.category_l2} onChange={e => setForm({...form, category_l2: e.target.value})}
                    className="w-full px-2 py-1.5 text-xs border rounded-lg" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">定价模式</label>
                  <select value={form.pricing_model} onChange={e => setForm({...form, pricing_model: e.target.value})}
                    className="w-full px-2 py-1.5 text-xs border rounded-lg">
                    <option value="fixed">一口价</option><option value="weight">计重</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">克重(g)</label>
                  <input value={form.weight_g} onChange={e => setForm({...form, weight_g: e.target.value})}
                    placeholder="选填" className="w-full px-2 py-1.5 text-xs border rounded-lg" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">吊牌价 *</label>
                  <input value={form.tag_price_rmb} onChange={e => setForm({...form, tag_price_rmb: e.target.value})}
                    placeholder="0" className="w-full px-2 py-1.5 text-xs border rounded-lg" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">划线价</label>
                  <input value={form.list_price_rmb} onChange={e => setForm({...form, list_price_rmb: e.target.value})}
                    placeholder="选填" className="w-full px-2 py-1.5 text-xs border rounded-lg" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">库存 *</label>
                  <input value={form.stock} onChange={e => setForm({...form, stock: e.target.value})}
                    placeholder="0" className="w-full px-2 py-1.5 text-xs border rounded-lg" />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">取消</button>
              <button onClick={handleAdd} disabled={adding || !form.sku_id || !form.product_name}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-40 flex items-center gap-1">
                {adding ? <><Loader2 size={14} className="animate-spin" />添加中...</> : <><Check size={14} />添加</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Product grid */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto">
          {loading ? (<p className="text-center text-gray-400 py-20">加载中...</p>) : products.length === 0 ? (
            <div className="text-center py-20"><Box size={40} className="mx-auto mb-3 text-gray-300" /><p className="text-gray-400 text-sm">暂无商品数据</p></div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {products.map(p => (
                <div key={p.sku_id} className="group bg-white border border-gray-200 rounded-xl p-4 hover:shadow-md hover:border-gray-300 transition-all">
                  <div className="flex items-start justify-between mb-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${categoryColors[p.category_l1] || 'bg-gray-100'}`}>{p.category_l1}</span>
                    <div className="flex items-center gap-1">
                      {p.new_product && <span className="text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded-full">NEW</span>}
                      <button onClick={() => handleDelete(p.sku_id)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500 transition-all" title="删除">
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-800 mb-1 line-clamp-2">{p.product_name}</h3>
                  <p className="text-[11px] text-gray-400 mb-2">{p.sku_id} · {p.brand} · {p.category_l2}</p>
                  <div className="grid grid-cols-3 gap-2 mb-2">
                    <div className="bg-gray-50 rounded-lg p-1.5 text-center">
                      <p className="text-sm font-bold text-gray-800">{formatPrice(p.tag_price_rmb)}</p>
                      <p className="text-[10px] text-gray-400">吊牌价</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-1.5 text-center">
                      <p className="text-sm font-bold text-gray-800">{p.stock}</p>
                      <p className="text-[10px] text-gray-400">库存</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-1.5 text-center">
                      <p className="text-sm font-bold text-gray-800">{p.last_90d_sales}</p>
                      <p className="text-[10px] text-gray-400">90天销量</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 text-[10px] text-gray-500">
                    {p.weight_g && <span className="px-1.5 py-0.5 bg-gray-100 rounded">{p.weight_g}g</span>}
                    {p.purity && <span className="px-1.5 py-0.5 bg-gray-100 rounded">{p.purity}</span>}
                    <span className="px-1.5 py-0.5 bg-gray-100 rounded">{p.pricing_model === 'weight' ? '计重' : '一口价'}</span>
                    <span className="px-1.5 py-0.5 bg-gray-100 rounded">好评{formatRate(p.review_rate)}</span>
                    {p.active_campaigns.length > 0 && (
                      <span className="px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">{p.active_campaigns.length}个活动</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {!loading && <p className="text-center text-xs text-gray-400 mt-6">共 {total} 件 SKU · {categories.length} 个品类</p>}
        </div>
      </div>
    </div>
  );
}
