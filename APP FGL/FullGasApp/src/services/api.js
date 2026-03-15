import axios from 'axios';

// Ajuste o IP conforme sua rede. Ou defina EXPO_PUBLIC_API_URL no ambiente.
// Exemplo: EXPO_PUBLIC_API_URL=http://192.168.0.10:5000/api
const baseURL = process.env.EXPO_PUBLIC_API_URL || 'http://192.168.2.2:5000/api';

const api = axios.create({
  baseURL,
});

let authToken = null;

export function setAuthToken(token) {
  authToken = token || null;
  if (authToken) {
    api.defaults.headers.common.Authorization = `Bearer ${authToken}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

// Intercepta TODAS as requisicoes para injetar o token de forma segura e dinamica
api.interceptors.request.use(
  (config) => {
    if (authToken) {
      config.headers.Authorization = `Bearer ${authToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default api;
