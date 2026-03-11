import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomeView.vue'),
  },
  {
    path: '/interpret/:patientId?',
    name: 'Interpret',
    component: () => import('@/views/InterpretView.vue'),
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/UploadView.vue'),
  },
  {
    path: '/float',
    name: 'Float',
    component: () => import('@/views/FloatView.vue'),
  },
  {
    path: '/embed-inner',
    name: 'EmbedInner',
    component: () => import('@/views/EmbedInnerView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
