<script setup>
// 主内容区：用 <router-view> 渲染当前路由对应的子页面。
// 路由结构上，本组件（MainLayout）是父路由，四个业务页是它的 children。
</script>

<template>
  <el-main class="app-main">
    <router-view />
  </el-main>
</template>

<style scoped>
.app-main {
  background-color: #f5f7fa;
  padding: 20px;
}
</style>
