import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';

// Configura o comportamento das notificações quando o app está em primeiro plano
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

/**
 * Solicita permissão ao usuário e obtém o FCM token nativo do dispositivo.
 * Retorna o token (string) ou null se não for possível obtê-lo.
 */
export async function registerForPushNotificationsAsync() {
  // Notificações push só funcionam em dispositivos físicos
  if (!Device.isDevice) {
    console.warn('[Notifications] Push não suportado em emulador/simulador.');
    return null;
  }

  // Verifica e solicita permissão
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.warn('[Notifications] Permissão negada pelo usuário.');
    return null;
  }

  // Canal de notificação (obrigatório no Android)
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('fullgas-default', {
      name: 'FullGas Notificações',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#E10600',
      sound: 'default',
    });
  }

  // Obtém o FCM token nativo (não Expo Push Token — compatível com firebase-admin)
  try {
    const tokenData = await Notifications.getDevicePushTokenAsync();
    console.log('[Notifications] FCM Token obtido:', tokenData.data?.substring(0, 25) + '...');
    // Retorna objeto { data: token } para manter compatibilidade com AuthContext
    return tokenData;
  } catch (error) {
    console.error('[Notifications] Erro ao obter FCM token:', error);
    return null;
  }
}

/**
 * Registra um listener para quando o usuário TOCA em uma notificação.
 * Retorna a função de cleanup para ser chamada no useEffect.
 *
 * @param {Function} onTap - Callback com os dados da notificação tocada.
 * @returns {Function} Função de cleanup.
 */
export function addNotificationTapListener(onTap) {
  const subscription = Notifications.addNotificationResponseReceivedListener(response => {
    const data = response.notification.request.content.data;
    console.log('[Notifications] Notificação tocada, dados:', data);
    if (onTap) onTap(data);
  });
  return () => subscription.remove();
}

/**
 * Registra um listener para notificações recebidas com o app em primeiro plano.
 *
 * @param {Function} onReceive - Callback com a notificação recebida.
 * @returns {Function} Função de cleanup.
 */
export function addNotificationReceivedListener(onReceive) {
  const subscription = Notifications.addNotificationReceivedListener(notification => {
    console.log('[Notifications] Notificação recebida em primeiro plano:', notification);
    if (onReceive) onReceive(notification);
  });
  return () => subscription.remove();
}

export default {
  registerForPushNotificationsAsync,
  addNotificationTapListener,
  addNotificationReceivedListener,
};
