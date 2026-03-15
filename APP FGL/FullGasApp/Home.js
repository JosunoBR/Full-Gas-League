import React, { useContext } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { AuthContext } from '../context/AuthContext';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function Home() {
  const { user, signOut } = useContext(AuthContext);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.welcome}>Olá, {user?.nickname}!</Text>
        <TouchableOpacity onPress={signOut} style={styles.logoutButton}>
          <Text style={styles.logoutText}>Sair</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.content}>
        <Text style={styles.text}>Login realizado com sucesso!</Text>
        <Text style={styles.subtext}>Em breve: Seu Perfil e Check-in aqui.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0f1d' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#1E1E1E',
  },
  welcome: { color: '#fff', fontSize: 20, fontWeight: 'bold' },
  logoutButton: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: '#333',
    borderRadius: 5,
  },
  logoutText: { color: '#fff', fontWeight: 'bold' },
  content: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 20 },
  text: { color: '#4ade80', fontSize: 18, fontWeight: 'bold', marginBottom: 10 },
  subtext: { color: '#6c757d', textAlign: 'center', fontSize: 16 }
});