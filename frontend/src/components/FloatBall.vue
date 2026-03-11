<template>
  <div class="float-ball-wrapper">
    <!-- 悬浮球 -->
    <div
      class="float-ball"
      :class="{ expanded: panelVisible }"
      @click="togglePanel"
      @mousedown="startDrag"
      :style="{ top: ballTop + 'px', right: ballRight + 'px' }"
    >
      <el-icon v-if="!panelVisible" :size="24"><Cpu /></el-icon>
      <el-icon v-else :size="20"><Close /></el-icon>
      <span class="ball-label" v-if="!panelVisible">AI</span>
    </div>

    <!-- 侧边面板 -->
    <transition name="slide">
      <div class="side-panel" v-if="panelVisible">
        <div class="panel-header">
          <span class="panel-title">报告AI解读</span>
          <el-button text size="small" @click="openFullPage">
            <el-icon><FullScreen /></el-icon> 全屏
          </el-button>
        </div>

        <!-- 搜索区域 -->
        <div class="panel-search">
          <el-input
            v-model="patientId"
            placeholder="输入住院号/门诊号"
            size="small"
            clearable
            @keyup.enter="searchAndInterpret"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="reportType" size="small" style="width: 110px; margin-top: 8px">
            <el-option label="检验报告" value="lab" />
            <el-option label="B超" value="ultrasound" />
            <el-option label="心电图" value="ecg" />
            <el-option label="脑电图" value="eeg" />
            <el-option label="肺功能" value="pulmonary" />
            <el-option label="CT" value="ct" />
            <el-option label="放射/X光" value="xray" />
            <el-option label="核磁共振" value="mri" />
          </el-select>
          <el-select v-model="deptCode" size="small" style="width: 90px; margin-top: 8px">
            <el-option label="通用" value="general" />
            <el-option label="血液科" value="hematology" />
            <el-option label="内科" value="internal" />
            <el-option label="呼吸科" value="respiratory" />
          </el-select>
          <el-button type="primary" size="small" style="margin-top: 8px; width: 100%" @click="searchAndInterpret" :loading="loading">
            查询并解读
          </el-button>
        </div>

        <!-- 上传图片入口 -->
        <div class="panel-upload">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleUpload"
            accept=".jpg,.jpeg,.png,.bmp"
          >
            <el-button size="small" style="width: 100%">
              <el-icon><UploadFilled /></el-icon> 上传报告图片
            </el-button>
          </el-upload>
        </div>

        <!-- 结果区域 -->
        <div class="panel-result">
          <div v-if="loading" class="loading-area">
            <el-icon class="spin" :size="24"><Loading /></el-icon>
            <span>AI解读中...</span>
          </div>

          <div v-else-if="result" class="result-content" v-html="formatResult(result)"></div>

          <div v-else-if="error" class="error-area">
            <el-alert :title="error" type="error" show-icon :closable="false" />
          </div>

          <div v-else class="empty-area">
            <p>输入住院号查询报告<br/>或上传报告图片</p>
          </div>
        </div>

        <!-- 免责声明 -->
        <div class="panel-footer">
          ⚠ 仅供临床参考，不替代医生诊断
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { interpretReport, uploadAndInterpret } from '@/api'

const panelVisible = ref(false)
const patientId = ref('')
const reportType = ref('lab')
const deptCode = ref('general')
const loading = ref(false)
const result = ref('')
const error = ref('')

const ballTop = ref(200)
const ballRight = ref(20)
let dragging = false
let dragStartY = 0
let dragStartTop = 0

function togglePanel() {
  if (!dragging) {
    panelVisible.value = !panelVisible.value
  }
}

function startDrag(e) {
  dragging = false
  dragStartY = e.clientY
  dragStartTop = ballTop.value

  const onMove = (ev) => {
    const diff = ev.clientY - dragStartY
    if (Math.abs(diff) > 3) dragging = true
    ballTop.value = Math.max(60, Math.min(window.innerHeight - 80, dragStartTop + diff))
  }
  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    setTimeout(() => { dragging = false }, 100)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

async function searchAndInterpret() {
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
    const data = res.data
    result.value = [
      data.abnormal_summary ? `【异常发现】\n${data.abnormal_summary}` : '',
      data.clinical_significance ? `【临床意义】\n${data.clinical_significance}` : '',
      data.clinical_suggestion ? `【临床建议】\n${data.clinical_suggestion}` : '',
    ].filter(Boolean).join('\n\n') || data.full_response || '解读完成'
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

function openFullPage() {
  window.open('/', '_blank')
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
.float-ball-wrapper {
  position: fixed;
  z-index: 99999;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.float-ball {
  position: fixed;
  z-index: 100000;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1677ff, #0958d9);
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(22, 119, 255, 0.4);
  transition: all 0.3s;
  user-select: none;
}

.float-ball:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 24px rgba(22, 119, 255, 0.5);
}

.float-ball.expanded {
  width: 36px;
  height: 36px;
  background: #ff4d4f;
  box-shadow: 0 2px 8px rgba(255, 77, 79, 0.4);
}

.ball-label {
  font-size: 10px;
  font-weight: 700;
  margin-top: -2px;
}

.side-panel {
  position: fixed;
  top: 0;
  right: 0;
  width: 380px;
  height: 100vh;
  background: #fff;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  z-index: 99999;
}

.slide-enter-active, .slide-leave-active {
  transition: transform 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(100%);
}

.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #1677ff;
}

.panel-search {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.panel-upload {
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.panel-result {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.loading-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 12px;
  color: #1677ff;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.result-content {
  font-size: 13px;
  line-height: 1.8;
  color: #333;
}

.empty-area {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  text-align: center;
  color: #bbb;
  font-size: 13px;
  line-height: 1.8;
}

.error-area {
  padding: 12px 0;
}

.panel-footer {
  padding: 8px 16px;
  text-align: center;
  font-size: 11px;
  color: #ff4d4f;
  background: #fff2f0;
  flex-shrink: 0;
}
</style>
