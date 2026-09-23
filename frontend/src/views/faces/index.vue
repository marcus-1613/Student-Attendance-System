<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import CameraCapture from '../../components/CameraCapture.vue'
import { listStudents } from '../../api/students'
import { uploadFace, listFaces, deleteFace } from '../../api/faces'

// 人脸录入页。
//
// 流程（对应规划文档第 10 节）：
//   1. 远程搜索选择学生
//   2. 打开摄像头 → 拍照（CameraCapture 返回 Blob）
//   3. 上传 Blob → 后端检测 + 三存储落库
//   4. 成功刷新该学生的脸照缩略图列表；失败提示重拍
//
// 图片访问：后端 image_path 是 /<student_id>/<filename>，
// 静态挂载在 /face-images 前缀，前端拼 /face-images + image_path 访问（走 vite 代理）。

// ---------- 选择学生 ----------
const selectedStudentId = ref(null)
const studentOptions = ref([])
const studentLoading = ref(false)

// 远程搜索学生（按姓名/学号）
async function searchStudents(keyword) {
  studentLoading.value = true
  try {
    const data = await listStudents({
      keyword: keyword || undefined,
      page: 1,
      page_size: 20,
    })
    studentOptions.value = data.items.map((s) => ({
      id: s.id,
      label: `${s.name}（${s.student_no}）`,
      student_no: s.student_no,
    }))
  } catch (e) {
    ElMessage.error(e.message || '搜索学生失败')
    studentOptions.value = []
  } finally {
    studentLoading.value = false
  }
}

// 初始加载时先拉一批学生，方便直接选
onMounted(() => {
  searchStudents('')
})

// ---------- 拍照上传 ----------
const cameraRef = ref(null)
const uploading = ref(false)

// 拍照后收到 Blob，转为 File 再上传
async function handleCaptured(blob) {
  if (!selectedStudentId.value) {
    ElMessage.warning('请先选择学生')
    return
  }
  const file = new File([blob], `face_${Date.now()}.jpg`, { type: 'image/jpeg' })
  uploading.value = true
  try {
    const res = await uploadFace(selectedStudentId.value, file)
    // total_faces > 1 说明图里有多张脸，只取了最大那张，提示用户
    if (res.total_faces > 1) {
      ElMessage.success(`录入成功（检测到 ${res.total_faces} 张脸，已保存最大的一张）`)
    } else {
      ElMessage.success('录入成功')
    }
    await loadFaces()
  } catch (e) {
    // 无人脸/图片无效等业务错误：停在当前页让用户重拍
    ElMessage.warning(e.message || '录入失败，请重拍')
  } finally {
    uploading.value = false
  }
}

// ---------- 脸照列表 ----------
const faces = ref([])
const facesLoading = ref(false)

async function loadFaces() {
  if (!selectedStudentId.value) {
    faces.value = []
    return
  }
  facesLoading.value = true
  try {
    faces.value = await listFaces(selectedStudentId.value)
  } catch (e) {
    ElMessage.error(e.message || '加载脸照失败')
    faces.value = []
  } finally {
    facesLoading.value = false
  }
}

// 图片完整 URL：/face-images 前缀 + 后端 image_path（如 /1/1_xxx.jpg）
function faceUrl(face) {
  return `/face-images${face.image_path}`
}

// 选择学生变化时刷新其脸照列表
function handleStudentChange() {
  loadFaces()
}

// 删除单张脸照
async function handleDeleteFace(face) {
  try {
    await ElMessageBox.confirm('确定删除这张脸照吗？', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteFace(face.face_id)
    ElMessage.success('删除成功')
    await loadFaces()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}
</script>

<template>
  <div class="faces-page">
    <!-- 选择学生 -->
    <div class="student-picker">
      <span class="picker-label">选择学生：</span>
      <el-select
        v-model="selectedStudentId"
        filterable
        remote
        reserve-keyword
        clearable
        :remote-method="searchStudents"
        :loading="studentLoading"
        placeholder="输入姓名或学号搜索"
        style="width: 280px"
        @change="handleStudentChange"
      >
        <el-option
          v-for="s in studentOptions"
          :key="s.id"
          :label="s.label"
          :value="s.id"
        />
      </el-select>
    </div>

    <!-- 摄像头采集 -->
    <CameraCapture ref="cameraRef" @captured="handleCaptured" />

    <!-- 上传中遮罩提示 -->
    <div v-if="uploading" class="uploading-tip">
      正在检测人脸并录入…
    </div>

    <!-- 脸照缩略图列表 -->
    <div class="face-list">
      <h3 class="face-list-title">已录入脸照</h3>
      <el-empty
        v-if="!selectedStudentId"
        description="请先选择学生"
        :image-size="80"
      />
      <el-empty
        v-else-if="!facesLoading && faces.length === 0"
        description="该学生还没有脸照"
        :image-size="80"
      />
      <div v-else v-loading="facesLoading" class="face-grid">
        <div v-for="face in faces" :key="face.id" class="face-card">
          <el-image
            :src="faceUrl(face)"
            fit="cover"
            class="face-thumb"
            :preview-src-list="faces.map(faceUrl)"
            :initial-index="faces.indexOf(face)"
          >
            <template #error>
              <div class="face-thumb-error">图片加载失败</div>
            </template>
          </el-image>
          <div class="face-card-footer">
            <span class="face-id">face_id: {{ face.face_id }}</span>
            <el-button
              link
              type="danger"
              size="small"
              :icon="Delete"
              @click="handleDeleteFace(face)"
            >
              删除
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.faces-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.student-picker {
  display: flex;
  align-items: center;
}
.picker-label {
  font-size: 14px;
  color: #303133;
}
.uploading-tip {
  color: #409eff;
  font-size: 13px;
  text-align: center;
}
.face-list-title {
  margin: 0 0 12px;
  font-size: 16px;
  color: #303133;
}
.face-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}
.face-card {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  overflow: hidden;
  background-color: #fff;
}
.face-thumb {
  width: 100%;
  height: 160px;
  display: block;
}
.face-thumb-error {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 12px;
}
.face-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
}
.face-id {
  font-size: 12px;
  color: #909399;
}
</style>
