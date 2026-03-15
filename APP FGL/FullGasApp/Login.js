import React, { useState, useContext } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { AuthContext } from '../context/AuthContext';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function Login() {
  const { signIn } = useContext(AuthContext);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email || !password) {
      Alert.alert('Atenção', 'Preencha todos os campos!');
      return;
    }

    setLoading(true);
    const response = await signIn(email.trim().toLowerCase(), password);
    setLoading(false);

    if (!response.success) {
      Alert.alert('Erro no Login', response.msg);
    }
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        
        <View style={styles.logoContainer}>
          <Text style={styles.logoText}>FULL GAS</Text>
          <Text style={styles.logoSubText}>LEAGUE</Text>
        </View>

        <Text style={styles.title}>Acesso do Piloto</Text>

        <TextInput
          style={styles.input}
          placeholder="E-mail"
          placeholderTextColor="#6c757d"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
        />

        <TextInput
          style={styles.input}
          placeholder="Senha"
          placeholderTextColor="#6c757d"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />

        <TouchableOpacity style={styles.button} onPress={handleLogin} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>ENTRAR</Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0f1d' },
  content: { flex: 1, justifyContent: 'center', paddingHorizontal: 30 },
  logoContainer: { alignItems: 'center', marginBottom: 40 },
  logoText: { fontSize: 42, fontWeight: 'bold', color: '#E60000', letterSpacing: 2 },
  logoSubText: { fontSize: 18, letterSpacing: 6, color: '#d8dbe1' },
  title: { fontSize: 18, color: '#fff', marginBottom: 20, textAlign: 'center', fontWeight: 'bold' },
  input: {
    backgroundColor: '#1E1E1E',
    color: '#fff',
    borderRadius: 8,
    padding: 15,
    marginBottom: 15,
    borderWidth: 1,
    borderColor: '#333',
    fontSize: 16,
  },
  button: {
    backgroundColor: '#E60000',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 10,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: 'bold', letterSpacing: 1 },
});