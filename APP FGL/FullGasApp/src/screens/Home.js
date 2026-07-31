import React, { useContext, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Image, ActivityIndicator, Alert, ScrollView } from 'react-native';
import { AuthContext } from '../context/AuthContext';
import api, { SERVER_BASE_URL } from '../services/api';
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function Home() {
  const { user, signOut, tokenReady } = useContext(AuthContext);
  const [profile, setProfile] = useState(null);
  const [nextRace, setNextRace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkinLoading, setCheckinLoading] = useState(false);

  // Função para buscar dados do servidor
  async function fetchDataFromServer() {
    const [profileResponse, nextRaceResponse] = await Promise.all([
      api.get('/profile'),
      api.get('/next-race')
    ]);
    
    setProfile(profileResponse.data);
    setNextRace(nextRaceResponse.data);
    await AsyncStorage.setItem('@FGL:profile', JSON.stringify(profileResponse.data));
    await AsyncStorage.setItem('@FGL:nextRace', JSON.stringify(nextRaceResponse.data));
  }

  useEffect(() => {
    async function loadData() {
      try {
        // 1. Tenta carregar os dados salvos na memória do celular primeiro
        const cachedProfile = await AsyncStorage.getItem('@FGL:profile');
        const cachedRace = await AsyncStorage.getItem('@FGL:nextRace');
        
        if (cachedProfile) setProfile(JSON.parse(cachedProfile));
        if (cachedRace) setNextRace(JSON.parse(cachedRace));
        
        // Se achou na memória, remove a tela de carregamento na mesma hora!
        if (cachedProfile || cachedRace) setLoading(false);

        // 2. Vai no site (API) buscar os dados mais atualizados de forma silenciosa
        await fetchDataFromServer();

      } catch (error) {
        const status = error?.response?.status;
        console.error(`[Home] Falha na API. Status: ${status}`);
        console.error('[Home] Resposta do Servidor:', error?.response?.data || error.message);
        
        if (status === 401 || status === 422) {
          Alert.alert('Sessao expirada', 'Faca login novamente.');
          signOut();
          return;
        }
        console.error('Failed to fetch data', error);
        Alert.alert('Erro', 'Nao foi possivel carregar os dados do servidor.');
      } finally {
        setLoading(false);
      }
    }

    if (!tokenReady) return;
    loadData();
  }, [signOut, tokenReady]);

  const handleCheckin = async (status) => {
    if (!nextRace || checkinLoading) return;

    Alert.alert(
      status === 'CONFIRMADO' ? 'Confirmar Presença' : 'Reportar Ausência',
      status === 'CONFIRMADO' 
        ? `Você confirma presença na corrida "${nextRace.nome_gp}"?`
        : `Você deseja reportar ausência na corrida "${nextRace.nome_gp}"?`,
      [
        { text: 'Cancelar', style: 'cancel' },
        { 
          text: 'Sim', 
          onPress: async () => {
            setCheckinLoading(true);
            try {
              const response = await api.post('/checkin', {
                race_id: nextRace.race_id,
                status: status
              });
              
              Alert.alert('Sucesso!', response.data.msg || 'Check-in realizado com sucesso!');
              
              // Recarrega os dados do servidor para atualizar a tela
              // Isso busca a próxima corrida pendente ou mostra mensagem apropriada
              await fetchDataFromServer();

            } catch (error) {
              const errStatus = error?.response?.status;
              if (errStatus === 401 || errStatus === 422) {
                Alert.alert('Sessao expirada', 'Faca login novamente.');
                signOut();
                return;
              }
              const errMsg = error?.response?.data?.msg || 'Nao foi possivel realizar o check-in. Tente novamente.';
              console.error('Failed to check in', error);
              Alert.alert('Erro', errMsg);
            } finally {
              setCheckinLoading(false);
            }
          }
        }
      ]
    );
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color="#E60000" />
        <Text style={styles.loadingText}>Carregando perfil...</Text>
      </View>
    );
  }

  const getCheckinButtonStyle = (status) => {
    if (status === 'CONFIRMADO') return { ...styles.checkinButton, backgroundColor: '#28a745' };
    if (status === 'AUSENTE') return { ...styles.checkinButton, backgroundColor: '#dc3545' };
    return { ...styles.checkinButton, backgroundColor: '#00BFFF' };
  };

  const getCheckinButtonText = (status) => {
    if (status === 'CONFIRMADO') return 'Presenca Confirmada';
    if (status === 'AUSENTE') return 'Ausencia Registrada';
    return 'Confirmar Presenca';
  };

  // Monta a URL completa da imagem para o React Native conseguir ler
  const serverBaseUrl = SERVER_BASE_URL;
  const profileImageUrl = profile?.foto_url 
    ? (profile.foto_url.startsWith('http') ? profile.foto_url : `${serverBaseUrl}/static/uploads/${profile.foto_url}`)
    : 'https://via.placeholder.com/150';

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Image
          source={{ uri: profileImageUrl }}
          style={styles.profileImage}
        />
        <Text style={styles.userName}>{profile?.nickname || user?.username}</Text>
        <Text style={styles.teamName}>🏎️ {profile?.equipe_atual || 'Sem Equipe'}</Text>
      </View>

      {profile?.quali_ban && (
        <View style={styles.qualiBanBanner}>
          <Text style={styles.qualiBanText}>⛔ ATENÇÃO: Você está cumprindo Punição de Quali Ban nesta etapa.</Text>
        </View>
      )}

      <View style={styles.statsContainer}>
        <View style={styles.statBox}>
          <Text style={[styles.statValue, { color: profile?.cnh_pontos <= 0 ? '#E60000' : (profile?.cnh_pontos <= 10 ? '#FFCC00' : '#28a745') }]}>
            {profile?.cnh_pontos} / 25
          </Text>
          <Text style={styles.statLabel}>Carteira CNH</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={[styles.statValue, { color: '#00BFFF' }]}>{profile?.lastro_veiculo || 'N/A'}</Text>
          <Text style={styles.statLabel}>Carro de Lastro</Text>
        </View>
      </View>

      {/* Pontuação nos Campeonatos / Grids */}
      {profile?.pontuacao_campeonatos && profile.pontuacao_campeonatos.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>🏆 Meus Campeonatos (Pontuação)</Text>
          {profile.pontuacao_campeonatos.map((camp, idx) => (
            <View key={idx} style={styles.campRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.campGridName}>Grid {camp.grid_nome}</Text>
                <Text style={styles.campTeam}>{camp.equipe}</Text>
              </View>

              <View style={{ alignItems: 'flex-end' }}>
                <Text style={styles.campPos}>{camp.posicao}º Lugar</Text>
                <Text style={styles.campPts}>{camp.pontos} pts • {camp.vitorias} Vit</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {nextRace ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Proxima Corrida: {nextRace.grid_nome}</Text>
          <Text style={styles.raceInfo}>{nextRace.nome_gp}</Text>
          <Text style={styles.raceInfo}>{new Date(nextRace.data_corrida).toLocaleDateString('pt-BR', { timeZone: 'UTC' })} - {nextRace.pista}</Text>
          
          <TouchableOpacity 
            style={getCheckinButtonStyle(nextRace.checkin_status)} 
            onPress={() => handleCheckin('CONFIRMADO')}
            disabled={nextRace.checkin_status === 'CONFIRMADO'}
          >
            <Text style={styles.checkinButtonText}>{getCheckinButtonText(nextRace.checkin_status)}</Text>
          </TouchableOpacity>
          
          {nextRace.checkin_status !== 'AUSENTE' && (
             <TouchableOpacity style={styles.absenceButton} onPress={() => handleCheckin('AUSENTE')}>
               <Text style={styles.absenceButtonText}>Informar Ausencia</Text>
             </TouchableOpacity>
          )}
        </View>
      ) : (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Nenhuma corrida agendada no seu grid.</Text>
        </View>
      )}

      {/* Tabela de Desempenho da Temporada */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Historico de Corridas</Text>
        {profile?.desempenho_temporada && profile.desempenho_temporada.length > 0 ? (
          profile.desempenho_temporada.map((corrida, index) => (
            <View key={index} style={styles.resultItem}>
              <View style={styles.resultInfo}>
                <Text style={styles.resultGp}>{corrida.gp}</Text>
                {corrida.grid && <Text style={styles.resultGrid}>{corrida.grid}</Text>}
              </View>
              <View style={styles.resultBadges}>
                <View style={[styles.badge, (corrida.dnf || corrida.dsq) ? styles.badgeDanger : styles.badgePrimary]}>
                  <Text style={styles.badgeText}>
                    {corrida.posicao > 0 && !corrida.dnf && !corrida.dsq ? `P${corrida.posicao}` : (corrida.dnf ? 'DNF' : (corrida.dsq ? 'DSQ' : '-'))}
                  </Text>
                </View>
                <View style={[styles.badge, styles.badgeSuccess]}>
                  <Text style={styles.badgeText}>+{corrida.pontos} pts</Text>
                </View>
              </View>
            </View>
          ))
        ) : (
          <Text style={styles.emptyText}>Nenhuma corrida registrada ainda.</Text>
        )}
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={signOut}>
        <Text style={styles.logoutButtonText}>Sair</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
    padding: 20,
  },
  center: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#FFF',
    marginTop: 10,
  },
  header: {
    alignItems: 'center',
    marginBottom: 20,
  },
  profileImage: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 3,
    borderColor: '#E60000',
  },
  userName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
    marginTop: 15,
  },
  teamName: {
    fontSize: 18,
    color: '#AAA',
    marginBottom: 20,
  },
  editButton: {
    backgroundColor: '#333',
    paddingVertical: 6,
    paddingHorizontal: 20,
    borderRadius: 5,
    marginBottom: 10,
  },
  editButtonText: {
    color: '#FFF',
    fontSize: 14,
  },
  qualiBanBanner: {
    backgroundColor: '#dc3545',
    padding: 12,
    borderRadius: 8,
    marginBottom: 15,
    alignItems: 'center',
  },
  qualiBanText: {
    color: '#FFF',
    fontWeight: 'bold',
    fontSize: 13,
    textAlign: 'center',
  },
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 20,
  },
  statBox: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#FFF',
  },
  statLabel: {
    fontSize: 14,
    color: '#AAA',
  },
  card: {
    backgroundColor: '#1e2745',
    borderRadius: 8,
    padding: 20,
    marginBottom: 20,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 15,
  },
  raceInfo: {
    fontSize: 16,
    color: '#DDD',
    marginBottom: 5,
  },
  checkinButton: {
    borderRadius: 8,
    paddingVertical: 15,
    alignItems: 'center',
    marginTop: 15,
  },
  checkinButtonText: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
  },
  absenceButton: {
    marginTop: 10,
    padding: 10,
    alignItems: 'center',
  },
  absenceButtonText: {
    color: '#AAA',
    fontSize: 14,
  },
  resultItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#2a365c',
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
  },
  resultInfo: {
    flex: 1,
  },
  resultGp: {
    color: '#DDD',
    fontSize: 16,
    fontWeight: 'bold',
    flex: 1,
  },
  resultGrid: {
    color: '#888',
    fontSize: 12,
    marginTop: 2,
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
    textAlign: 'center',
    paddingVertical: 20,
  },
  resultBadges: {
    flexDirection: 'row',
    gap: 8,
  },
  badge: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
  },
  badgePrimary: { backgroundColor: '#00BFFF' },
  badgeDanger: { backgroundColor: '#E60000' },
  badgeSuccess: { backgroundColor: '#28a745' },
  badgeText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  logoutButton: {
    backgroundColor: 'transparent',
    borderColor: '#E60000',
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 15,
    alignItems: 'center',
    marginBottom: 40,
  },
  logoutButtonText: {
    color: '#E60000',
    fontSize: 18,
    fontWeight: 'bold',
  },
  campRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#2a365c',
  },
  campGridName: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  campTeam: {
    color: '#00BFFF',
    fontSize: 12,
    marginTop: 2,
  },
  campPos: {
    color: '#FFCC00',
    fontSize: 16,
    fontWeight: 'bold',
  },
  campPts: {
    color: '#AAA',
    fontSize: 12,
    marginTop: 2,
  },
});
