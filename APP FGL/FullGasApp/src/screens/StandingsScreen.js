import React, { useState, useEffect, useContext } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Image, Modal } from 'react-native';
import api, { SERVER_BASE_URL } from '../services/api';
import { AuthContext } from '../context/AuthContext';

export default function StandingsScreen() {
  const { tokenReady } = useContext(AuthContext);
  const [standings, setStandings] = useState([]);
  const [teams, setTeams] = useState([]);
  const [activeGrids, setActiveGrids] = useState([]);
  const [selectedGrid, setSelectedGrid] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [viewCategory, setViewCategory] = useState('PILOTS'); // 'PILOTS' ou 'TEAMS'

  // Modal Head-to-Head (X-Ray)
  const [h2hModalVisible, setH2hModalVisible] = useState(false);
  const [h2hData, setH2hData] = useState(null);
  const [loadingH2H, setLoadingH2H] = useState(false);
  const [currentPilotId, setCurrentPilotId] = useState(null);

  const initGridsAndFetch = async (targetGrid = null) => {
    try {
      const [gridConfigsRes, profileRes] = await Promise.all([
        api.get('/grid-configs').catch(() => ({ data: [] })),
        api.get('/profile').catch(() => ({ data: {} }))
      ]);

      if (profileRes.data?.id) setCurrentPilotId(profileRes.data.id);

      const gridNames = (gridConfigsRes.data || []).map(g => g.nome);
      setActiveGrids(gridNames);

      const activeTarget = targetGrid || (gridNames.includes(selectedGrid) ? selectedGrid : (gridNames.length > 0 ? gridNames[0] : ''));
      if (activeTarget) {
        setSelectedGrid(activeTarget);
        const [standingsRes, constructorsRes] = await Promise.all([
          api.get(`/standings/${encodeURIComponent(activeTarget)}`).catch(() => ({ data: [] })),
          api.get(`/constructors/${encodeURIComponent(activeTarget)}`).catch(() => ({ data: [] }))
        ]);
        setStandings(standingsRes.data || []);
        setTeams(constructorsRes.data || []);
      }
    } catch (error) {
      console.log('[StandingsScreen] Erro ao carregar classificação:', error?.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (tokenReady) initGridsAndFetch();
  }, [tokenReady]);

  const onRefresh = () => {
    setRefreshing(true);
    initGridsAndFetch(selectedGrid);
  };

  const handleGridChange = (grid) => {
    setSelectedGrid(grid);
    setLoading(true);
    initGridsAndFetch(grid);
  };

  const handleOpenH2H = async (opponentId) => {
    if (!currentPilotId || currentPilotId === opponentId) return;
    setLoadingH2H(true);
    setH2hModalVisible(true);
    try {
      const res = await api.get(`/head-to-head/${currentPilotId}/${opponentId}`);
      setH2hData(res.data);
    } catch (error) {
      console.log('[StandingsScreen] Erro H2H:', error?.message);
      setH2hData(null);
    } finally {
      setLoadingH2H(false);
    }
  };

  if (loading && !refreshing) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color="#E60000" />
        <Text style={styles.loadingText}>Carregando tabela...</Text>
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#E60000" />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>🏆 Classificação & Equipes</Text>
        <Text style={styles.subtitle}>Tabela oficial da temporada & comparativo X-Ray</Text>
      </View>

      {/* Mode Switch (Pilotos vs Construtores) */}
      <View style={styles.categoryTabs}>
        <TouchableOpacity 
          style={[styles.catTab, viewCategory === 'PILOTS' && styles.catTabActive]}
          onPress={() => setViewCategory('PILOTS')}
        >
          <Text style={[styles.catTabText, viewCategory === 'PILOTS' && styles.catTabTextActive]}>🏎️ Pilotos</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.catTab, viewCategory === 'TEAMS' && styles.catTabActive]}
          onPress={() => setViewCategory('TEAMS')}
        >
          <Text style={[styles.catTabText, viewCategory === 'TEAMS' && styles.catTabTextActive]}>🛡️ Construtores (Equipes)</Text>
        </TouchableOpacity>
      </View>

      {/* Grid Selector (Ativos) */}
      <View style={styles.gridTabs}>
        {activeGrids.map((g) => (
          <TouchableOpacity 
            key={g} 
            style={[styles.gridTab, selectedGrid === g && styles.gridTabActive]}
            onPress={() => handleGridChange(g)}
          >
            <Text style={[styles.gridTabText, selectedGrid === g && styles.gridTabTextActive]}>{g}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Standings / Teams List */}
      <View style={styles.card}>
        {viewCategory === 'PILOTS' ? (
          standings.length > 0 ? (
            standings.map((item, index) => {
              const fotoUrl = item.foto 
                ? (item.foto.startsWith('http') ? item.foto : `${SERVER_BASE_URL}/static/uploads/${item.foto}`)
                : 'https://via.placeholder.com/50';

              const isMe = item.id === currentPilotId;

              return (
                <View key={item.id || index} style={[styles.row, isMe && styles.rowMe]}>
                  <Text style={styles.posText}>{index + 1}º</Text>
                  <Image source={{ uri: fotoUrl }} style={styles.avatar} />
                  <View style={styles.pilotDetails}>
                    <Text style={styles.nickname}>{item.nickname} {isMe && '(Você)'}</Text>
                  </View>
                  <Text style={styles.pointsText}>{item.pontos} pts</Text>

                  {!isMe && currentPilotId && (
                    <TouchableOpacity style={styles.h2hBtn} onPress={() => handleOpenH2H(item.id)}>
                      <Text style={styles.h2hBtnText}>⚔️ X-Ray</Text>
                    </TouchableOpacity>
                  )}
                </View>
              );
            })
          ) : (
            <Text style={styles.emptyText}>Nenhum piloto encontrado para o grid {selectedGrid}.</Text>
          )
        ) : (
          teams.length > 0 ? (
            teams.map((t, idx) => {
              const logoUrl = t.logo 
                ? (t.logo.startsWith('http') ? t.logo : `${SERVER_BASE_URL}/static/uploads/${t.logo}`)
                : 'https://via.placeholder.com/50';

              return (
                <View key={t.id || idx} style={styles.row}>
                  <Text style={styles.posText}>{t.posicao || (idx + 1)}º</Text>
                  <Image source={{ uri: logoUrl }} style={styles.avatar} />
                  <View style={styles.pilotDetails}>
                    <Text style={styles.nickname}>{t.nome}</Text>
                    <Text style={styles.teamGrid}>🏆 {t.vitorias || 0} Vitória(s)</Text>
                  </View>
                  <Text style={styles.pointsText}>{t.pontos} pts</Text>
                </View>
              );
            })
          ) : (
            <Text style={styles.emptyText}>Nenhuma pontuação de construtores registrada para o grid {selectedGrid}.</Text>
          )
        )}
      </View>

      {/* Modal Head-to-Head (X-Ray) */}
      <Modal visible={h2hModalVisible} animationType="slide" transparent={true}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            <Text style={styles.modalTitle}>⚔️ Comparativo X-Ray (Head-to-Head)</Text>
            
            {loadingH2H ? (
              <ActivityIndicator size="large" color="#E60000" style={{ marginVertical: 30 }} />
            ) : h2hData ? (
              <View style={{ marginVertical: 15 }}>
                <View style={styles.h2hVSContainer}>
                  <View style={styles.h2hPilotBox}>
                    <Text style={styles.h2hPilotName}>{h2hData.p1?.nickname}</Text>
                    <Text style={styles.h2hScore}>{h2hData.p1?.h2h_vitorias}</Text>
                    <Text style={styles.h2hLabel}>Vitórias à Frente</Text>
                  </View>

                  <Text style={styles.vsText}>VS</Text>

                  <View style={styles.h2hPilotBox}>
                    <Text style={styles.h2hPilotName}>{h2hData.p2?.nickname}</Text>
                    <Text style={styles.h2hScore}>{h2hData.p2?.h2h_vitorias}</Text>
                    <Text style={styles.h2hLabel}>Vitórias à Frente</Text>
                  </View>
                </View>
                <Text style={styles.h2hSubText}>Corridas disputadas juntos nesta temporada: {h2hData.corridas_em_comum}</Text>
              </View>
            ) : (
              <Text style={styles.emptyText}>Sem dados suficientes para comparação direta.</Text>
            )}

            <TouchableOpacity style={styles.closeBtn} onPress={() => setH2hModalVisible(false)}>
              <Text style={styles.closeBtnText}>Fechar</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
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
    marginTop: 40,
    marginBottom: 15,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
  },
  subtitle: {
    fontSize: 14,
    color: '#888',
    marginTop: 4,
  },
  categoryTabs: {
    flexDirection: 'row',
    marginBottom: 15,
    backgroundColor: '#1e2745',
    borderRadius: 8,
    padding: 4,
  },
  catTab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 6,
  },
  catTabActive: {
    backgroundColor: '#E60000',
  },
  catTabText: {
    color: '#AAA',
    fontWeight: 'bold',
    fontSize: 14,
  },
  catTabTextActive: {
    color: '#FFF',
  },
  gridTabs: {
    flexDirection: 'row',
    marginBottom: 15,
    gap: 10,
  },
  gridTab: {
    flex: 1,
    backgroundColor: '#1e2745',
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
  },
  gridTabActive: {
    backgroundColor: '#2a365c',
    borderWidth: 1,
    borderColor: '#00BFFF',
  },
  gridTabText: {
    color: '#AAA',
    fontWeight: 'bold',
    fontSize: 12,
  },
  gridTabTextActive: {
    color: '#00BFFF',
  },
  card: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    padding: 15,
    marginBottom: 20,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2a365c',
  },
  rowMe: {
    backgroundColor: 'rgba(0, 191, 255, 0.1)',
    borderRadius: 8,
    paddingHorizontal: 8,
  },
  posText: {
    width: 30,
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFCC00',
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    marginRight: 10,
    borderWidth: 1,
    borderColor: '#333',
  },
  pilotDetails: {
    flex: 1,
  },
  nickname: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: 'bold',
  },
  teamGrid: {
    color: '#888',
    fontSize: 12,
  },
  pointsText: {
    color: '#00BFFF',
    fontSize: 15,
    fontWeight: 'bold',
    marginRight: 8,
  },
  h2hBtn: {
    backgroundColor: '#2a365c',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  h2hBtnText: {
    color: '#FFCC00',
    fontSize: 11,
    fontWeight: 'bold',
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
    textAlign: 'center',
    paddingVertical: 20,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContainer: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    padding: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 10,
    textAlign: 'center',
  },
  h2hVSContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    marginVertical: 15,
  },
  h2hPilotBox: {
    alignItems: 'center',
    flex: 1,
  },
  h2hPilotName: {
    color: '#FFF',
    fontWeight: 'bold',
    fontSize: 15,
    marginBottom: 4,
  },
  h2hScore: {
    color: '#FFCC00',
    fontSize: 36,
    fontWeight: 'bold',
  },
  h2hLabel: {
    color: '#AAA',
    fontSize: 11,
  },
  vsText: {
    color: '#E60000',
    fontSize: 22,
    fontWeight: 'bold',
    marginHorizontal: 10,
  },
  h2hSubText: {
    color: '#888',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 10,
  },
  closeBtn: {
    backgroundColor: '#2a365c',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 15,
  },
  closeBtnText: {
    color: '#FFF',
    fontWeight: 'bold',
  },
});
