<template>
  <footer class="app-footer" v-if="helpUrl || feedbackUrl">
    <a v-if="helpUrl" :href="helpUrl" target="_blank" rel="noopener">使用帮助</a>
    <a v-if="feedbackUrl" :href="feedbackUrl" target="_blank" rel="noopener">问题反馈</a>
  </footer>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getConfig } from '@/api'

const helpUrl = ref('')
const feedbackUrl = ref('')

onMounted(async () => {
  try {
    const res = await getConfig()
    helpUrl.value = res.data.help_url || ''
    feedbackUrl.value = res.data.feedback_url || ''
  } catch {}
})
</script>

<style scoped>
.app-footer {
  padding: 8px 20px;
  text-align: center;
  font-size: 12px;
  color: #999;
  border-top: 1px solid #eee;
  background: #fff;
  display: flex;
  justify-content: center;
  gap: 24px;
}
.app-footer a {
  color: #1677ff;
  text-decoration: none;
}
.app-footer a:hover {
  text-decoration: underline;
}
</style>
