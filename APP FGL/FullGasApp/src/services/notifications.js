import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';

const isExpoGo = Constants.appOwnership === 'expo'
  || Constants.executionEnvironment === 'storeClient';

// Configure o comportamento das notificacoes
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotificationsAsync() {
  let token = null;

  if (isExpoGo) {
    console.warn('[Notifications] Expo Go nao suporta push remoto no SDK 53+. Use um Development Build.');
    return null;
  }

  // Verifica se esta rodando em um dispositivo fisico
  const isDevice = Constants.platform?.ios || Constants.platform?.android;
  if (isDevice) {
    // Solicita permissao ao usuario
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== 'granted') {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== 'granted') {
      console.log('[Notifications] Permissao de notificacoes nao concedida');
      return null;
    }

    // Obtem o token do dispositivo
    try {
      const projectId = Constants.expoConfig?.extra?.eas?.projectId
        ?? Constants.manifest?.extra?.eas?.projectId;

      if (projectId) {
        token = await Notifications.getExpoPushTokenAsync({ projectId });
      } else {
        // Fallback: token sem projectId
        token = await Notifications.getPushTokenAsync();
      }

      console.log('[Notifications] Token obtido:', token.data);
    } catch (error) {
      console.error('[Notifications] Erro ao obter token:', error);
    }
  }

  return token;
}

export async function scheduleCheckinReminder(raceName, raceDate, hoursBefore = 24) {
  const trigger = new Date(raceDate);
  trigger.setHours(trigger.getHours() - hoursBefore);

  if (trigger <= new Date()) {
    console.log('[Notifications] Horario ja passou, nao agenda notificacao');
    return;
  }

  await Notifications.scheduleNotificationAsync({
    content: {
      title: 'Lembrete de Check-in',
      body: `A corrida "${raceName}" esta chegando! Voce tem ate 24h antes para confirmar sua presenca.`,
      data: { type: 'checkin_reminder', raceName },
    },
    trigger,
  });

  console.log(`[Notifications] Lembrete agendado para ${trigger}`);
}

export async function cancelCheckinReminder(raceName) {
  console.log(`[Notifications] Cancelando lembretes para ${raceName}`);
}

export default {
  registerForPushNotificationsAsync,
  scheduleCheckinReminder,
  cancelCheckinReminder,
};
