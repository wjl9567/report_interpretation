<template>
  <div class="upload-container">
    <!-- 顶部导航 -->
    <div class="top-bar">
      <div class="top-left">
        <el-button text @click="$router.push('/')">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <span class="app-title">上传报告图片解读</span>
      </div>
      <div class="top-right">
        <span class="disclaimer-text">⚠ 仅供临床参考，不替代医生诊断</span>
      </div>
    </div>

    <div class="main-area">
      <!-- 左侧：上传区域 -->
      <div class="left-panel">
        <div class="panel-header"><h3>上传报告图片</h3></div>

        <div class="upload-section">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
            accept=".jpg,.jpeg,.png,.bmp,.tiff,.tif"
          >
            <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              将报告图片拖拽到此处，或 <em>点击选择</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 JPG/PNG/BMP/TIFF 格式，单张最大 10MB
              </div>
            </template>
          </el-upload>

          <!-- 图片预览 -->
          <div class="preview-area" v-if="previewUrl">
            <img :src="previewUrl" alt="报告预览" class="preview-img" />
          </div>
        </div>

        <!-- 患者信息（可选） -->
        <div class="patient-form">
          <h4>患者信息（可选，有助于提升解读质量）</h4>
          <el-form :model="patientForm" label-width="70px" size="small">
            <el-row :gutter="12">
              <el-col :span="8">
                <el-form-item label="姓名">
                  <el-input v-model="patientForm.name" placeholder="患者姓名" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="性别">
                  <el-select v-model="patientForm.gender" placeholder="性别">
                    <el-option label="男" value="男" />
                    <el-option label="女" value="女" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="年龄">
                  <el-input v-model="patientForm.age" placeholder="年龄" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <!-- 科室选择 + 解读按钮 -->
        <div class="action-area">
          <el-select v-model="reportType" placeholder="报告类型" style="width: 130px">
            <el-option label="检验报告" value="lab" />
            <el-option label="B超" value="ultrasound" />
            <el-option label="心电图" value="ecg" />
            <el-option label="脑电图" value="eeg" />
            <el-option label="肺功能" value="pulmonary" />
            <el-option label="CT" value="ct" />
            <el-option label="放射/X光" value="xray" />
            <el-option label="核磁共振" value="mri" />
          </el-select>
          <el-select v-model="departmentCode" placeholder="选择科室" style="width: 120px">
            <el-option label="通用" value="general" />
            <el-option label="血液科" value="hematology" />
            <el-option label="内科" value="internal" />
            <el-option label="呼吸科" value="respiratory" />
          </el-select>
          <el-button
            type="primary"
            size="large"
            :loading="interpreting"
            :disabled="!selectedFile"
            @click="doInterpret"
          >
            <el-icon><MagicStick /></el-icon>
            {{ interpreting ? 'AI解读中...' : '开始AI解读' }}
          </el-button>
        </div>
      </div>

      <!-- 右侧：解读结果 -->
      <div class="right-panel">
        <div class="panel-header">
          <h3>AI解读结果</h3>
          <div class="interpret-meta" v-if="result">
            <el-tag type="info" size="small">{{ result.model_name }}</el-tag>
            <el-tag type="info" size="small">{{ result.latency_ms }}ms</el-tag>
          </div>
        </div>

        <!-- 加载状态 -->
        <div class="loading-state" v-if="interpreting">
          <el-icon class="loading-icon" :size="32"><Loading /></el-icon>
          <p>正在识别并解读报告，请稍候...</p>
          <p class="loading-sub">OCR识别 → AI解读，预计需要5-10秒</p>
        </div>

        <!-- 解读结果 -->
        <div class="result-area" v-else-if="result">
          <!-- OCR 识别文本 -->
          <el-collapse v-model="activeCollapse">
            <el-collapse-item title="OCR识别原文（点击展开）" name="ocr">
              <div class="ocr-text">{{ result.ocr_text }}</div>
            </el-collapse-item>
          </el-collapse>

          <!-- AI 解读 -->
          <div class="interpret-content" v-html="formatContent(result.interpretation)"></div>

          <!-- 免责声明 -->
          <div class="result-disclaimer">
            ⚠ {{ result.disclaimer }}
          </div>
        </div>

        <!-- 空状态 -->
        <div class="empty-state" v-else>
          <el-empty description="上传报告图片后点击解读" :image-size="120" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadAndInterpret } from '@/api'

const uploadRef = ref(null)
const selectedFile = ref(null)
const previewUrl = ref('')
const interpreting = ref(false)
const result = ref(null)
const reportType = ref('lab')
const departmentCode = ref('general')
const activeCollapse = ref([])
const patientForm = ref({ name: '', gender: '', age: '' })

function handleFileChange(uploadFile) {
  selectedFile.value = uploadFile.raw
  previewUrl.value = URL.createObjectURL(uploadFile.raw)
  result.value = null
}

function handleExceed() {
  ElMessage.warning('只能上传一张图片，请先移除已选图片')
}

async function doInterpret() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择报告图片')
    return
  }

  interpreting.value = true
  result.value = null

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('department_code', departmentCode.value)
  formData.append('report_type', reportType.value)
  if (patientForm.value.name) formData.append('patient_name', patientForm.value.name)
  if (patientForm.value.gender) formData.append('patient_gender', patientForm.value.gender)
  if (patientForm.value.age) formData.append('patient_age', patientForm.value.age)

  try {
    const res = await uploadAndInterpret(formData)
    result.value = res.data
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '解读失败，请重试')
  } finally {
    interpreting.value = false
  }
}

function formatContent(text) {
  if (!text) return ''
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/【(.*?)】/g, '<h4 style="margin:16px 0 8px;color:#1677ff">$1</h4>')
    .replace(/- /g, '• ')
}
</script>

<style scoped>
.upload-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
}

.top-bar {
  height: 52px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
}

.top-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-title {
  font-size: 16px;
  font-weight: 600;
  color: #1677ff;
}

.top-right {
  display: flex;
  align-items: center;
}

.disclaimer-text {
  font-size: 12px;
  color: #ff4d4f;
  background: #fff2f0;
  padding: 4px 12px;
  border-radius: 4px;
}

.main-area {
  flex: 1;
  display: flex;
  gap: 1px;
  background: #e8e8e8;
  overflow: hidden;
}

.left-panel, .right-panel {
  width: 50%;
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.panel-header {
  padding: 12px 20px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.panel-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.interpret-meta {
  display: flex;
  gap: 6px;
}

.upload-section {
  padding: 20px;
}

.preview-area {
  margin-top: 16px;
  text-align: center;
}

.preview-img {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.patient-form {
  padding: 0 20px 12px;
}

.patient-form h4 {
  font-size: 13px;
  color: #888;
  font-weight: 400;
  margin-bottom: 12px;
}

.action-area {
  padding: 16px 20px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #1677ff;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

.loading-sub {
  font-size: 13px;
  color: #999;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.result-area {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.ocr-text {
  font-size: 13px;
  line-height: 1.8;
  color: #666;
  white-space: pre-wrap;
  background: #fafafa;
  padding: 12px;
  border-radius: 6px;
}

.interpret-content {
  margin-top: 20px;
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

.result-disclaimer {
  margin-top: 24px;
  padding: 12px 16px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 8px;
  font-size: 13px;
  color: #ad6800;
  text-align: center;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
