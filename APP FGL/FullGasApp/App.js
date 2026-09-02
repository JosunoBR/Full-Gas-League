import 'react-native-gesture-handler';
import React, { useContext, useEffect } from 'react';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, View, Alert, Linking } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as Notifications from 'expo-notifications';

import AuthProvider, { AuthContext } from './src/context/AuthContext';
import Login from './src/screens/Login';
import AppNavigator from './src/navigation/AppNavigator';
import { addNotificationTapListener, addNotificationReceivedListener } from './src/services/notifications';
import api from './src/services/api';

const Stack = createStackNavigator();
export const navigationRef = createNavigationContainerRef();

function Routes() {
  const { signed, loading } = useContext(AuthContext);

  useEffect(() => {
    // 1. Checa se o app foi aberto pelo clique em uma notificação com ele fechado (Cold Start)
    Notifications.getLastNotificationResponseAsync()
      .then((response) => {
        if (response && response.notification && response.notification.request) {
          const data = response.notification.request.content.data;
          if (data) {
            console.log('[App] Notificação capturada via Cold Start:', data);
            handleNotificationNavigation(data);
          }
        }
      })
      .catch((err) => console.warn('[App] Erro ao checar notificação inicial:', err));

    // 2. Listener: notificação recebida com app em primeiro plano
    const cleanupReceived = addNotificationReceivedListener((notification) => {
      const { title, body } = notification.request.content;
      Alert.alert(title || 'FullGas', body || '');
    });

    // 3. Listener: usuário tocou na notificação com o app aberto ou em background
    const cleanupTap = addNotificationTapListener((data) => {
      console.log('[App] Notificação tocada pelo usuário:', data);
      handleNotificationNavigation(data);
    });

    return () => {
      cleanupReceived();
      cleanupTap();
    };
  }, []);

  useEffect(() => {
    if (!signed) return;

    // Listener: token FCM renovado pelo sistema operacional
    const tokenSubscription = Notifications.addPushTokenListener(async (newTokenData) => {
      console.log('[App] Token FCM renovado pelo sistema:', newTokenData.data?.substring(0, 25) + '...');
      try {
        await api.post('/update-fcm-token', { fcm_token: newTokenData.data });
        console.log('[App] Novo token enviado ao servidor com sucesso.');
      } catch (err) {
        console.warn('[App] Falha ao atualizar token renovado:', err.message);
      }
    });

    return () => {
      tokenSubscription.remove();
    };
  }, [signed]);

  /**
   * Navega para a tela correta ao tocar em uma notificação.
   * Se for notificação com link externo (YouTube / live), abre diretamente sem depender da navegação interna.
   */
  function handleNotificationNavigation(data) {
    if (!data) return;

    const { type, url } = data;
    console.log('[App] Navegando por notificação. Tipo:', type, 'URL:', url);

    // 1. Redirecionamento direto para links externos (YouTube da corrida / canal)
    if (url || type === 'race_day' || type === 'broadcast' || type === 'youtube_broadcast') {
      const targetUrl = url || 'https://www.youtube.com/@FullGasLeagueF1Oficial';
      console.log('[App] Abrindo link de transmissão externo:', targetUrl);
      Linking.openURL(targetUrl).catch((err) => {
        console.warn('[App] Erro ao abrir URL no navegador/YouTube:', err);
      });
      return;
    }

    // 2. Navegação interna do app (espera navigationRef estar pronto caso necessário)
    const executeInternalNavigation = () => {
      if (!navigationRef.isReady()) {
        setTimeout(executeInternalNavigation, 150);
        return;
      }

      switch (type) {
        case 'race_result':
          navigationRef.navigate('MainApp', { screen: 'RacesTab' });
          break;
        case 'protest_opened':
        case 'protest_verdict':
        case 'defense_deadline':
          navigationRef.navigate('MainApp', { screen: 'TribunalTab' });
          break;
        case 'news':
          navigationRef.navigate('MainApp', { screen: 'HomeTab' });
          break;
        case 'race_reminder':
        case 'ban_alert':
          navigationRef.navigate('MainApp', { screen: 'ProfileTab' });
          break;
        default:
          navigationRef.navigate('MainApp', { screen: 'HomeTab' });
      }
    };

    executeInternalNavigation();
  }

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#000000' }}>
        <ActivityIndicator size="large" color="#E60000" />
      </View>
    );
  }

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {signed ? (
        <Stack.Screen name="MainApp" component={AppNavigator} />
      ) : (
        <Stack.Screen name="Login" component={Login} />
      )}
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer ref={navigationRef}>
        <AuthProvider>
          <StatusBar style="light" />
          <Routes />
        </AuthProvider>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}