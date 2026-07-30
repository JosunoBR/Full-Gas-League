import React, { useState, useEffect, useContext } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Image, Alert, RefreshControl } from 'react-native';
import api, { SERVER_BASE_URL } from '../services/api';
import { AuthContext } from '../context/AuthContext';

import NewsScreen from './NewsScreen';
import HallOfFameScreen from './HallOfFameScreen';

export default function ProfileScreen() {
  const { user, signOut, tokenReady } = useContext(AuthContext);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Modais de Mídia
  const [newsModalVisible, setNewsModalVisible] = useState(false);
  const [hallModalVisible, setHallModalVisible] = useState(false);

  const fetchProfile = async () => {
    try {
      const res = await api.get('/profile');
      setProfile(res.data);
    } catch (error) {
      console.log('[ProfileScreen] Erro ao carregar perfil:', error?.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (tokenReady) fetchProfile();
  }, [tokenReady]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchProfile();
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color="#E60000" />
        <Text style={styles.loadingText}>Carregando perfil...</Text>
      </View>
    );
  }

  const profileImageUrl = profile?.foto_url 
    ? (profile.foto_url.startsWith('http') ? profile.foto_url : `${SERVER_BASE_URL}/static/uploads/${profile.foto_url}`)
    : 'https://via.placeholder.com/150';

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#E60000" />}
    >
      <View style={styles.header}>
        <Image source={{ uri: profileImageUrl }} style={styles.profileImage} />
        <Text style={styles.userName}>{profile?.nickname || user?.username}</Text>
        <Text style={styles.realName}>{profile?.nome_real}</Text>
        <Text style={styles.teamName}>🏎️ {profile?.equipe_atual || 'Sem Equipe'}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Dados Pessoais</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Nickname:</Text>
          <Text style={styles.infoValue}>{profile?.nickname}</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>CNH Pontos:</Text>
          <Text style={styles.infoValue}>{profile?.cnh_pontos} pts</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Status CNH:</Text>
          <Text style={styles.infoValue}>{profile?.cnh_status}</Text>
        </View>

        <TouchableOpacity 
          style={styles.actionBtn}
          onPress={() => Alert.alert('Fotos por Grid', 'Para enviar fotos customizadas de macacão para cada grid, utilize a aba de Perfil no portal web.')}
        >
          <Text style={styles.actionBtnText}>🖼️ Fotos por Grid (Macacões)</Text>
        </TouchableOpacity>
      </View>

      {/* Seção de Mídia e Hall da Fama */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Liga & Mídia</Text>
        <TouchableOpacity 
          style={styles.mediaBtn}
          onPress={() => setNewsModalVisible(true)}
        >
          <Text style={styles.mediaBtnText}>📰 Ver Notícias & Comunicados</Text>
        </TouchableOpacity>

        <TouchableOpacity 
          style={[styles.mediaBtn, { marginTop: 10 }]}
          onPress={() => setHallModalVisible(true)}
        >
          <Text style={styles.mediaBtnText}>🏛️ Ver Hall da Fama</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={signOut}>
        <Text style={styles.logoutButtonText}>Sair da Conta</Text>
      </TouchableOpacity>

      {/* Modal Notícias */}
      <Modal visible={newsModalVisible} animationType="slide" transparent={false}>
        <View style={{ flex: 1, backgroundColor: '#000000' }}>
          <TouchableOpacity style={styles.modalCloseHeader} onPress={() => setNewsModalVisible(false)}>
            <Text style={styles.modalCloseText}>← Voltar para Perfil</Text>
          </TouchableOpacity>
          <NewsScreen />
        </View>
      </Modal>

      {/* Modal Hall da Fama */}
      <Modal visible={hallModalVisible} animationType="slide" transparent={false}>
        <View style={{ flex: 1, backgroundColor: '#000000' }}>
          <TouchableOpacity style={styles.modalCloseHeader} onPress={() => setHallModalVisible(false)}>
            <Text style={styles.modalCloseText}>← Voltar para Perfil</Text>
          </TouchableOpacity>
          <HallOfFameScreen />
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
    alignItems: 'center',
    marginBottom: 20,
  },
  profileImage: {
    width: 110,
    height: 110,
    borderRadius: 55,
    borderWidth: 3,
    borderColor: '#E60000',
    marginBottom: 12,
  },
  userName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFF',
  },
  realName: {
    fontSize: 14,
    color: '#888',
    marginTop: 2,
  },
  teamName: {
    fontSize: 16,
    color: '#00BFFF',
    marginTop: 6,
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
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2a365c',
  },
  infoLabel: {
    color: '#AAA',
    fontSize: 14,
  },
  infoValue: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: 'bold',
  },
  actionBtn: {
    backgroundColor: '#2a365c',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 15,
  },
  actionBtnText: {
    color: '#00BFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  mediaBtn: {
    backgroundColor: '#2a365c',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 15,
  },
  mediaBtnText: {
    color: '#FFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  modalCloseHeader: {
    paddingTop: 45,
    paddingBottom: 15,
    paddingHorizontal: 20,
    backgroundColor: '#1e2745',
  },
  modalCloseText: {
    color: '#00BFFF',
    fontWeight: 'bold',
    fontSize: 16,
  },
  logoutButton: {
    backgroundColor: 'transparent',
    borderColor: '#E60000',
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 40,
  },
  logoutButtonText: {
    color: '#E60000',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
