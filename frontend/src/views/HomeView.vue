<template>
  <div class="home-container">
    <div class="home-header">
      <div class="logo-area">
        <el-icon :size="32" color="#1677ff"><Monitor /></el-icon>
        <h1>报告AI解读系统</h1>
      </div>
      <div class="hospital-name">{{ hospitalName }}</div>
    </div>

    <div class="search-section">
      <div class="search-card">
        <el-collapse>
          <el-collapse-item name="usage">
            <template #title>
              <span class="usage-title"><el-icon><InfoFilled /></el-icon> 使用说明</span>
            </template>
            <div class="usage-content">
              <p><strong>从本院系统（EMR）打开：</strong>链接中已带患者号时，直接显示该患者报告列表，选择报告即可解读。</p>
              <p><strong>独立使用：</strong>下方输入住院号/门诊号（或病历号、门诊卡号）查询本院报告；或上传外院报告图片进行解读。</p>
            </div>
          </el-collapse-item>
        </el-collapse>
        <h2>{{ searchTitle }}</h2>
        <div class="search-bar">
          <el-input
            v-model="patientId"
            :placeholder="searchPlaceholder"
            size="large"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" size="large" @click="handleSearch" :loading="loading">
            查询报告
          </el-button>
        </div>

        <div class="divider-row">
          <el-divider>或</el-divider>
        </div>
        <el-button type="success" size="large" style="width: 100%" @click="goUpload">
          <el-icon><UploadFilled /></el-icon>
          上传外院报告图片解读
        </el-button>

        <div class="quick-demo">
          <span class="demo-label">演示数据：</span>
          <el-button link type="primary" @click="fillDemo('100001')">内科-张*</el-button>
          <el-button link type="primary" @click="fillDemo('100002')">血液科-李*</el-button>
          <el-button link type="primary" @click="fillDemo('100003')">呼吸科-王*</el-button>
        </div>
      </div>
    </div>

    <div class="features-section">
      <div class="feature-card">
        <el-icon :size="36" color="#1677ff"><Document /></el-icon>
        <h3>智能解读</h3>
        <p>基于安诊儿医疗大模型，专业解读检查检验报告</p>
      </div>
      <div class="feature-card">
        <el-icon :size="36" color="#ff6600"><Warning /></el-icon>
        <h3>异常标注</h3>
        <p>自动识别异常项，按危急值/重度/中度/轻度分级标注</p>
      </div>
      <div class="feature-card">
        <el-icon :size="36" color="#52c41a"><UserFilled /></el-icon>
        <h3>专科适配</h3>
        <p>支持血液科、内科、呼吸科等多科室定制解读</p>
      </div>
    </div>

    <div class="disclaimer">
      本系统AI解读结果仅供临床参考，不替代医生诊断。
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getConfig } from '@/api'

const router = useRouter()
const patientId = ref('')
const loading = ref(false)
const hospitalName = ref('')
const mssqlHidResolver = ref(false)

const searchTitle = computed(() =>
  mssqlHidResolver.value ? '请输入患者住院号/门诊号或病历号/门诊卡号' : '请输入患者住院号/门诊号'
)
const searchPlaceholder = computed(() =>
  mssqlHidResolver.value ? '输入住院号、门诊号或病历号/门诊卡号，如 100001' : '输入住院号或门诊号，如 100001'
)

onMounted(async () => {
  try {
    const res = await getConfig()
    hospitalName.value = res.data.hospital_name ?? ''
    mssqlHidResolver.value = !!res.data.mssql_hid_resolver
  } catch {
    hospitalName.value = ''
  }
})

function handleSearch() {
  const id = patientId.value.trim()
  if (!id) {
    ElMessage.warning(mssqlHidResolver.value ? '请输入住院号、门诊号或病历号/门诊卡号' : '请输入住院号或门诊号')
    return
  }
  router.push({ name: 'Interpret', params: { patientId: id } })
}

function fillDemo(id) {
  patientId.value = id
  handleSearch()
}

function goUpload() {
  router.push('/upload')
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.home-header {
  width: 100%;
  padding: 16px 32px;
  background: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-area h1 {
  font-size: 20px;
  color: #1677ff;
  font-weight: 600;
}

.hospital-name {
  font-size: 14px;
  color: #666;
}

.search-section {
  margin-top: 80px;
  width: 100%;
  max-width: 640px;
  padding: 0 20px;
}

.search-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  text-align: center;
}

.search-card h2 {
  font-size: 22px;
  font-weight: 500;
  color: #333;
  margin-bottom: 24px;
}

.search-bar {
  display: flex;
  gap: 12px;
}

.search-bar .el-input {
  flex: 1;
}

.quick-demo {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.demo-label {
  font-size: 13px;
  color: #999;
}

.usage-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}
.usage-content {
  font-size: 13px;
  color: #666;
  line-height: 1.7;
}
.usage-content p {
  margin: 0 0 8px;
}
.usage-content p:last-child {
  margin-bottom: 0;
}

.features-section {
  margin-top: 60px;
  display: flex;
  gap: 24px;
  padding: 0 20px;
  max-width: 900px;
}

.feature-card {
  flex: 1;
  background: #fff;
  border-radius: 12px;
  padding: 32px 24px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.feature-card h3 {
  margin-top: 16px;
  font-size: 16px;
  color: #333;
}

.feature-card p {
  margin-top: 8px;
  font-size: 13px;
  color: #888;
  line-height: 1.6;
}

.disclaimer {
  margin-top: auto;
  padding: 20px;
  text-align: center;
  font-size: 12px;
  color: #bbb;
}
</style>
