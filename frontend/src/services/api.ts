import axios from 'axios';
import type { ApiResponse, Product, HealthStatus } from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 5000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const actuatorApi = axios.create({
  baseURL: '/actuator',
  timeout: 4000,
});

// Request interceptor – logging
api.interceptors.request.use((config) => {
  console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  return config;
});

// Response interceptor – error normalisation
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.message || error.message || 'An unknown error occurred';
    console.error(`[API Error] ${message}`);
    return Promise.reject(new Error(message));
  }
);

// ─── Product APIs ─────────────────────────────────────────────────────────────

export const fetchAllProducts = async (category?: string): Promise<ApiResponse<Product[]>> => {
  const params = category && category !== 'all' ? { category } : {};
  const { data } = await api.get<ApiResponse<Product[]>>('/products', { params });
  return data;
};

export const fetchProductById = async (id: string): Promise<ApiResponse<Product>> => {
  const { data } = await api.get<ApiResponse<Product>>(`/products/${id}`);
  return data;
};

export const createProduct = async (product: Omit<Product, 'id' | 'createdAt' | 'updatedAt'>): Promise<ApiResponse<Product>> => {
  const { data } = await api.post<ApiResponse<Product>>('/products', product);
  return data;
};

export const updateProduct = async (id: string, product: Partial<Product>): Promise<ApiResponse<Product>> => {
  const { data } = await api.put<ApiResponse<Product>>(`/products/${id}`, product);
  return data;
};

export const deleteProduct = async (id: string): Promise<ApiResponse<void>> => {
  const { data } = await api.delete<ApiResponse<void>>(`/products/${id}`);
  return data;
};

// ─── Health APIs ──────────────────────────────────────────────────────────────

export const fetchActuatorHealth = async (): Promise<HealthStatus> => {
  const { data } = await actuatorApi.get<HealthStatus>('/health');
  return data;
};

export const fetchAppHealth = async (): Promise<{ status: string }> => {
  const { data } = await api.get<{ status: string }>('/health');
  return data;
};
