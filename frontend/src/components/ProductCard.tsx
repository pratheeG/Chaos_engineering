import React from 'react';
import type { Product } from '../types';

interface ProductCardProps {
  product: Product;
  onDelete?: (id: string) => void;
}

const STATUS_CONFIG: Record<Product['status'], { label: string; color: string; bg: string }> = {
  ACTIVE: { label: 'Active', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' },
  INACTIVE: { label: 'Inactive', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.12)' },
  OUT_OF_STOCK: { label: 'Out of Stock', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)' },
};

const CATEGORY_ICONS: Record<string, string> = {
  electronics: '💻',
  furniture: '🪑',
  books: '📚',
};

const ProductCard: React.FC<ProductCardProps> = ({ product, onDelete }) => {
  const status = STATUS_CONFIG[product.status] ?? STATUS_CONFIG.ACTIVE;
  const icon = CATEGORY_ICONS[product.category] ?? '📦';

  return (
    <div className="product-card">
      <div className="product-card-header">
        <span className="product-category-icon">{icon}</span>
        <span
          className="product-status-badge"
          style={{ color: status.color, background: status.bg }}
        >
          {status.label}
        </span>
      </div>

      <h3 className="product-name">{product.name}</h3>
      <p className="product-description">{product.description}</p>

      <div className="product-meta">
        <span className="product-category">
          {product.category.charAt(0).toUpperCase() + product.category.slice(1)}
        </span>
        <span className={`product-stock ${product.stock === 0 ? 'stock-empty' : ''}`}>
          {product.stock === 0 ? 'No stock' : `${product.stock} in stock`}
        </span>
      </div>

      <div className="product-footer">
        <span className="product-price">${product.price.toFixed(2)}</span>
        {onDelete && (
          <button
            className="delete-btn"
            onClick={() => onDelete(product.id)}
            title="Delete product"
          >
            🗑
          </button>
        )}
      </div>
    </div>
  );
};

export default ProductCard;
