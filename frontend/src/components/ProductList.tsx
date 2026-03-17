import React, { useEffect, useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import { fetchAllProducts, deleteProduct } from '../services/api';
import type { Product, ProductCategory } from '../types';
import ProductCard from './ProductCard';

const CATEGORIES: { label: string; value: ProductCategory }[] = [
  { label: 'All', value: 'all' },
  { label: '💻 Electronics', value: 'electronics' },
  { label: '🪑 Furniture', value: 'furniture' },
  { label: '📚 Books', value: 'books' },
];

const ProductList: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState<ProductCategory>('all');
  const [search, setSearch] = useState<string>('');

  const loadProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchAllProducts(category !== 'all' ? category : undefined);
      setProducts(response.data ?? []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load products';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const handleDelete = async (id: string) => {
    try {
      await deleteProduct(id);
      toast.success('Product deleted successfully');
      setProducts((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to delete product';
      toast.error(msg);
    }
  };

  const filtered = products.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.description?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <section className="product-section">
      {/* Controls */}
      <div className="product-controls">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search products..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="search-input"
          />
        </div>

        <div className="category-tabs">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.value}
              className={`category-tab ${category === cat.value ? 'active' : ''}`}
              onClick={() => setCategory(cat.value)}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <button className="refresh-btn primary" onClick={loadProducts} disabled={loading}>
          {loading ? '⟳ Loading...' : '↺ Refresh'}
        </button>
      </div>

      {/* Results summary */}
      <div className="results-summary">
        {!loading && !error && (
          <span>
            Showing <strong>{filtered.length}</strong> of <strong>{products.length}</strong> products
          </span>
        )}
      </div>

      {/* Content */}
      {loading && (
        <div className="skeleton-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton-card" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="error-state">
          <span className="error-icon">⚠️</span>
          <p>{error}</p>
          <button className="refresh-btn primary" onClick={loadProducts}>Retry</button>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="empty-state">
          <span className="empty-icon">📭</span>
          <p>No products found.</p>
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="product-grid">
          {filtered.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </section>
  );
};

export default ProductList;
