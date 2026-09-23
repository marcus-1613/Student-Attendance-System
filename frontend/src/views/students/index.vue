<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import {
  listStudents,
  createStudent,
  updateStudent,
  deleteStudent,
  importStudents,
} from '../../api/students'
import { getEnums } from '../../api/enums'

// ---------- 状态 ----------
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

// 查询条件（keyword 模糊匹配姓名/学号/班级）+ 分页
const query = reactive({
  keyword: '',
  page: 1,
  page_size: 20,
})

// 枚举下拉
const classes = ref([])
const majors = ref([])

// ---------- 新增/编辑对话框 ----------
const dialogVisible = ref(false)
const dialogMode = ref('create') // 'create' | 'edit'
const submitting = ref(false)
const formRef = ref(null)

const emptyForm = () => ({
  id: null,
  student_no: '',
  name: '',
  gender: null,
  class_name: null,
  major: null,
  enroll_year: null,
  phone: '',
})
const form = reactive(emptyForm())

const formRules = {
  student_no: [{ required: true, message: '请输入学号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
}

// ---------- 数据加载 ----------
async function loadData() {
  loading.value = true
  try {
    const data = await listStudents({
      keyword: query.keyword || undefined,
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

async function loadEnums() {
  try {
    const data = await getEnums()
    classes.value = data.classes
    majors.value = data.majors
  } catch (e) {
    ElMessage.error(e.message || '加载枚举失败')
  }
}

// ---------- 搜索 / 分页 ----------
function handleSearch() {
  query.page = 1
  loadData()
}

function handlePageChange(page) {
  query.page = page
  loadData()
}

function handleSizeChange(size) {
  query.page_size = size
  query.page = 1
  loadData()
}

// ---------- 新增 / 编辑 ----------
function openCreate() {
  dialogMode.value = 'create'
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  Object.assign(form, {
    id: row.id,
    student_no: row.student_no,
    name: row.name,
    gender: row.gender,
    class_name: row.class_name,
    major: row.major,
    enroll_year: row.enroll_year,
    phone: row.phone,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()

  // 编辑模式不传 student_no（学号禁止修改）；空字符串字段转 null 方便后端
  const payload = {
    name: form.name,
    gender: form.gender || null,
    class_name: form.class_name || null,
    major: form.major || null,
    enroll_year: form.enroll_year || null,
    phone: form.phone || null,
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      payload.student_no = form.student_no
      await createStudent(payload)
      ElMessage.success('新增成功')
    } else {
      await updateStudent(form.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

// ---------- 删除 ----------
async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除学生「${row.name}（${row.student_no}）」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return // 用户取消
  }
  try {
    await deleteStudent(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

// ---------- 批量导入 ----------
const importVisible = ref(false)
const importing = ref(false)
const importFile = ref(null)
const fileList = ref([])

// 导入文件需要的列（与后端 IMPORT_COLUMNS 约定一致，仅作提示展示）
const importCols = ['学号', '姓名', '性别', '班级', '专业', '入学年份', '联系方式']

// 导入结果弹窗
const resultVisible = ref(false)
const importResult = reactive({
  total: 0,
  success: 0,
  failed: 0,
  errors: [],
})

function openImport() {
  importFile.value = null
  importVisible.value = true
}

// 文件选择变化时，只保存文件对象（真正的上传由「开始导入」按钮触发）
function handleFileChange(file) {
  importFile.value = file
}

// 校验文件类型：后端只支持 .csv / .xlsx
function beforeUpload(file) {
  const ok = /\.(csv|xlsx)$/i.test(file.name)
  if (!ok) {
    ElMessage.error('仅支持 .csv 或 .xlsx 文件')
  }
  return ok
}

async function handleImport() {
  if (!importFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  importing.value = true
  try {
    const res = await importStudents(importFile.value)
    // 组装结果弹窗数据
    importResult.total = res.total
    importResult.success = res.success
    importResult.failed = res.failed
    importResult.errors = res.errors || []

    importVisible.value = false
    resultVisible.value = true
    // 无论成败都刷新列表，让成功导入的行立即可见
    loadData()
  } catch (e) {
    ElMessage.error(e.message || '导入失败')
  } finally {
    importing.value = false
  }
}

function closeResult() {
  resultVisible.value = false
}

onMounted(() => {
  loadData()
  loadEnums()
})
</script>

<template>
  <div class="students-page">
    <!-- 搜索栏 -->
    <div class="toolbar">
      <el-input
        v-model="query.keyword"
        placeholder="搜索姓名 / 学号 / 班级"
        clearable
        style="width: 260px"
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      />
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button type="success" @click="openCreate">新增学生</el-button>
      <el-button type="warning" plain @click="openImport">批量导入</el-button>
    </div>

    <!-- 表格 -->
    <el-table
      v-loading="loading"
      :data="tableData"
      border
      stripe
      style="width: 100%"
    >
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="gender" label="性别" width="70">
        <template #default="{ row }">{{ row.gender || '—' }}</template>
      </el-table-column>
      <el-table-column prop="class_name" label="班级" min-width="150">
        <template #default="{ row }">{{ row.class_name || '—' }}</template>
      </el-table-column>
      <el-table-column prop="major" label="专业" min-width="150">
        <template #default="{ row }">{{ row.major || '—' }}</template>
      </el-table-column>
      <el-table-column prop="enroll_year" label="入学年份" width="90">
        <template #default="{ row }">{{ row.enroll_year || '—' }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="联系方式" min-width="130">
        <template #default="{ row }">{{ row.phone || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        :current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增学生' : '编辑学生'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="80px">
        <el-form-item label="学号" prop="student_no">
          <el-input
            v-model="form.student_no"
            :disabled="dialogMode === 'edit'"
            placeholder="请输入学号"
          />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.gender" placeholder="请选择" clearable>
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
          </el-select>
        </el-form-item>
        <el-form-item label="班级">
          <el-select v-model="form.class_name" placeholder="请选择" clearable filterable>
            <el-option v-for="c in classes" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="专业">
          <el-select v-model="form.major" placeholder="请选择" clearable filterable>
            <el-option v-for="m in majors" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="入学年份">
          <el-input-number
            v-model="form.enroll_year"
            :min="1900"
            :max="2100"
            :controls="false"
            placeholder="请输入年份"
          />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="form.phone" placeholder="请输入联系方式" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog
      v-model="importVisible"
      title="批量导入学生"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="import-tips">
        请上传 .csv 或 .xlsx 文件，表头需包含以下列：
      </div>
      <div class="import-cols">
        <el-tag v-for="c in importCols" :key="c" size="small" class="col-tag">
          {{ c }}
        </el-tag>
      </div>

      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".csv,.xlsx"
        :on-change="handleFileChange"
        :before-upload="beforeUpload"
        :file-list="fileList"
        style="margin-top: 16px"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或<em>点击选择文件</em>
        </div>
      </el-upload>

      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入结果对话框 -->
    <el-dialog
      v-model="resultVisible"
      title="导入结果"
      width="560px"
      :close-on-click-modal="false"
    >
      <div class="result-summary">
        <el-tag type="info" size="large">总数 {{ importResult.total }}</el-tag>
        <el-tag type="success" size="large">成功 {{ importResult.success }}</el-tag>
        <el-tag type="danger" size="large">失败 {{ importResult.failed }}</el-tag>
      </div>

      <el-table
        v-if="importResult.failed > 0"
        :data="importResult.errors"
        border
        max-height="320"
        style="margin-top: 16px"
      >
        <el-table-column prop="row" label="行号" width="80" />
        <el-table-column prop="student_no" label="学号" min-width="120">
          <template #default="{ row }">{{ row.student_no || '—' }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="失败原因" min-width="200" />
      </el-table>

      <template #footer>
        <el-button type="primary" @click="closeResult">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.students-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}
.pagination {
  display: flex;
  justify-content: flex-end;
}
.import-tips {
  color: #606266;
  font-size: 13px;
}
.import-cols {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.col-tag {
  margin: 0;
}
.result-summary {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>
