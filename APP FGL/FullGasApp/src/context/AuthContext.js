import React, { createContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api, { setAuthToken } from '../services/api';
import { registerForPushNotificationsAsync } from '../services/notifications';

export const AuthContext = createContext({});

function AuthProvider({ children }) {
  const AUTH_USER_KEY = '@RNAuth:user';
  const AUTH_TOKEN_KEY = '@RNAuth:token';
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingAuth, setLoadingAuth] = useState(false);
  const [tokenReady, setTokenReady] = useState(false);
  const [expoPushToken, setExpoPushToken] = useState(null);

  function isValidJwt(token) {
    if (!token) return false;
    const trimmed = token.trim();
    if (!trimmed || trimmed === 'null' || trimmed === 'undefined') return false;
    const parts = trimmed.split('.');
    return parts.length === 3 && parts.every((p) => p.length > 0);
  }

  useEffect(() => {
    async function loadStorageData() {
      console.log('[Auth] Verificando sessão salva...');
      const storagedUser = await AsyncStorage.getItem(AUTH_USER_KEY);
      const storagedToken = await AsyncStorage.getItem(AUTH_TOKEN_KEY);
      console.log('[Auth] Dados do storage lidos.');

      if (storagedUser && isValidJwt(storagedToken)) {
        console.log('[Auth] Sessão válida encontrada. Restaurando...');
        try {
          setAuthToken(storagedToken);
          setUser(JSON.parse(storagedUser));
          setTokenReady(true);
        } catch (err) {
          console.error('[Auth] Erro ao restaurar sessão. Limpando storage.', err);
          await AsyncStorage.multiRemove([AUTH_USER_KEY, AUTH_TOKEN_KEY]);
          setAuthToken(null);
          setTokenReady(false);
        }
      } else if (storagedUser || storagedToken) {
        console.log('[Auth] Dados inconsistentes no storage. Limpando...');
        await AsyncStorage.multiRemove([AUTH_USER_KEY, AUTH_TOKEN_KEY]);
        setAuthToken(null);
        setTokenReady(false);
      } else {
        console.log('[Auth] Nenhuma sessão encontrada.');
      }
      console.log('[Auth] Verificação de sessão finalizada. App pronto.');
      setLoading(false);
    }
    loadStorageData();
  }, []);

  async function signIn(email, password) {
    setLoadingAuth(true);
    console.log('[Auth] Iniciando processo de signIn...');
    try {
      const normalizedEmail = (email || '').trim().toLowerCase();
      const normalizedPassword = (password || '').trim();

      if (!normalizedEmail || !normalizedPassword) {
        return { success: false, msg: 'Informe email e senha.' };
      }

      // Primeiro faz login para obter o token de acesso
      console.log(`[Auth] Disparando requisição para o servidor (IP 192.168.2.2) com o email: ${normalizedEmail}`);
      
      // Registra o token de notificação ANTES de fazer login
      let pushToken = null;
      try {
        pushToken = await registerForPushNotificationsAsync();
        if (pushToken) {
          console.log('[Auth] Token de notificação obtido:', pushToken.data);
          setExpoPushToken(pushToken.data);
        }
      } catch (notifError) {
        console.warn('[Auth] Erro ao obter token de notificação:', notifError.message);
      }

      const response = await api.post('/login', {
        email: normalizedEmail,
        password: normalizedPassword,
        fcm_token: pushToken ? pushToken.data : null
      });
      console.log('[Auth] Resposta recebida do servidor com sucesso (Status 200).');

      const { user, access_token } = response.data;

      if (!user || !access_token) {
        throw new Error('Resposta inesperada do servidor (faltando usuario ou token).');
      }

      setAuthToken(access_token);
      await AsyncStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
      await AsyncStorage.setItem(AUTH_TOKEN_KEY, access_token);

      // A transição de tela só ocorre APÓS o token estar salvo com segurança
      setTokenReady(true);
      setUser(user); 
      return { success: true };
    } catch (err) {
      console.error('[Auth] Erro capturado pelo catch:', err.message);
      if (err.message === 'Network Error') {
        return { success: false, msg: 'Erro de Rede: O App não alcançou o servidor no IP 192.168.2.2.' };
      }
      return { success: false, msg: err.response?.data?.msg || `Falha: ${err.message}` };
    } finally {
      setLoadingAuth(false);
    }
  }

  async function signOut() {
    console.log('[Auth] Realizando logout...');
    await AsyncStorage.multiRemove([AUTH_USER_KEY, AUTH_TOKEN_KEY]);
    setAuthToken(null);
    setTokenReady(false);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ signed: !!user, user, loading, loadingAuth, tokenReady, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export default AuthProvider;
