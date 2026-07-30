import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, Image, RefreshControl } from 'react-native';
import api, { SERVER_BASE_URL } from '../services/api';

export default function HallOfFameScreen() {
  const [champions, setChampions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHallOfFame = async () => {
    try {
      const res = await api.get('/hall-of-fame');
      setChampions(res.data || []);
    } catch (error) {
      console.log('[HallOfFameScreen] Erro ao carregar Hall da Fama:', error?.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHallOfFame();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchHallOfFame();
  };

  if (loading && !refreshing) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color="#E60000" />
        <Text style={styles.loadingText}>Carregando Hall da Fama...</Text>
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#E60000" />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>🏛️ Hall da Fama</Text>
        <Text style={styles.subtitle}>Os lendários campeões da FullGas League</Text>
      </View>

      {champions.length > 0 ? (
        champions.map((c, idx) => {
          const imgUrl = c.image_url 
            ? (c.image_url.startsWith('http') ? c.image_url : `${SERVER_BASE_URL}/static/uploads/${c.image_url}`)
            : null;

          return (
            <View key={idx} style={styles.champCard}>
              <View style={styles.champBadgeHeader}>
                <Text style={styles.seasonBadge}>{c.season}</Text>
                <Text style={styles.gridBadge}>{c.grid}</Text>
              </View>

              <View style={styles.champBody}>
                {imgUrl && <Image source={{ uri: imgUrl }} style={styles.champAvatar} />}
                <View style={styles.champInfo}>
                  <Text style={styles.champPosition}>🏆 {c.position}º Lugar ({c.category === 'PILOT' ? 'Piloto' : 'Construtores'})</Text>
                  <Text style={styles.champName}>{c.name}</Text>
                  {c.team_name && <Text style={styles.teamName}>Equipe: {c.team_name}</Text>}
                  <Text style={styles.statsText}>{c.pontos} pts • {c.vitorias} Vitória(s)</Text>
                </View>
              </View>
            </View>
          );
        })
      ) : (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>Nenhum campeão congelado no Hall da Fama ainda.</Text>
        </View>
      )}
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
  champCard: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    padding: 16,
    marginBottom: 15,
    borderLeftWidth: 4,
    borderLeftColor: '#FFCC00',
  },
  champBadgeHeader: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  seasonBadge: {
    backgroundColor: '#E60000',
    color: '#FFF',
    fontSize: 11,
    fontWeight: 'bold',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  gridBadge: {
    backgroundColor: '#2a365c',
    color: '#00BFFF',
    fontSize: 11,
    fontWeight: 'bold',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  champBody: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  champAvatar: {
    width: 60,
    height: 60,
    borderRadius: 30,
    marginRight: 14,
    borderWidth: 2,
    borderColor: '#FFCC00',
  },
  champInfo: {
    flex: 1,
  },
  champPosition: {
    color: '#FFCC00',
    fontSize: 12,
    fontWeight: 'bold',
  },
  champName: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 2,
  },
  teamName: {
    color: '#AAA',
    fontSize: 13,
  },
  statsText: {
    color: '#00BFFF',
    fontSize: 12,
    marginTop: 4,
    fontWeight: 'bold',
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
});
