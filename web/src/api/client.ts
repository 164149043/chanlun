// API Client
import axios from 'axios';
import type { ChanlunData, AIAnalysisResult } from '@/types/chanlun';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,  // 60s timeout
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add retry interceptor for connection errors
api.interceptors.response.use(
  response => response,
  async error => {
    // Retry on network errors or 5xx errors
    if (!error.response && error.config) {
      // Network error - server might not be ready
      console.log('API connection error, retrying...');
      const retries = error.config._retry || 0;
      if (retries < 3) {
        error.config._retry = retries + 1;
        await new Promise(resolve => setTimeout(resolve, 1000 * (retries + 1)));
        return api.request(error.config);
      }
    }
    return Promise.reject(error);
  }
);

// Get K-line and Chanlun data
export async function getKlineData(
  symbol: string,
  interval: string,
  limit: number = 1000
): Promise<ChanlunData> {
  const response = await api.get<ChanlunData>(`/kline/${symbol}/${interval}`, {
    params: { limit }
  });
  return response.data;
}

// AI Analysis - with test mode support
export async function analyzeAI(
  symbol: string,
  interval: string,
  mode: 'structured' | 'table' = 'structured',
  test: boolean = false,  // New test parameter
  aiProvider?: string,   // New: AI provider
  aiModel?: string,      // New: AI model
  apiKey?: string        // New: API key
): Promise<AIAnalysisResult> {
  const response = await api.post<AIAnalysisResult>('/analyze', {
    symbol,
    interval,
    mode,
    test,
    limit: 500,
    // New: AI configuration
    ai_provider: aiProvider,
    ai_model: aiModel,
    api_key: apiKey
  });
  return response.data;
}

// AI Analysis Test Mode (mock data without actual AI call)
export async function analyzeAITest(
  symbol: string,
  interval: string,
  test: boolean = true
): Promise<AIAnalysisResult> {
  const response = await api.post<AIAnalysisResult>('/analyze', {
    symbol,
    interval,
    mode: 'structured',
    test,
    limit: 500
  });
  return response.data;
}

// Export API instance for other uses
export default api;
