import axios from 'axios'

const API_BASE = '/api'
const TOKEN_KEY = 'monitor_access_token'

export const authStore = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY)
  },
  setToken(token) {
    localStorage.setItem(TOKEN_KEY, token)
  },
  clearToken() {
    localStorage.removeItem(TOKEN_KEY)
  }
}

const api = axios.create({
  baseURL: API_BASE
})

api.interceptors.request.use((config) => {
  const token = authStore.getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      authStore.clearToken()
      window.dispatchEvent(new CustomEvent('auth-expired'))
    }
    return Promise.reject(error)
  }
)

export const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password })
  authStore.setToken(response.data.access_token)
  return response.data
}

export const logout = async () => {
  try {
    await api.post('/auth/logout')
  } finally {
    authStore.clearToken()
  }
}

export const getCurrentUser = async () => {
  const response = await api.get('/auth/me')
  return response.data.user
}

export const getDevices = async () => {
  const response = await api.get('/devices')
  return response.data.devices || []
}

export const getHistoryData = async (deviceId, limit = 50) => {
  if (!deviceId) return []
  const response = await api.get('/history', {
    params: { device_id: deviceId, limit }
  })
  return response.data.history || []
}

export const getLatestData = async (deviceId) => {
  const response = await api.get('/latest', {
    params: deviceId ? { device_id: deviceId } : {}
  })
  return response.data.data
}

export const listUsers = async () => {
  const response = await api.get('/admin/users')
  return response.data.users || []
}

export const createUser = async (payload) => {
  const response = await api.post('/admin/users', payload)
  return response.data.user
}

export const updateUser = async (userId, payload) => {
  const response = await api.put(`/admin/users/${userId}`, payload)
  return response.data.user
}

export const deleteUser = async (userId) => {
  const response = await api.delete(`/admin/users/${userId}`)
  return response.data
}

export class SocketService {
  constructor() {
    this.socket = null
    this.listeners = []
    this.isConnected = false
  }

  connect(token = authStore.getToken()) {
    this.disconnect()
    if (!token) return

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${wsProtocol}//${window.location.host}/ws?token=${encodeURIComponent(token)}`
    this.socket = new WebSocket(url)

    this.socket.onopen = () => {
      this.isConnected = true
      this.notifyListeners({ type: 'status', data: 'connected' })
    }

    this.socket.onmessage = (event) => {
      try {
        this.notifyListeners(JSON.parse(event.data))
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    this.socket.onclose = () => {
      this.isConnected = false
      this.notifyListeners({ type: 'status', data: 'disconnected' })
    }

    this.socket.onerror = () => {
      this.isConnected = false
      this.notifyListeners({ type: 'status', data: 'disconnected' })
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
  }

  addListener(callback) {
    if (!this.listeners.includes(callback)) {
      this.listeners.push(callback)
    }
  }

  removeListener(callback) {
    const index = this.listeners.indexOf(callback)
    if (index > -1) {
      this.listeners.splice(index, 1)
    }
  }

  notifyListeners(message) {
    this.listeners.forEach((callback) => callback(message))
  }
}

export const socketService = new SocketService()
