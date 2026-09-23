<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { getSummary, getFaceCoverage, getFaceCount } from '../../api/stats'

// 数据统计看板页。
//
// 5 个图表（对应规划文档第 11 节）：
//   1. 总人数 —— 数字卡片
//   2. 覆盖率 —— 环形进度图（核心指标，放最显眼位置）
//   3. 性别分布 —— 饼图
//   4. 班级分布 —— 柱状图
//   5. 专业分布 —— 柱状图
//   6. 脸照数量分布 —— 柱状图
//
// 注意：三个接口并发请求（Promise.all），图表用 echarts 渲染。
// 空库时各分布为空列表，图表要能正常显示空态，不报错。

const loading = ref(false)

// 各图表的 DOM 容器 ref
const coverageRef = ref(null)
const genderRef = ref(null)
const classRef = ref(null)
const majorRef = ref(null)
const faceCountRef = ref(null)

const totalStudents = ref(0)

// 保存图表实例，销毁时释放
let charts = []

function makeChart(el) {
  const c = echarts.init(el)
  charts.push(c)
  return c
}

function disposeCharts() {
  charts.forEach((c) => c.dispose())
  charts = []
}

// 渲染覆盖率环形图
function renderCoverage(data) {
  if (!coverageRef.value) return
  const c = makeChart(coverageRef.value)
  const pct = Math.round(data.coverage_rate * 100)
  c.setOption({
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: ['62%', '85%'],
        avoidLabelOverlap: false,
        label: {
          show: true,
          position: 'center',
          formatter: () => `${pct}%\n覆盖率`,
          fontSize: 20,
          color: '#303133',
        },
        data: [
          { value: data.enrolled, name: '已录入', itemStyle: { color: '#409eff' } },
          { value: data.not_enrolled, name: '未录入', itemStyle: { color: '#e6e8eb' } },
        ],
      },
    ],
  })
}

// 渲染性别饼图
function renderGender(items) {
  if (!genderRef.value) return
  const c = makeChart(genderRef.value)
  c.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 人 ({d}%)' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: '60%',
        data: items.map((it) => ({ name: it.name, value: it.count })),
        label: { formatter: '{b}: {c}' },
      },
    ],
  })
}

// 渲染柱状图（班级/专业/脸照数分布通用）
function renderBar(el, items, color) {
  if (!el) return
  const c = makeChart(el)
  c.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 8, right: 8, top: 20, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: items.map((it) => it.name),
      axisLabel: { interval: 0, rotate: items.length > 4 ? 30 : 0, fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: items.map((it) => it.count),
        itemStyle: { color },
        barMaxWidth: 40,
      },
    ],
  })
}

async function loadData() {
  loading.value = true
  try {
    const [summary, coverage, faceCount] = await Promise.all([
      getSummary(),
      getFaceCoverage(),
      getFaceCount(),
    ])

    totalStudents.value = summary.total_students

    renderCoverage(coverage)
    renderGender(summary.by_gender)
    renderBar(classRef.value, summary.by_class, '#67c23a')
    renderBar(majorRef.value, summary.by_major, '#e6a23c')
    renderBar(
      faceCountRef.value,
      [
        { name: '0 张', count: faceCount.zero_face },
        { name: '1 张', count: faceCount.one_face },
        { name: '多张', count: faceCount.multiple_faces },
      ],
      '#f56c6c',
    )
  } catch (e) {
    ElMessage.error(e.message || '加载统计数据失败')
  } finally {
    loading.value = false
  }
}

// 窗口尺寸变化时重绘图表
function onResize() {
  charts.forEach((c) => c.resize())
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeCharts()
})
</script>

<template>
  <div class="stats-page" v-loading="loading">
    <!-- 总人数卡片 -->
    <div class="total-card">
      <div class="total-label">学生总数</div>
      <div class="total-number">{{ totalStudents }}</div>
    </div>

    <!-- 覆盖率（核心指标，放最显眼位置） -->
    <div class="chart-card chart-card--wide">
      <div class="chart-title">脸照覆盖率</div>
      <div ref="coverageRef" class="chart chart--coverage"></div>
    </div>

    <!-- 性别分布 -->
    <div class="chart-card">
      <div class="chart-title">性别分布</div>
      <div ref="genderRef" class="chart"></div>
    </div>

    <!-- 班级分布 -->
    <div class="chart-card chart-card--wide">
      <div class="chart-title">班级分布</div>
      <div ref="classRef" class="chart"></div>
    </div>

    <!-- 专业分布 -->
    <div class="chart-card chart-card--wide">
      <div class="chart-title">专业分布</div>
      <div ref="majorRef" class="chart"></div>
    </div>

    <!-- 脸照数量分布 -->
    <div class="chart-card">
      <div class="chart-title">脸照数量分布</div>
      <div ref="faceCountRef" class="chart"></div>
    </div>
  </div>
</template>

<style scoped>
.stats-page {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
.total-card {
  grid-column: 1 / -1;
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  border-radius: 8px;
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.total-label {
  font-size: 15px;
  opacity: 0.9;
}
.total-number {
  font-size: 36px;
  font-weight: 700;
}
.chart-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  min-width: 0;
}
.chart-card--wide {
  grid-column: 1 / -1;
}
.chart-title {
  font-size: 15px;
  color: #303133;
  margin-bottom: 12px;
  font-weight: 600;
}
.chart {
  width: 100%;
  height: 280px;
}
.chart--coverage {
  height: 320px;
}
</style>
