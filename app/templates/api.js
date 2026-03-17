import axios from 'axios';

// ATENÇÃO: Substitua '192.168.1.5' pelo IPv4 do seu computador (veja no comando ipconfig)
// Se estiver usando Emulador do Android Studio, use 'http://10.0.2.2:5000/api'
const BASE_URL = 'http://192.168.1.5:5000/api'; 

const api = axios.create({
  baseURL: BASE_URL,
});

export default api;