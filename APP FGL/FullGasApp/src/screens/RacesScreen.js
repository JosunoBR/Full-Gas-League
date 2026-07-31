import React, { useState, useEffect, useContext } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Modal } from 'react-native';
import api from '../services/api';
import { AuthContext } from '../context/AuthContext';

export default function RacesScreen() {
  const { tokenReady } = useContext(AuthContext);
  const [races, setRaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Súmula Modal
  const [summaryModalVisible, setSummaryModalVisible] = useState(false);
  const [selectedRaceSummary, setSelectedRaceSummary] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  const fetchCalendar = async () => {
    try {
      const profileRes = await api.get('/profile');
      const grid = profileRes.data?.grid_id || 'ELITE';
      const calendarRes = await api.get(`/calendar/${grid}`);
      setRaces(calendarRes.data || []);
    } catch (error) {
      console.log('[RacesScreen] Erro ao carregar calendário:', error?.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (tokenReady) fetchCalendar();
  }, [tokenReady]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchCalendar();
  };

  const handleOpenSummary = async (raceId) => {
    setLoadingSummary(true);
    setSummaryModalVisible(true);
    try {
      const res = await api.get(`/race/${raceId}/results`);
      setSelectedRaceSummary(res.data);
    } catch (error) {
      console.log('[RacesScreen] Erro ao carregar súmula:', error?.message);
      setSelectedRaceSummary(null);
    } finally {
      setLoadingSummary(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color="#E60000" />
        <Text style={styles.loadingText}>Carregando calendário...</Text>
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#E60000" />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>🏁 Corridas & Calendário</Text>
        <Text style={styles.subtitle}>Etapas, briefing de lobby e súmula da corrida</Text>
      </View>

      {races.length > 0 ? (
        races.map((race, idx) => (
          <View key={race.id || idx} style={styles.raceCard}>
            <View style={styles.raceHeader}>
              <Text style={styles.raceName}>{race.nome_gp}</Text>
              <View style={[styles.statusBadge, race.status === 'Concluida' ? styles.badgeSuccess : styles.badgeInfo]}>
                <Text style={styles.statusText}>{race.status || 'Agendada'}</Text>
              </View>
            </View>

            <Text style={styles.raceDetail}>📍 Pista: {race.pista}</Text>
            <Text style={styles.raceDetail}>📅 Data: {race.data}</Text>
            <Text style={styles.raceDetail}>🏎️ Grid: {race.grid}</Text>

            <TouchableOpacity style={styles.detailButton} onPress={() => handleOpenSummary(race.id)}>
              <Text style={styles.detailButtonText}>
                {race.status === 'Concluida' ? '📊 Ver Súmula da Etapa' : 'ℹ️ Ver Briefing da Etapa'}
              </Text>
            </TouchableOpacity>
          </View>
        ))
      ) : (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>Nenhuma corrida agendada para o seu grid no momento.</Text>
        </View>
      )}

      {/* Modal de Súmula / Briefing */}
      <Modal visible={summaryModalVisible} animationType="slide" transparent={true}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            <Text style={styles.modalTitle}>Detalhes da Etapa</Text>
            
            {loadingSummary ? (
              <ActivityIndicator size="large" color="#E60000" style={{ marginVertical: 30 }} />
            ) : selectedRaceSummary ? (
              <ScrollView style={{ maxHeight: 400 }}>
                <Text style={styles.summaryGp}>{selectedRaceSummary.nome_gp}</Text>
                <Text style={styles.summaryInfo}>Pista: {selectedRaceSummary.pista}</Text>
                <Text style={styles.summaryInfo}>Data: {selectedRaceSummary.data_corrida || 'N/A'}</Text>

                {selectedRaceSummary.pole_sitter && (
                  <View style={styles.poleBox}>
                    <Text style={styles.poleTitle}>⏱️ Pole Position</Text>
                    <Text style={styles.poleText}>{selectedRaceSummary.pole_sitter} ({selectedRaceSummary.pole_time || 'N/A'})</Text>
                  </View>
                )}

                <Text style={[styles.summaryGp, { fontSize: 16, marginTop: 15 }]}>Classificação da Corrida</Text>
                {selectedRaceSummary.resultados && selectedRaceSummary.resultados.map((res, i) => (
                  <View key={i} style={styles.summaryRow}>
                    <Text style={styles.posText}>P{res.posicao}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.pilotText}>{res.piloto}</Text>
                      <Text style={styles.teamText}>{res.equipe} • {res.pit_stops || 0} Pit(s)</Text>
                      {res.pneus_stints && <Text style={styles.stintsText}>Pneus: {res.pneus_stints}</Text>}
                    </View>
                    <Text style={styles.ptsText}>+{res.pontos} pts</Text>
                  </View>
                ))}
              </ScrollView>
            ) : (
              <Text style={styles.emptyText}>Informações da etapa indisponíveis.</Text>
            )}

            <TouchableOpacity style={styles.closeBtn} onPress={() => setSummaryModalVisible(false)}>
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
    marginBottom: 20,
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
  raceCard: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    padding: 16,
    marginBottom: 15,
    borderLeftWidth: 4,
    borderLeftColor: '#E60000',
  },
  raceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  raceName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFF',
    flex: 1,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  badgeSuccess: { backgroundColor: '#28a745' },
  badgeInfo: { backgroundColor: '#00BFFF' },
  statusText: {
    color: '#FFF',
    fontSize: 11,
    fontWeight: 'bold',
  },
  raceDetail: {
    color: '#CCC',
    fontSize: 14,
    marginBottom: 4,
  },
  detailButton: {
    marginTop: 12,
    backgroundColor: '#2a365c',
    paddingVertical: 10,
    borderRadius: 6,
    alignItems: 'center',
  },
  detailButtonText: {
    color: '#00BFFF',
    fontWeight: 'bold',
    fontSize: 13,
  },
  emptyCard: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
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
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 10,
  },
  summaryGp: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#E60000',
    marginBottom: 4,
  },
  summaryInfo: {
    color: '#DDD',
    fontSize: 14,
    marginBottom: 2,
  },
  poleBox: {
    backgroundColor: '#2a365c',
    borderRadius: 8,
    padding: 10,
    marginVertical: 10,
  },
  poleTitle: {
    color: '#FFCC00',
    fontSize: 12,
    fontWeight: 'bold',
  },
  poleText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
    marginTop: 2,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2a365c',
  },
  posText: {
    width: 35,
    fontSize: 14,
    fontWeight: 'bold',
    color: '#00BFFF',
  },
  pilotText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  teamText: {
    color: '#AAA',
    fontSize: 12,
  },
  stintsText: {
    color: '#888',
    fontSize: 11,
    fontStyle: 'italic',
  },
  ptsText: {
    color: '#28a745',
    fontSize: 14,
    fontWeight: 'bold',
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
