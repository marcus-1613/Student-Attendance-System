<script setup>
// 公告管理页面：公告列表（分页）+ 发布 / 编辑 / 删除。
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { listNotices, createNotice, updateNotice, deleteNotice } from '../../api/notice'
import { useNoticeStore } from '../../stores/notice'

const noticeStore = useNoticeStore()

// ---------- 状态 ----------
const loading = ref(false)
const tableData = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 10,
})

// ---------- 发布/编辑对话框 ----------
const dialogVisible = ref(false)
const dialogMode = ref('create') // 'create' | 'edit'
const submitting = ref(false)
const formRef = ref(null)

const emptyForm = () => ({
  id: null,
  title: '',
  content: '',
  publisher: '',
})
const form = reactive(emptyForm())

const formRules = {
  title: [{ required: true, message: '请输入公告标题', trigger: 'blur' }],
}

// ---------- 数据加载 ----------
async function loadData() {
  loading.value = true
  try {
    const data = await listNotices({
      page: query.page,
      page_size: query.page_size,
    })
    tableData.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e.message || '加载公告列表失败')
  } finally {
    loading.value = false
  }
}

// ---------- 分页 ----------
function handlePageChange(page) {
  query.page = page
  loadData()
}

// ---------- 发布 / 编辑 ----------
function openCreate() {
  dialogMode.value = 'create'
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  Object.assign(form, {
    id: row.id,
    title: row.title,
    content: row.content || '',
    publisher: row.publisher || '',
  })
  dialogVisible.value = true
}

async function submitForm() {
  // 手动校验必填标题
  if (!form.title || !form.title.trim()) {
    ElMessage.warning('请输入公告标题')
    return
  }
  submitting.value = true
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content || null,
      publisher: form.publisher || null,
    }
    if (dialogMode.value === 'create') {
      await createNotice(payload)
      ElMessage.success('发布成功')
    } else {
      await updateNotice(form.id, payload)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    // 重新加载列表（自己发布的公告不会触发自己的 WS 红点，这里刷新列表即可）
    query.page = 1
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
    await ElMessageBox.confirm(`确定删除公告「${row.title}」吗？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch (e) {
    return // 用户取消
  }
  try {
    await deleteNotice(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

// ---------- 详情 ----------
async function openDetail(row) {
  await ElMessageBox.alert(row.content || '（无内容）', row.title, {
    confirmButtonText: '关闭',
  })
}

// ---------- 时间格式化 ----------
function formatTime(datetime) {
  if (!datetime) return ''
  return String(datetime).slice(0, 19).replace('T', ' ')
}

// 进入页面时清除未读数（用户已经看到公告了）
onMounted(() => {
  noticeStore.clearUnread()
  loadData()
})
</script>

<template>
  <div class="notice-page">
    <div class="page-header">
      <h2>公告管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">发布公告</el-button>
    </div>

    <el-table v-loading="loading" :data="tableData" border stripe>
      <el-table-column prop="id" label="ID" width="70" align="center" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="publisher" label="发布人" width="140" align="center">
        <template #default="{ row }">{{ row.publisher || '未知' }}</template>
      </el-table-column>
      <el-table-column label="发布时间" width="180" align="center">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDetail(row)">查看</el-button>
          <el-button size="small" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="query.page"
        :page-size="query.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- 发布 / 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '发布公告' : '编辑公告'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" maxlength="100" placeholder="请输入公告标题" />
        </el-form-item>
        <el-form-item label="发布人" prop="publisher">
          <el-input v-model="form.publisher" maxlength="50" placeholder="请输入发布人（选填）" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="5"
            placeholder="请输入公告内容（选填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ dialogMode === 'create' ? '发布' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.notice-page {
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
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
