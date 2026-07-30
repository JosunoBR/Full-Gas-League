import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, Image, RefreshControl } from 'react-native';
import api, { SERVER_BASE_URL } from '../services/api';

export default function NewsScreen() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchNews = async () => {
    try {
      const res = await api.get('/news');
      setNews(res.data || []);
    } catch (error) {
      console.log('[NewsScreen] Erro ao carregar notícias:', error?.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchNews();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchNews();
  };

  if (loading && !refreshing) {
    return (
      <View style={[styles.container, styles.center]}>
        <ActivityIndicator size="large" color="#E60000" />
        <Text style={styles.loadingText}>Carregando notícias...</Text>
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#E60000" />}
    >
      <View style={styles.header}>
        <Text style={styles.title}>📰 Notícias & Comunicados</Text>
        <Text style={styles.subtitle}>Fique por dentro de todas as novidades da FullGas</Text>
      </View>

      {news.length > 0 ? (
        news.map((item, idx) => {
          const imgUrl = item.imagem_url 
            ? (item.imagem_url.startsWith('http') ? item.imagem_url : `${SERVER_BASE_URL}/static/uploads/${item.imagem_url}`)
            : null;

          return (
            <View key={item.id || idx} style={styles.newsCard}>
              {imgUrl && <Image source={{ uri: imgUrl }} style={styles.newsImg} />}
              <View style={styles.newsBody}>
                <Text style={styles.newsDate}>{item.data}</Text>
                <Text style={styles.newsTitle}>{item.titulo}</Text>
                {item.subtitulo && <Text style={styles.newsSubtitle}>{item.subtitulo}</Text>}
                <Text style={styles.newsText}>{item.texto}</Text>
              </View>
            </View>
          );
        })
      ) : (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>Nenhuma notícia publicada recentemente.</Text>
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
  newsCard: {
    backgroundColor: '#1e2745',
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 20,
  },
  newsImg: {
    width: '100%',
    height: 160,
  },
  newsBody: {
    padding: 16,
  },
  newsDate: {
    color: '#E60000',
    fontSize: 11,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  newsTitle: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  newsSubtitle: {
    color: '#00BFFF',
    fontSize: 14,
    marginBottom: 10,
  },
  newsText: {
    color: '#CCC',
    fontSize: 13,
    lineHeight: 18,
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
