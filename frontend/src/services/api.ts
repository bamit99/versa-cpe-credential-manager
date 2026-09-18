import axios, { AxiosError } from "axios";
import { getToken, refreshToken } from "./keycloak";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
  timeout: 30_000,
});

api.interceptors.request.use(async (config) => {
  // Refresh best-effort, then attach whatever token keycloak-js holds.
  // NOTE: keycloak-js v26 updateToken() resolves FALSE when the token is still
  // valid ("no refresh needed") — its return value must NOT gate the header.
  await refreshToken().catch(() => false);
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      window.location.reload(); // expired session → Keycloak re-auth
    }
    return Promise.reject(error);
  },
);

export function errorMessage(err: unknown): string {
  const axiosErr = err as AxiosError<{ detail?: string }>;
  return axiosErr?.response?.data?.detail ?? axiosErr?.message ?? "Unexpected error";
}

export default api;