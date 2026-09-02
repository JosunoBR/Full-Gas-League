import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

/**
 * Configura o comportamento das notificações quando o app está em primeiro plano.
 * Exibe o banner, toca o som e atualiza o badge mesmo com o app aberto.
 */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

/**
 * Solicita permissão ao usuário e obtém o FCM token do dispositivo.
 * Deve ser chamado na inicialização do app (tela de login ou App.js).
 *
 * @returns {Promise<string|null>} O FCM token ou null se não foi possível obter.
 */
export async function registerForPushNotifications() {
  // Notificações push só funcionam em dispositivos físicos
  if (!Device.isDevice) {
    console.log('[Notifications] Push não suportado em emulador/simulador.');
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
    console.log('[Notifications] Permissão de notificação negada pelo usuário.');
    return null;
  }

  // Configuração específica para Android: canal de notificação
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('fullgas-default', {
      name: 'FullGas Notificações',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#E10600',
      sound: 'default',
    });
  }

  // Obtém o token FCM do dispositivo
  try {
    const tokenData = await Notifications.getDevicePushTokenAsync();
    console.log('[Notifications] FCM Token obtido:', tokenData.data?.substring(0, 20) + '...');
    return tokenData.data;
  } catch (error) {
    console.error('[Notifications] Erro ao obter FCM token:', error);
    return null;
  }
}

/**
 * Registra um listener para quando o usuário toca em uma notificação.
 * Retorna a função de cleanup para ser chamada no useEffect.
 *
 * @param {Function} onNotificationTapped - Callback recebendo o objeto de notificação.
 * @returns {Function} Função de cleanup do listener.
 */
export function addNotificationTapListener(onNotificationTapped) {
  const subscription = Notifications.addNotificationResponseReceivedListener(response => {
    const data = response.notification.request.content.data;
    console.log('[Notifications] Notificação tocada:', data);
    onNotificationTapped(data);
  });

  // Retorna cleanup para useEffect
  return () => subscription.remove();
}
