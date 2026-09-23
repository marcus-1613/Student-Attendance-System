<script setup>
import { ref } from 'vue'
import RealtimeCamera from '../../components/RealtimeCamera.vue'

// 实时人脸识别页（第二阶段 P12-P14）。
//
// 能力：摄像头 → 后端识别（InsightFace 提取 embedding → Milvus 检索身份）→
//      画框 + 显示姓名 → 自动写考勤 → 多人同框代刷预警。

const latest = ref(null) // 最近一次识别结果（RecognizeOut）

function onRecognized(data) {
  latest.value = data
}
</script>

<template>
  <div class="recognition-page">
    <div class="page-header">
      <h2 class="page-title">实时人脸识别</h2>
      <p class="page-subtitle">
        开启摄像头后自动识别身份并打卡；命中学生显示绿色框，陌生人显示黄色框。
      </p>
    </div>

    <div class="layout">
      <el-card shadow="never" class="camera-card">
        <RealtimeCamera @recognized="onRecognized" />
      </el-card>

      <el-card shadow="never" class="result-card">
        <template #header>
          <span>最新识别结果</span>
        </template>
        <div v-if="!latest || latest.face_count === 0" class="empty">
          <p>暂无识别结果</p>
          <p class="sub">将脸对准摄像头，识别到人脸后这里会显示身份信息</p>
        </div>
        <div v-else>
          <el-table :data="latest.faces" size="small" border>
            <el-table-column prop="name" label="姓名" width="90">
              <template #default="{ row }">
                {{ row.matched ? row.name : '未识别' }}
              </template>
            </el-table-column>
            <el-table-column prop="student_no" label="学号" width="120">
              <template #default="{ row }">
                {{ row.matched ? row.student_no : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="相似度" width="90">
              <template #default="{ row }">
                <span v-if="row.matched">{{ (row.similarity * 100).toFixed(1) }}%</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.matched" type="success" size="small">已打卡</el-tag>
                <el-tag v-else type="warning" size="small">陌生人</el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-alert
            v-if="latest.warning && latest.warning.triggered"
            class="warning-alert"
            type="error"
            :closable="false"
            show-icon
            :title="latest.warning.reason"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.recognition-page {
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
.layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
.empty {
  text-align: center;
  color: #909399;
  padding: 24px 0;
}
.empty p {
  margin: 0 0 6px;
}
.empty .sub {
  font-size: 12px;
  color: #c0c4cc;
}
.warning-alert {
  margin-top: 12px;
}
</style>
