export interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  stock: number;
  status: 'ACTIVE' | 'INACTIVE' | 'OUT_OF_STOCK';
  description: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  count?: number;
}

export interface HealthStatus {
  status: 'UP' | 'DOWN' | 'CHECKING';
  components?: Record<string, { status: string }>;
}

export interface AppHealthResponse {
  status: string;
  service: string;
  version: string;
}

export type ProductCategory = 'all' | 'electronics' | 'furniture' | 'books';
