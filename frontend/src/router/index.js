import { createRouter, createWebHistory } from 'vue-router'

// 路由结构说明：
// - MainLayout 是父级路由，四个业务页是它的 children。
//   这样访问 /students 时，会先渲染 MainLayout（Header + Sidebar + Main），
//   再由 MainLayout 里的 <router-view> 渲染具体页面。
// - 使用 createWebHistory（HTML5 History 模式），URL 形如 /students，不带 #。
// - 默认路由 / 重定向到 /students。
const routes = [
  { path: '/', redirect: '/students' },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    children: [
      {
        path: 'students',
        name: 'students',
        component: () => import('../views/students/index.vue'),
        meta: { title: '学生管理' },
      },
      {
        path: 'faces',
        name: 'faces',
        component: () => import('../views/faces/index.vue'),
        meta: { title: '人脸录入' },
      },
      {
        path: 'stats',
        name: 'stats',
        component: () => import('../views/stats/index.vue'),
        meta: { title: '数据统计' },
      },
      {
        path: 'notices',
        name: 'notices',
        component: () => import('../views/notices/index.vue'),
        meta: { title: '公告管理' },
      },
      {
        path: 'audit',
        name: 'audit',
        component: () => import('../views/audit/index.vue'),
        meta: { title: '脸库审计' },
      },
      {
        path: 'recognition',
        name: 'recognition',
        component: () => import('../views/recognition/index.vue'),
        meta: { title: '实时识别' },
      },
      {
        path: 'attendance',
        name: 'attendance',
        component: () => import('../views/attendance/index.vue'),
        meta: { title: '考勤记录' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
