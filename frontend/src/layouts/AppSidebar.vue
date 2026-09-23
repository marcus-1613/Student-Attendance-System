<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

// 左侧 Sidebar 菜单，点击触发真正的路由跳转。
// 高亮项根据当前路由路径自动计算（如 /students 高亮"学生管理"）。

const router = useRouter()
const route = useRoute()

const menus = [
  { path: '/students', label: '学生管理' },
  { path: '/faces', label: '人脸录入' },
  { path: '/recognition', label: '实时识别' },
  { path: '/attendance', label: '考勤记录' },
  { path: '/stats', label: '数据统计' },
  { path: '/notices', label: '公告管理' },
  { path: '/audit', label: '脸库审计' },
]

// 当前高亮菜单 = 当前路由 path 对应的菜单项
const activeMenu = computed(() => route.path)

function onSelect(path) {
  router.push(path)
}
</script>

<template>
  <el-aside class="app-aside" width="200px">
    <el-menu
      class="app-menu"
      :default-active="activeMenu"
      active-text-color="#409eff"
      background-color="#ffffff"
      text-color="#303133"
      @select="onSelect"
    >
      <el-menu-item
        v-for="item in menus"
        :key="item.path"
        :index="item.path"
      >
        <span>{{ item.label }}</span>
      </el-menu-item>
    </el-menu>
  </el-aside>
</template>

<style scoped>
.app-aside {
  background-color: #ffffff;
  border-right: 1px solid #e4e7ed;
}
.app-menu {
  border-right: none;
}
</style>
