<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { listAttendances } from '../../api/attendance'

// 考勤记录查询页（第二阶段 P13）。

const loading = ref(false)
const tableData = ref([])
const total = ref(0)

const query = reactive({
  student_id: null,
  page: 1,
  page_size: 20,
})

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

async function loadData() {
  loading.value = true
  try {
    const data = await listAttendances({
      student_id: query.student_id || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    tableData.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onPageChange(p) {
  query.page = p
  loadData()
}

function onSizeChange(s) {
  query.page_size = s
  query.page = 1
  loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="attendance-page">
    <div class="page-header">
      <h2 class="page-title">考勤记录</h2>
      <p class="page-subtitle">实时识别打卡产生的考勤记录，按打卡时间倒序排列。</p>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="query.student_id"
          placeholder="按学生 ID 过滤（留空查全部）"
          clearable
          style="width: 220px"
          @keyup.enter="query.page = 1; loadData()"
          @clear="query.page = 1; loadData()"
        />
        <el-button :icon="Refresh" @click="loadData">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="student_no" label="学号" width="140" />
        <el-table-column prop="face_id" label="脸照ID" width="90" />
        <el-table-column label="相似度" width="100">
          <template #default="{ row }">
            {{ (row.similarity * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column label="打卡时间">
          <template #default="{ row }">{{ formatTime(row.check_time) }}</template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :current-page="query.page"
          :page-size="query.page_size"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="onPageChange"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.attendance-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.page-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  color: #303133;
}
.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: #909399;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
