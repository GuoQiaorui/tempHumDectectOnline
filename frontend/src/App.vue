<template>
  <main class="app-shell" @click="closeMenus">
    <section v-if="initializing" class="center-panel">
      <div class="panel">
        <h1>温湿度监测平台</h1>
        <p>正在加载账号信息...</p>
      </div>
    </section>

    <section v-else-if="!currentUser" class="center-panel">
      <form class="login-panel" @submit.prevent="handleLogin">
        <h1>温湿度监测平台</h1>
        <p class="muted">登录后查看已绑定设备的实时数据</p>

        <label>
          账号
          <input v-model.trim="loginForm.username" autocomplete="username" required />
        </label>

        <label>
          密码
          <input v-model="loginForm.password" type="password" autocomplete="current-password" required />
        </label>

        <p v-if="loginError" class="error">{{ loginError }}</p>
        <button type="submit" :disabled="loginLoading">
          {{ loginLoading ? '登录中...' : '登录' }}
        </button>
      </form>
    </section>

    <section v-else class="container">
      <header class="topbar">
        <div>
          <h1>温湿度实时监测</h1>
          <p class="muted">
            {{ currentUser.username }} · {{ currentUser.role === 'admin' ? '管理员' : '普通用户' }}
          </p>
        </div>
        <div class="topbar-actions">
          <div class="select-menu device-menu" @click.stop>
            <button type="button" class="select-trigger" @click="toggleMenu('device')">
              <span>{{ selectedDeviceId || '无设备' }}</span>
              <span class="chevron">⌄</span>
            </button>
            <div v-if="openMenu === 'device'" class="select-options">
              <button
                v-for="device in devices"
                :key="device.device_id"
                type="button"
                class="select-option"
                :class="{ active: selectedDeviceId === device.device_id }"
                @click="chooseDevice(device.device_id)"
              >
                {{ device.device_id }}
              </button>
              <div v-if="devices.length === 0" class="select-empty">暂无设备</div>
            </div>
          </div>

          <button
            v-if="currentUser.role === 'admin'"
            type="button"
            class="secondary"
            @click="activeView = activeView === 'admin' ? 'dashboard' : 'admin'"
          >
            {{ activeView === 'admin' ? '监控面板' : '用户管理' }}
          </button>
          <button type="button" class="secondary" @click="handleLogout">退出</button>
        </div>
      </header>

      <section v-if="activeView === 'dashboard'" class="dashboard">
        <div class="status-row">
          <span class="status-badge" :class="connectionStatus">
            {{ connectionStatus === 'connected' ? '实时连接中' : '连接断开' }}
          </span>
        </div>

        <div class="cards">
          <div class="card temp">
            <span class="label">当前温度</span>
            <span class="value">{{ currentData.temperature }}°C</span>
          </div>
          <div class="card humidity">
            <span class="label">当前湿度</span>
            <span class="value">{{ currentData.humidity }}%</span>
          </div>
          <div class="card device">
            <span class="label">设备 ID</span>
            <span class="value">{{ currentData.device_id || selectedDeviceId || '无设备' }}</span>
          </div>
        </div>

        <div class="charts-grid" v-if="historyData.length > 0">
          <TemperatureChart :initialData="historyData" />
          <HumidityChart :initialData="historyData" />
        </div>
        <div v-else class="empty-panel">
          {{ selectedDeviceId ? '暂无历史数据，等待设备上传。' : '当前账号尚未绑定设备。' }}
        </div>
      </section>

      <section v-else class="admin-panel">
        <div class="admin-header">
          <h2>用户管理</h2>
          <button type="button" @click="refreshAdminData">刷新</button>
        </div>

        <form class="user-form" @submit.prevent="handleCreateUser">
          <input v-model.trim="newUser.username" placeholder="账号" required />
          <input v-model="newUser.password" type="password" placeholder="密码，至少8位字母数字" required />

          <div class="select-menu role-menu" @click.stop>
            <button type="button" class="select-trigger" @click="toggleMenu('newRole')">
              <span>{{ roleLabel(newUser.role) }}</span>
              <span class="chevron">⌄</span>
            </button>
            <div v-if="openMenu === 'newRole'" class="select-options">
              <button type="button" class="select-option" @click="chooseNewRole('user')">普通用户</button>
              <button type="button" class="select-option" @click="chooseNewRole('admin')">管理员</button>
            </div>
          </div>

          <input v-model.trim="newUser.devicesText" placeholder="设备ID，逗号分隔，如 DEV0001" />
          <button type="submit">创建用户</button>
        </form>

        <p v-if="adminMessage" class="message">{{ adminMessage }}</p>

        <div class="user-table">
          <div class="table-row table-head">
            <span>账号</span>
            <span>角色</span>
            <span>状态</span>
            <span>设备</span>
            <span>新密码</span>
            <span>操作</span>
          </div>
          <div v-for="user in users" :key="user.id" class="table-row">
            <span>{{ user.username }}</span>

            <div class="select-menu" @click.stop>
              <button
                type="button"
                class="select-trigger"
                :disabled="user.username === 'admin'"
                @click="toggleMenu(`role-${user.id}`)"
              >
                <span>{{ roleLabel(user.role) }}</span>
                <span class="chevron">⌄</span>
              </button>
              <div v-if="openMenu === `role-${user.id}`" class="select-options">
                <button type="button" class="select-option" @click="chooseUserRole(user, 'user')">普通用户</button>
                <button type="button" class="select-option" @click="chooseUserRole(user, 'admin')">管理员</button>
              </div>
            </div>

            <label class="inline-check">
              <input v-model="user.is_active" type="checkbox" :disabled="user.username === 'admin'" />
              启用
            </label>
            <input v-model="user.devicesText" :disabled="user.role === 'admin'" />
            <input v-model="user.passwordReset" type="password" placeholder="留空不修改" />
            <div class="row-actions">
              <button type="button" @click="handleUpdateUser(user)">保存</button>
              <button
                type="button"
                class="danger"
                :disabled="user.username === 'admin'"
                @click="handleDeleteUser(user)"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  authStore,
  createUser,
  deleteUser,
  getCurrentUser,
  getDevices,
  getHistoryData,
  listUsers,
  login,
  logout,
  socketService,
  updateUser
} from './index.js'
import TemperatureChart from './components/TemperatureChart.vue'
import HumidityChart from './components/HumidityChart.vue'

