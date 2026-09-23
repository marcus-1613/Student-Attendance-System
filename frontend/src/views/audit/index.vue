<script setup>
// 脸库审计页面：展示人脸嵌入聚类审计结果。
//
// 对应后端 GET /api/audit/duplicates 返回的三类嫌疑清单：
//   1. duplicates  ：疑似重复登记（两个不同学号人脸相似度 > 0.85，疑似一人多号）
//   2. dirty_faces ：疑似脏录入（同一学生两张脸相似度 < 0.6，疑似录错人）
//   3. clusters    ：可疑团伙（两两高相似的人脸聚成的簇）
//
// 注意：审计是无监督方法，输出是「嫌疑清单」不是「判决书」，需要人工复核。
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getAuditDuplicates } from '../../api/audit'

const loading = ref(false)
const auditing = ref(false)

// 审计结果
const result = ref({
  total_faces: 0,
  total_students: 0,
  duplicates: [],
  dirty_faces: [],
  clusters: [],
})

// 是否已执行过审计（首次进入页面不自动跑，等用户点「开始审计」）
const hasAudited = ref(false)

async function runAudit() {
  auditing.value = true
  try {
    const data = await getAuditDuplicates()
    result.value = data
    hasAudited.value = true
    const suspectCount = data.duplicates.length + data.dirty_faces.length + data.clusters.length
    if (suspectCount === 0) {
      ElMessage.success('审计完成，未发现异常')
    } else {
      ElMessage.warning(`审计完成，发现 ${suspectCount} 处可疑项，请人工复核`)
    }
  } catch (e) {
    ElMessage.error(e.message || '审计失败')
  } finally {
    auditing.value = false
  }
}

// 相似度格式化（百分比）
function fmtSimilarity(sim) {
  return (sim * 100).toFixed(1) + '%'
}

onMounted(() => {
  // 进入页面自动执行一次审计（脸库数据量小，秒级完成）
  runAudit()
})
</script>

<template>
  <div class="audit-page">
    <div class="page-header">
      <h2>脸库审计</h2>
      <el-button type="primary" :icon="Refresh" :loading="auditing" @click="runAudit">
        重新审计
      </el-button>
    </div>

    <!-- 审计概览 -->
    <el-row :gutter="16" class="overview">
      <el-col :span="8">
        <el-card shadow="never">
          <div class="stat-card">
            <div class="stat-value">{{ result.total_faces }}</div>
            <div class="stat-label">参与审计的人脸</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div class="stat-card">
            <div class="stat-value">{{ result.total_students }}</div>
            <div class="stat-label">涉及的学生</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never">
          <div class="stat-card">
            <div class="stat-value warn">
              {{ result.duplicates.length + result.dirty_faces.length + result.clusters.length }}
            </div>
            <div class="stat-label">可疑项总数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 提示 -->
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="审计结果为无监督聚类的「嫌疑清单」，不是最终结论，请人工复核确认。"
      class="audit-tip"
    />

    <!-- 1. 疑似重复登记 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">疑似重复登记（不同学号人脸高度相似）</span>
      </template>
      <el-table
        v-if="result.duplicates.length"
        :data="result.duplicates"
        border
        stripe
      >
        <el-table-column label="学生 A" min-width="180">
          <template #default="{ row }">
            {{ row.student_a.name }}（{{ row.student_a.student_no }}）
          </template>
        </el-table-column>
        <el-table-column label="学生 B" min-width="180">
          <template #default="{ row }">
            {{ row.student_b.name }}（{{ row.student_b.student_no }}）
          </template>
        </el-table-column>
        <el-table-column label="相似度" width="200" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.similarity * 100)"
              :color="row.similarity > 0.9 ? '#f56c6c' : '#e6a23c'"
            />
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="未发现疑似重复登记" :image-size="60" />
    </el-card>

    <!-- 2. 疑似脏录入 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">疑似脏录入（同一学生两张脸差异极大）</span>
      </template>
      <el-table
        v-if="result.dirty_faces.length"
        :data="result.dirty_faces"
        border
        stripe
      >
        <el-table-column label="学生" min-width="160">
          <template #default="{ row }">
            {{ row.student.name }}（{{ row.student.student_no }}）
          </template>
        </el-table-column>
        <el-table-column prop="face_a_id" label="脸照 A (face_id)" width="150" align="center" />
        <el-table-column prop="face_b_id" label="脸照 B (face_id)" width="150" align="center" />
        <el-table-column label="相似度" width="200" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.similarity * 100)"
              :color="'#f56c6c'"
              :format="() => fmtSimilarity(row.similarity)"
            />
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="未发现疑似脏录入" :image-size="60" />
    </el-card>

    <!-- 3. 可疑团伙（聚类） -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <span class="section-title">可疑团伙（两两高相似聚成的簇）</span>
      </template>
      <div v-if="result.clusters.length" class="clusters">
        <div v-for="(cluster, idx) in result.clusters" :key="idx" class="cluster-item">
          <div class="cluster-tag">团伙 {{ idx + 1 }}</div>
          <div class="cluster-members">
            <el-tag
              v-for="face in cluster.faces"
              :key="face.face_id"
              type="danger"
              effect="plain"
              class="cluster-tag-item"
            >
              {{ face.student_name }}（{{ face.student_no }}）
            </el-tag>
          </div>
        </div>
      </div>
      <el-empty v-else description="未发现可疑团伙" :image-size="60" />
    </el-card>
  </div>
</template>

<style scoped>
.audit-page {
  padding: 20px;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}
.overview {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
  padding: 8px 0;
}
.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
}
.stat-value.warn {
  color: #f56c6c;
}
.stat-label {
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}
.audit-tip {
  margin-bottom: 16px;
}
.section-card {
  margin-bottom: 16px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.clusters {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cluster-item {
  padding: 12px;
  background: #fef0f0;
  border-radius: 6px;
}
.cluster-tag {
  font-size: 13px;
  font-weight: 600;
  color: #f56c6c;
  margin-bottom: 8px;
}
.cluster-members {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cluster-tag-item {
  cursor: default;
}
</style>
