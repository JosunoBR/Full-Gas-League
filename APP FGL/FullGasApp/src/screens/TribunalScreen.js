import React, { useState, useEffect, useContext } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert, RefreshControl, Modal, TextInput } from 'react-native';
import api from '../services/api';
import { AuthContext } from '../context/AuthContext';

export default function TribunalScreen() {
  const { tokenReady } = useContext(AuthContext);
  const [profile, setProfile] = useState(null);
  const [protestsFeitos, setProtestsFeitos] = useState([]);
  const [protestsRecebidos, setProtestsRecebidos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Modais
  const [defenseModalVisible, setDefenseModalVisible] = useState(false);
  const [selectedProtest, setSelectedProtest] = useState(null);
  const [defenseVideo, setDefenseVideo] = useState('');
  const [defenseArg, setDefenseArg] = useState('');
  const [submittingDefense, setSubmittingDefense] = useState(false);

  const fetchTribunalData = async () => {
    try {
      const [profileRes, protestsRes] = await Promise.all([
        api.get('/profile'),
        api.get('/protests').catch(() => ({ data: { protestos_feitos: [], protestos_recebidos: [] } }))
      ]);
      setProfile(profileRes.data);
      setProtestsFeitos(protestsRes.data?.protestos_feitos || []);
      setProtestsRecebidos(protestsRes.data?.protestos_recebidos || []);
    } catch (error) {
      console.log('[TribunalScreen] Erro ao carregar dados:', error?.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (tokenReady) fetchTribunalData();
  }, [tokenReady]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchTribunalData();
  };

  const handleOpenDefenseModal = (protest) => {
    setSelectedProtest(protest);
    setDefenseVideo(protest.video_defesa || '');
    setDefenseArg(protest.argumento_defesa || '');
    setDefenseModalVisible(true);
  };

  const handleSubmitDefense = async () => {
    if (!selectedProtest) return;
    if (!defenseArg.trim()) {
      Alert.alert('Atenção', 'Por favor informe o argumento de defesa.');
      return;
    }

    setSubmittingDefense(true);
    try {
      await api.post(`/protests/${selectedProtest.id}/defense`, {
        video_defesa: defenseVideo,
        argumento_defesa: defenseArg,
      });
      Alert.alert('Sucesso!', 'Sua defesa foi submetida e enviada aos comissários.');
      setDefenseModalVisible(false);
      fetchTribunalData();
    } catch (error) {
      Alert.alert('Erro', error?.response?.data?.msg || 'Não foi possível enviar a defesa.');
    } finally {
      setSubmittingDefense(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color="#E60000" />
        <Text style={styles.loadingText}>Carregando tribunal...</Text>
      </View>
    );
  }

  const cnhPontos = profile?.cnh_pontos ?? 25;
  const cnhStatus = profile?.cnh_status || 'OK';

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#E60000" />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>⚖️ Tribunal Virtual</Text>
        <Text style={styles.subtitle}>Ouvidoria de incidentes & acompanhamento de julgamentos</Text>
      </View>

      {/* CNH Gauge Card */}
      <View style={styles.cnhCard}>
        <Text style={styles.cnhTitle}>Carteira de Habilitação (CNH)</Text>
        <View style={styles.cnhScoreContainer}>
          <Text style={[
            styles.cnhScore, 
            cnhPontos <= 0 ? { color: '#E60000' } : (cnhPontos <= 10 ? { color: '#FFCC00' } : { color: '#28a745' })
          ]}>
            {cnhPontos} / 25
          </Text>
          <Text style={styles.cnhUnit}>pontos</Text>
        </View>
        <View style={styles.cnhStatusBadge}>
          <Text style={styles.cnhStatusText}>Status: {cnhStatus}</Text>
        </View>
      </View>

      {/* Protestos Recebidos (Defesas Pendentes) */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Protestos Recebidos (Sua Defesa)</Text>
        {protestsRecebidos.length > 0 ? (
          protestsRecebidos.map((p) => (
            <View key={p.id} style={styles.protestItem}>
              <View style={styles.protestHeader}>
                <Text style={styles.protestGp}>GP: {p.etapa}</Text>
                <View style={[styles.statusBadge, p.status === 'CONCLUIDO' ? styles.badgeSuccess : styles.badgeWarning]}>
                  <Text style={styles.badgeText}>{p.status}</Text>
                </View>
              </View>
              <Text style={styles.protestDetail}>Acusador: {p.acusador}</Text>
              <Text style={styles.protestDetail}>Minuto: {p.minuto || 'N/A'}</Text>
              <Text style={styles.protestDesc}>"{p.descricao || 'Sem descrição'}"</Text>

              {p.status === 'AGUARDANDO_DEFESA' && (
                <TouchableOpacity style={styles.defenseBtn} onPress={() => handleOpenDefenseModal(p)}>
                  <Text style={styles.defenseBtnText}>📹 Enviar Defesa</Text>
                </TouchableOpacity>
              )}
            </View>
          ))
        ) : (
          <Text style={styles.emptyText}>Você não possui protestos contra você no momento.</Text>
        )}
      </View>

      {/* Protestos Efetuados */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Protestos Abertos por Você</Text>
        {protestsFeitos.length > 0 ? (
          protestsFeitos.map((p) => (
            <View key={p.id} style={styles.protestItem}>
              <View style={styles.protestHeader}>
                <Text style={styles.protestGp}>GP: {p.etapa}</Text>
                <Text style={styles.statusText}>{p.status}</Text>
              </View>
              <Text style={styles.protestDetail}>Acusado: {p.acusado}</Text>
              {p.veredito && <Text style={styles.vereditoText}>Veredito: {p.veredito}</Text>}
            </View>
          ))
        ) : (
          <Text style={styles.emptyText}>Você não abriu protestos recentemente.</Text>
        )}
      </View>

      {/* Modal de Defesa */}
      <Modal visible={defenseModalVisible} animationType="slide" transparent={true}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContainer}>
            <Text style={styles.modalTitle}>Enviar Defesa de Incidentes</Text>
            <Text style={styles.modalSubtitle}>GP {selectedProtest?.etapa} — Acusador: {selectedProtest?.acusador}</Text>

            <Text style={styles.inputLabel}>Link do Vídeo da Defesa (YouTube / Twitch):</Text>
            <TextInput
              style={styles.input}
              placeholder="https://youtu.be/..."
              placeholderTextColor="#666"
              value={defenseVideo}
              onChangeText={setDefenseVideo}
            />

            <Text style={styles.inputLabel}>Argumentação da Defesa:</Text>
            <TextInput
              style={[styles.input, styles.textArea]}
              placeholder="Explique o lance sob seu ponto de vista..."
              placeholderTextColor="#666"
              multiline={true}
              numberOfLines={4}
              value={defenseArg}
              onChangeText={setDefenseArg}
            />

            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setDefenseModalVisible(false)}>
                <Text style={styles.cancelBtnText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.submitBtn} onPress={handleSubmitDefense} disabled={submittingDefense}>
                {submittingDefense ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitBtnText}>Enviar Defesa</Text>}
              </TouchableOpacity>
            </View>
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
  cnhCard: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginBottom: 20,
    borderTopWidth: 4,
    borderTopColor: '#E60000',
  },
  cnhTitle: {
    color: '#AAA',
    fontSize: 14,
    marginBottom: 10,
  },
  cnhScoreContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  cnhScore: {
    fontSize: 42,
    fontWeight: 'bold',
  },
  cnhUnit: {
    color: '#888',
    fontSize: 16,
    marginLeft: 6,
  },
  cnhStatusBadge: {
    backgroundColor: '#2a365c',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
    marginTop: 8,
  },
  cnhStatusText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  card: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFF',
    marginBottom: 15,
  },
  protestItem: {
    backgroundColor: '#2a365c',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  protestHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  protestGp: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  badgeWarning: { backgroundColor: '#FFCC00' },
  badgeSuccess: { backgroundColor: '#28a745' },
  badgeText: {
    color: '#000',
    fontSize: 10,
    fontWeight: 'bold',
  },
  statusText: {
    color: '#00BFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  protestDetail: {
    color: '#DDD',
    fontSize: 13,
    marginBottom: 2,
  },
  protestDesc: {
    color: '#AAA',
    fontSize: 13,
    fontStyle: 'italic',
    marginTop: 4,
  },
  vereditoText: {
    color: '#E60000',
    fontSize: 13,
    fontWeight: 'bold',
    marginTop: 4,
  },
  defenseBtn: {
    backgroundColor: '#E60000',
    borderRadius: 6,
    paddingVertical: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  defenseBtnText: {
    color: '#FFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
    textAlign: 'center',
    paddingVertical: 10,
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
    marginBottom: 4,
  },
  modalSubtitle: {
    fontSize: 13,
    color: '#888',
    marginBottom: 15,
  },
  inputLabel: {
    color: '#DDD',
    fontSize: 14,
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#2a365c',
    color: '#FFF',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    marginBottom: 15,
  },
  textArea: {
    height: 90,
    textAlignVertical: 'top',
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
  },
  cancelBtn: {
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  cancelBtnText: {
    color: '#AAA',
    fontWeight: 'bold',
  },
  submitBtn: {
    backgroundColor: '#E60000',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  submitBtnText: {
    color: '#FFF',
    fontWeight: 'bold',
  },
});