const initializing = ref(true)
const loginLoading = ref(false)
const loginError = ref('')
const adminMessage = ref('')
const activeView = ref('dashboard')
const connectionStatus = ref('disconnected')
const currentUser = ref(null)
const devices = ref([])
const users = ref([])
const selectedDeviceId = ref('')
const historyData = ref([])
const openMenu = ref('')

const loginForm = reactive({
  username: '',
  password: ''
})

const newUser = reactive({
  username: '',
  password: '',
  role: 'user',
  devicesText: 'DEV0001'
})

const currentData = reactive({
  temperature: '--',
  humidity: '--',
  device_id: '',
  timestamp: ''
})

const parseDevices = (value) => {
  return (value || '')
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
}

const roleLabel = (role) => (role === 'admin' ? '管理员' : '普通用户')

const toggleMenu = (menu) => {
  openMenu.value = openMenu.value === menu ? '' : menu
}

const closeMenus = () => {
  openMenu.value = ''
}

const chooseNewRole = (role) => {
  newUser.role = role
  closeMenus()
}

const chooseUserRole = (user, role) => {
  user.role = role
  closeMenus()
}

const chooseDevice = async (deviceId) => {
  selectedDeviceId.value = deviceId
  closeMenus()
  await loadHistory()
}

const resetDashboard = () => {
  historyData.value = []
  currentData.temperature = '--'
  currentData.humidity = '--'
  currentData.device_id = ''
  currentData.timestamp = ''
}

const handleSocketMessage = (msg) => {
  if (msg.type === 'status') {
    connectionStatus.value = msg.data
    return
  }

  const data = msg.data || msg
  if (data.temperature === undefined || data.device_id !== selectedDeviceId.value) {
    return
  }

  currentData.temperature = data.temperature
  currentData.humidity = data.humidity
  currentData.device_id = data.device_id
  currentData.timestamp = data.timestamp
}

const loadHistory = async () => {
  resetDashboard()
  if (!selectedDeviceId.value) return
  const data = await getHistoryData(selectedDeviceId.value)
  historyData.value = data
  const latest = data[data.length - 1]
  if (latest) {
    currentData.temperature = latest.temperature
    currentData.humidity = latest.humidity
    currentData.device_id = latest.device_id || selectedDeviceId.value
    currentData.timestamp = latest.timestamp
  }
}

const loadDevices = async () => {
  const previousDevice = selectedDeviceId.value
  devices.value = await getDevices()
  const ids = devices.value.map((device) => device.device_id)
  if (previousDevice && ids.includes(previousDevice)) {
    selectedDeviceId.value = previousDevice
  } else {
    selectedDeviceId.value = ids[0] || ''
  }
  await loadHistory()
}

const loadUsers = async () => {
  const data = await listUsers()
  users.value = data.map((user) => ({
    ...user,
    devicesText: (user.devices || []).join(', '),
    passwordReset: ''
  }))
}

const refreshAdminData = async () => {
  await loadUsers()
  await loadDevices()
}

const enterApp = async (user) => {
  currentUser.value = user
  activeView.value = 'dashboard'
  await loadDevices()
  socketService.connect(authStore.getToken())
  if (user.role === 'admin') {
    await loadUsers()
  }
}

const handleLogin = async () => {
  loginError.value = ''
  loginLoading.value = true
  try {
    const data = await login(loginForm.username, loginForm.password)
    loginForm.password = ''
    await enterApp(data.user)
  } catch (error) {
    loginError.value = error.response?.data?.detail || '登录失败'
  } finally {
    loginLoading.value = false
  }
}

const handleLogout = async () => {
  await logout()
  socketService.disconnect()
  currentUser.value = null
  selectedDeviceId.value = ''
  devices.value = []
  users.value = []
  resetDashboard()
}

