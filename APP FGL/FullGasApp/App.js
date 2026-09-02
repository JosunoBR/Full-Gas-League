import 'react-native-gesture-handler';
import React, { useContext, useEffect } from 'react';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, View, Alert } from 'react-native';
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
    if (!signed) return;

    // Listener: notificação recebida com app em primeiro plano
    const cleanupReceived = addNotificationReceivedListener((notification) => {
      const { title, body } = notification.request.content;
      Alert.alert(title || 'FullGas', body || '');
    });

    // Listener: usuário tocou na notificação
    const cleanupTap = addNotificationTapListener((data) => {
      handleNotificationNavigation(data);
    });

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
      cleanupReceived();
      cleanupTap();
      tokenSubscription.remove();
    };
  }, [signed]);

  /**
   * Navega para a tela correta ao tocar em uma notificação.
   * Utiliza os dados (data) enviados pelo backend para determinar o destino.
   */
  function handleNotificationNavigation(data) {
    if (!data || !navigationRef.isReady()) return;

    const { type } = data;
    console.log('[App] Navegando por notificação do tipo:', type);

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