<template>
  <div class="app-wrap">
    <router-view />
    <AppFooter />
  </div>
</template>

<script setup>
import AppFooter from '@/components/AppFooter.vue'
</script>

<style>
.app-wrap {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-wrap > :first-child {
  flex: 1;
}
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  background-color: #f0f2f5;
  color: #333;
}
</style>