const handleCreateUser = async () => {
  adminMessage.value = ''
  try {
    await createUser({
      username: newUser.username,
      password: newUser.password,
      role: newUser.role,
      devices: parseDevices(newUser.devicesText)
    })
    newUser.username = ''
    newUser.password = ''
    newUser.role = 'user'
    newUser.devicesText = 'DEV0001'
    adminMessage.value = '用户已创建'
    await refreshAdminData()
  } catch (error) {
    adminMessage.value = error.response?.data?.detail || '创建失败'
  }
}

const handleUpdateUser = async (user) => {
  adminMessage.value = ''
  try {
    await updateUser(user.id, {
      role: user.role,
      is_active: user.is_active,
      devices: user.role === 'admin' ? [] : parseDevices(user.devicesText),
      password: user.passwordReset || undefined
    })
    adminMessage.value = '用户已更新'
    await refreshAdminData()
  } catch (error) {
    adminMessage.value = error.response?.data?.detail || '更新失败'
  }
}

const handleDeleteUser = async (user) => {
  adminMessage.value = ''
  try {
    await deleteUser(user.id)
    adminMessage.value = '用户已删除'
    await refreshAdminData()
  } catch (error) {
    adminMessage.value = error.response?.data?.detail || '删除失败'
  }
}

const handleAuthExpired = () => {
  socketService.disconnect()
  currentUser.value = null
  loginError.value = '登录状态已失效，请重新登录'
}

onMounted(async () => {
  window.addEventListener('auth-expired', handleAuthExpired)
  socketService.addListener(handleSocketMessage)
  try {
    if (authStore.getToken()) {
      const user = await getCurrentUser()
      await enterApp(user)
    }
  } catch {
    authStore.clearToken()
  } finally {
    initializing.value = false
  }
})

onUnmounted(() => {
  window.removeEventListener('auth-expired', handleAuthExpired)
  socketService.removeListener(handleSocketMessage)
  socketService.disconnect()
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  background: #f4f7fb;
  color: #1f2937;
}

.center-panel {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.panel,
.login-panel,
.empty-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.login-panel {
  width: min(420px, 100%);
  padding: 32px;
  display: grid;
  gap: 16px;
}

.panel {
  padding: 32px;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 24px;
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

h1,
h2 {
  margin: 0;
}

.muted {
  color: #64748b;
  margin: 6px 0 0;
}

label {
  display: grid;
  gap: 6px;
  font-size: 14px;
  color: #334155;
}

input,
button {
  min-height: 40px;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  padding: 8px 10px;
  font: inherit;
}

button {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
  cursor: pointer;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button.secondary {
  background: #fff;
  color: #1f2937;
  border-color: #cbd5e1;
}

button.danger {
  background: #dc2626;
  border-color: #dc2626;
}

.select-menu {
  position: relative;
  min-width: 158px;
}

.device-menu {
  min-width: 168px;
}

.role-menu {
  min-width: 156px;
}

.select-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: #fff;
  color: #1f2937;
  border-color: #cbd5e1;
  text-align: left;
}

.select-trigger:focus-visible {
  outline: 2px solid #0ea5e9;
  outline-offset: 2px;
}

.chevron {
  color: #475569;
  font-size: 18px;
  line-height: 1;
}

.select-options {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 30;
  width: 100%;
  overflow: hidden;
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.14);
}

.select-option {
  width: 100%;
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 8px 10px;
  background: #fff;
  color: #1f2937;
  border: 0;
  border-radius: 0;
}

.select-option:hover,
.select-option.active {
  background: #eff6ff;
  color: #1d4ed8;
}

.select-empty {
  padding: 10px;
  color: #64748b;
}

.error,
.message {
  margin: 0;
  color: #b91c1c;
}

.status-row {
  margin-bottom: 16px;
}

.status-badge {
  display: inline-flex;
  padding: 8px 12px;
  border-radius: 999px;
  font-weight: 700;
  font-size: 14px;
}

.status-badge.connected {
  background: #dcfce7;
  color: #166534;
}

.status-badge.disconnected {
  background: #fee2e2;
  color: #991b1b;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.card {
  background: #fff;
  padding: 24px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  text-align: center;
}

.label {
  display: block;
  color: #64748b;
  margin-bottom: 10px;
}

.value {
  display: block;
  font-size: 28px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.temp .value {
  color: #dc2626;
}

.humidity .value {
  color: #2563eb;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.empty-panel {
  padding: 48px;
  text-align: center;
  color: #64748b;
}

.admin-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 20px;
}

.admin-header,
.user-form,
.row-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.admin-header {
  justify-content: space-between;
  margin-bottom: 16px;
}

.user-form {
  margin-bottom: 16px;
}

.user-form input {
  min-width: 220px;
}

.user-table {
  display: grid;
  gap: 8px;
}

.table-row {
  display: grid;
  grid-template-columns: 1.1fr 1fr 0.8fr 1.4fr 1.2fr 1.1fr;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.table-head {
  font-weight: 800;
  background: #f8fafc;
}

.inline-check {
  display: inline-flex;
  grid-template-columns: none;
  align-items: center;
  gap: 8px;
}

@media (max-width: 820px) {
  .topbar,
  .table-row {
    grid-template-columns: 1fr;
    display: grid;
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
