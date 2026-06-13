<template>
  <div class="chart-card">
    <h3>🌡️ 实时温度趋势</h3>
    <Line :key="chartKey" :data="chartData" :options="chartOptions" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js'
import { socketService } from '../index.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const props = defineProps({
  initialData: { type: Array, default: () => [] }
})

// 使用 key 来强制重新渲染图表
const chartKey = ref(0)

const chartData = ref({
  labels: [],
  datasets: [{
    label: '温度 (°C)',
    backgroundColor: 'rgba(255, 99, 132, 0.2)',
    borderColor: 'rgb(255, 99, 132)',
    data: [],
    tension: 0.4,
    fill: true
  }]
})

// 最大显示数据量
const MAX_DATA_POINTS = 50

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 0 }, // 禁用动画以提高实时性能
  scales: {
    y: { beginAtZero: false }
  }
}

// ✅ 实时更新图表（每收到一条新数据立即更新）
const updateChart = (data) => {
  console.log('🔄 温度图表准备更新数据...')
  
  const time = data.timestamp.split('T')[1] || data.timestamp
  const timeLabel = time.substring(0, 8) // 取 HH:mm:ss
  const temperature = data.temperature

  console.log('  - 时间标签:', timeLabel)
  console.log('  - 温度值:', temperature)

  // 创建新的数组副本
  let newLabels = [...chartData.value.labels]
  let newValues = [...chartData.value.datasets[0].data]

  // 检查是否已存在该时间点的数据
  const existingIndex = newLabels.indexOf(timeLabel)
  console.log('  - 在图表中查找时间标签:', existingIndex)

  if (existingIndex !== -1) {
    // 更新已存在的点
    newValues = newValues.map((val, idx) => 
      idx === existingIndex ? temperature : val
    )
    console.log('🔄 更新已存在的数据点:', timeLabel, '=', temperature, '°C')
  } else {
    // 添加新数据点到末尾
    newLabels.push(timeLabel)
    newValues.push(temperature)
    console.log('➕ 添加新数据点:', timeLabel, '=', temperature, '°C')
  }

  // 🎯 保持最多显示 50 个点，超出则移除最旧的数据
  if (newLabels.length > MAX_DATA_POINTS) {
    newLabels.shift() // 删除第一个（最旧的）
    newValues.shift()
    console.log('🗑️ 已移除最旧数据，保持最新 50 条')
  }

  // ✅ 替换整个数组触发响应式更新
  chartData.value.labels = newLabels
  chartData.value.datasets[0].data = newValues
  
  // 强制更新 key 来重新渲染图表
  chartKey.value++

  console.log(`✅ 温度图表更新完成，当前数据点数量:${chartData.value.labels.length}`)
  console.log('📊 最新 5 个数据点:', {
    labels: chartData.value.labels.slice(-5),
    values: chartData.value.datasets[0].data.slice(-5)
  })
}

// ✅ 初始化数据（从 props 加载历史数据，只显示最新 50 条）
const initFromProps = () => {
  if (!props.initialData || props.initialData.length === 0) {
    console.log('📊 温度图表：没有历史数据')
    return
  }
  
  // 只取最新 50 条数据
  const recentData = props.initialData.slice(-MAX_DATA_POINTS)
  
  // ✅ 包含时分秒，让每个数据点都有不同的时间标签
  const labels = recentData.map(d => {
    const time = d.timestamp.split('T')[1] || d.timestamp
    return time.substring(0, 8) // 取 HH:mm:ss
  })
  const values = recentData.map(d => d.temperature)

  chartData.value.labels = labels
  chartData.value.datasets[0].data = values
  console.log(`📊 温度图表初始化完成，显示最新${labels.length}条数据`)
  console.log('📊 温度图表 labels:', labels)
  console.log('📊 温度图表 values:', values)
}



// ✅ 处理新数据（立即更新图表）
const handleNewData = (msg) => {
  console.log('📈 温度图表收到 WebSocket 消息:', msg)
  
  // ✅ 后端发送的格式：{type: 'data', data: {...}}
  // 需要提取 msg.data 中的温湿度数据
  const data = msg.data || msg
  
  console.log('🔍 提取的数据对象:', data)
  console.log('🔍 温度值:', data.temperature)
  console.log('🔍 时间戳:', data.timestamp)
  
  if (data.temperature !== undefined && data.timestamp) {
    updateChart(data)
  } else {
    console.log('⚠️ 温度数据格式不正确，跳过:', data)
  }
}

// ✅ 监听历史数据变化
watch(() => props.initialData, (newData) => {
  console.log('👁️ 温度图表监听到历史数据变化，数据条数:', newData?.length)
  if (newData && newData.length > 0) {
    initFromProps()
  }
}, { immediate: true })

onMounted(() => {
  socketService.addListener(handleNewData)
})

onUnmounted(() => {
  socketService.removeListener(handleNewData)
})
</script>

<style scoped>
.chart-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.05);
  height: 300px;
}
h3 { margin-top: 0; color: #333; }
</style>