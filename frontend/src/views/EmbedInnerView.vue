<template>
  <div class="embed-container">
    <div class="embed-header">
      <span class="embed-title">报告AI解读</span>
    </div>

    <!-- 搜索区域 -->
    <div class="embed-search">
      <el-input
        v-model="patientId"
        placeholder="输入住院号/门诊号"
        size="small"
        clearable
        @keyup.enter="doInterpret"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <div class="select-row">
        <el-select v-model="reportType" size="small" style="flex:1">
          <el-option label="检验报告" value="lab" />
          <el-option label="B超" value="ultrasound" />
          <el-option label="心电图" value="ecg" />
          <el-option label="脑电图" value="eeg" />
          <el-option label="肺功能" value="pulmonary" />
          <el-option label="CT" value="ct" />
          <el-option label="放射/X光" value="xray" />
          <el-option label="核磁共振" value="mri" />
        </el-select>
        <el-select v-model="deptCode" size="small" style="flex:1">
          <el-option label="通用" value="general" />
          <el-option label="血液科" value="hematology" />
          <el-option label="内科" value="internal" />
          <el-option label="呼吸科" value="respiratory" />
        </el-select>
      </div>
      <el-button type="primary" size="small" style="width:100%; margin-top:8px" @click="doInterpret" :loading="loading">
        查询并解读
      </el-button>
    </div>

    <!-- 上传入口 -->
    <div class="embed-upload">
      <el-upload :auto-upload="false" :show-file-list="false" :on-change="handleUpload" accept=".jpg,.jpeg,.png,.bmp">
        <el-button size="small" style="width:100%">
          <el-icon><UploadFilled /></el-icon> 上传报告图片解读
        </el-button>
      </el-upload>
    </div>

    <!-- 结果区域 -->
    <div class="embed-result">
      <div v-if="loading" class="state-box">
        <el-icon class="spin" :size="24"><Loading /></el-icon>
        <span>AI解读中...</span>
      </div>
      <div v-else-if="result" class="result-content" v-html="formatResult(result)"></div>
      <div v-else-if="error" style="padding:8px 0">
        <el-alert :title="error" type="error" show-icon :closable="false" />
      </div>
      <div v-else class="state-box" style="color:#bbb">
        输入住院号/门诊号查询<br/>或上传报告图片
      </div>
    </div>

    <!-- 全屏入口 -->
    <div class="embed-actions">
      <el-button text size="small" @click="openFull">
        <el-icon><FullScreen /></el-icon> 打开完整版
      </el-button>
    </div>

    <div class="embed-footer">⚠ 仅供临床参考，不替代医生诊断</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { interpretReport, uploadAndInterpret } from '@/api'

const route = useRoute()
const patientId = ref('')
const reportType = ref('lab')
const deptCode = ref('general')
const loading = ref(false)
const result = ref('')
const error = ref('')

onMounted(() => {
  const pid = route.query.pid
  if (pid) {
    patientId.value = pid
    doInterpret()
  }
})

async function doInterpret() {
  if (!patientId.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = ''
  try {
    const res = await interpretReport({
      patient_id: patientId.value.trim(),
      department_code: deptCode.value,
      report_type: reportType.value,
    })
    const d = res.data
    result.value = [
      d.abnormal_summary ? `【异常发现】\n${d.abnormal_summary}` : '',
      d.clinical_significance ? `【临床意义】\n${d.clinical_significance}` : '',
      d.clinical_suggestion ? `【临床建议】\n${d.clinical_suggestion}` : '',
    ].filter(Boolean).join('\n\n') || '解读完成'
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

async function handleUpload(uploadFile) {
  loading.value = true
  error.value = ''
  result.value = ''
  const formData = new FormData()
  formData.append('file', uploadFile.raw)
  formData.append('department_code', deptCode.value)
  formData.append('report_type', reportType.value)
  try {
    const res = await uploadAndInterpret(formData)
    result.value = res.data.interpretation
  } catch (err) {
    error.value = err.response?.data?.detail || '解读失败'
  } finally {
    loading.value = false
  }
}

function openFull() {
  const url = patientId.value ? `/interpret/${patientId.value}` : '/'
  window.open(url, '_blank')
}

function formatResult(text) {
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/【(.*?)】/g, '<h4 style="margin:12px 0 6px;color:#1677ff;font-size:13px">$1</h4>')
    .replace(/- /g, '• ')
}
</script>

<style scoped>
.embed-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #fff;
}
.embed-header {
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.embed-title {
  font-size: 15px;
  font-weight: 600;
  color: #1677ff;
}
.embed-search {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.select-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.embed-upload {
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.embed-result {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 180px;
  gap: 12px;
  color: #1677ff;
  text-align: center;
  font-size: 13px;
  line-height: 1.8;
}
.spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.result-content {
  font-size: 13px;
  line-height: 1.8;
  color: #333;
}
.embed-actions {
  padding: 4px 16px;
  border-top: 1px solid #f0f0f0;
  text-align: center;
  flex-shrink: 0;
}
.embed-footer {
  padding: 6px 16px;
  text-align: center;
  font-size: 11px;
  color: #ff4d4f;
  background: #fff2f0;
  flex-shrink: 0;
}
</style>
