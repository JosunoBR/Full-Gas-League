import React, { createContext, useState, useEffect } from 'react';
import * as SecureStore from 'expo-secure-store';
import api from '../services/api';

export const AuthContext = createContext({});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStorageData() {
      const storedToken = await SecureStore.getItemAsync('user_token');
      const storedUser = await SecureStore.getItemAsync('user_data');

      if (storedToken && storedUser) {
        api.defaults.headers['Authorization'] = `Bearer ${storedToken}`;
        setUser(JSON.parse(storedUser));
      }
      setLoading(false);
    }

    loadStorageData();
  }, []);

  async function signIn(email, password) {
    try {
      const response = await api.post('/login', {
        email,
        password,
        // fcm_token: ... (será implementado na Fase 3)
      });

      const { access_token, user } = response.data;

      api.defaults.headers['Authorization'] = `Bearer ${access_token}`;

      await SecureStore.setItemAsync('user_token', access_token);
      await SecureStore.setItemAsync('user_data', JSON.stringify(user));

      setUser(user);
      return { success: true };
    } catch (error) {
        const msg = error.response?.data?.msg || 'Erro ao conectar com o servidor';
        return { success: false, msg };
    }
  }

  async function signOut() {
    await SecureStore.deleteItemAsync('user_token');
    await SecureStore.deleteItemAsync('user_data');
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ signed: !!user, user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};