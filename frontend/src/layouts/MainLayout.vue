<script setup>
// 整体布局：Header + (Sidebar + Main)。
// 使用 Element Plus 的 ElContainer 组合出经典的后台管理布局。
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'
import AppMain from './AppMain.vue'
</script>

<template>
  <el-container class="main-layout">
    <AppHeader />

    <el-container class="body-container">
      <AppSidebar />
      <AppMain />
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100vh;
}
.body-container {
  flex: 1;
  overflow: hidden;
}
</style>
