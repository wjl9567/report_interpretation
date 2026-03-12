<template>
  <div class="interpret-container">
    <!-- 顶部导航 -->
    <div class="top-bar">
      <div class="top-left">
        <el-button text @click="goHome">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <span class="app-title">报告AI解读</span>
      </div>
      <div class="top-right">
        <el-select v-model="reportType" placeholder="报告类型" size="small" style="width: 120px">
          <el-option label="检验报告" value="lab" />
          <el-option label="B超" value="ultrasound" />
          <el-option label="心电图" value="ecg" />
          <el-option label="脑电图" value="eeg" />
          <el-option label="肺功能" value="pulmonary" />
          <el-option label="CT" value="ct" />
          <el-option label="放射/X光" value="xray" />
          <el-option label="核磁共振" value="mri" />
        </el-select>
        <el-select v-model="departmentCode" placeholder="选择科室" size="small" style="width: 120px">
          <el-option label="通用" value="general" />
          <el-option label="血液科" value="hematology" />
          <el-option label="内科" value="internal" />
          <el-option label="呼吸科" value="respiratory" />
        </el-select>
        <span class="disclaimer-text">⚠ AI 解读仅供参考，不替代临床判断，诊疗责任由医师承担。</span>
      </div>
    </div>

    <!-- 患者信息条 -->
    <div class="patient-bar" v-if="patientInfo">
      <el-descriptions :column="5" size="small" border>
        <el-descriptions-item :label="patientIdLabel">{{ patientInfo.patient_id }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ patientInfo.name }}</el-descriptions-item>
        <el-descriptions-item label="性别">{{ patientInfo.gender }}</el-descriptions-item>
        <el-descriptions-item label="年龄">{{ patientInfo.age }}岁</el-descriptions-item>
        <el-descriptions-item label="科室">{{ patientInfo.department }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 主内容区域：左右分栏 -->
    <div class="main-content">
      <!-- 左侧：报告列表 + 报告详情 -->
      <div class="left-panel">
        <div class="panel-header">
          <h3>报告</h3>
        </div>

        <!-- 检验/检查 Tab，便于医生按类型查看 -->
        <el-tabs v-model="reportListSourceTab" class="report-source-tabs" v-if="reportList.length > 0">
          <el-tab-pane label="全部" name="all" />
          <el-tab-pane name="lab">
            <template #label>
              <span>检验</span>
              <el-badge v-if="labReportCount > 0" :value="labReportCount" class="tab-badge" />
            </template>
          </el-tab-pane>
          <el-tab-pane name="exam">
            <template #label>
              <span>检查</span>
              <el-badge v-if="examReportCount > 0" :value="examReportCount" class="tab-badge" />
            </template>
          </el-tab-pane>
          <el-tab-pane label="多份对比解读" name="trend" />
        </el-tabs>

        <!-- 多份对比解读页左侧：同类报告≥2 份列表，点击后在右侧展示多份报告解读 -->
        <div class="trend-panel" v-if="reportListSourceTab === 'trend' && patientInfo">
          <div class="trend-groups-title">同类报告（≥2 份）<span class="trend-groups-hint">选一组，多份报告一起提交 AI 解读</span></div>
          <div v-if="trendGroups.length" class="trend-groups-list">
            <div
              v-for="g in trendGroups"
              :key="g.title"
              class="trend-group-item"
              :class="{ active: selectedTrendGroup?.title === g.title }"
              @click="selectTrendGroup(g)"
            >
              <span class="trend-group-name">{{ g.title }}</span>
              <el-tag size="small" type="info">{{ g.count }} 份</el-tag>
            </div>
          </div>
          <div v-else class="trend-groups-empty">暂无同类多份报告，可切换「全部/检验/检查」查看单份报告</div>
        </div>

        <!-- 报告列表（按 Tab 筛选） -->
        <div class="report-list" v-else-if="filteredReportList.length > 0">
          <div
            v-for="report in filteredReportList"
            :key="report.report_no"
            class="report-list-item"
            :class="{ active: selectedReportNo === report.report_no }"
            @click="selectReport(report)"
          >
            <div class="report-item-title">
              {{ report.report_title }}
              <el-tag v-if="report.report_source === 'lab'" type="info" size="small" class="report-source-tag">检验</el-tag>
              <el-tag v-else-if="report.report_source === 'exam'" type="info" size="small" class="report-source-tag">检查</el-tag>
              <el-tag v-if="report.has_critical" type="danger" size="small">危急值</el-tag>
              <el-tag v-else-if="report.has_abnormal" type="warning" size="small">异常</el-tag>
            </div>
            <div class="report-item-date">{{ formatDate(report.report_date) }}</div>
          </div>
        </div>
        <div v-else-if="reportList.length > 0 && filteredReportList.length === 0 && reportListSourceTab !== 'trend'" class="report-list-empty-tab">
          <span class="empty-tab-hint">当前分类暂无报告</span>
        </div>

        <!-- 报告 PDF 展示（LIS 返回 FILEURL 时） -->
        <div class="report-pdf-wrap" v-if="selectedReport?.pdf_url">
          <iframe
            :src="pdfIframeSrc"
            class="report-pdf-iframe"
            title="报告PDF"
          />
        </div>

        <!-- 报告详情表格：解读后展示异常项（带等级），解读前或无 PDF 时展示报告项目列表 -->
        <div class="report-detail" v-else-if="interpretResult">
          <el-table
            :data="interpretResult.abnormal_items"
            stripe
            size="small"
            :row-class-name="getRowClassName"
          >
            <el-table-column prop="name" label="检验项目" min-width="160" />
            <el-table-column label="结果" min-width="100">
              <template #default="{ row }">
                <span :style="{ color: row.color, fontWeight: row.abnormal_level !== 'normal' ? '600' : '400' }">
                  {{ row.value }} {{ row.unit }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="reference_range" label="参考范围" min-width="120" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="getLevelTagType(row.abnormal_level)"
                  size="small"
                  v-if="row.abnormal_level !== 'normal'"
                >
                  {{ row.level_label }}
                </el-tag>
                <span v-else style="color: #52c41a">正常</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <!-- 解读前：无 PDF 时展示报告项目（先看再解读） -->
        <div class="report-detail" v-else-if="reportDetail?.items?.length">
          <div class="report-detail-tip">报告项目（点击右侧「开始AI解读」获取解读结果）</div>
          <el-table :data="reportDetail.items" stripe size="small">
            <el-table-column prop="name" label="检验项目" min-width="160" />
            <el-table-column label="结果" min-width="100">
              <template #default="{ row }">
                {{ row.value }} {{ row.unit }}
              </template>
            </el-table-column>
            <el-table-column prop="reference_range" label="参考范围" min-width="120" />
            <el-table-column prop="abnormal_flag" label="标记" width="70" align="center" />
          </el-table>
        </div>

        <!-- 空状态：可操作 -->
        <div class="empty-state" v-if="!loading && reportList.length === 0 && searched">
          <el-empty description="未找到该患者的报告">
            <template #description>
              <p>未找到该患者的报告</p>
              <p class="empty-hint">请核对住院号/门诊号或病历号是否与系统一致，或联系信息科确认。</p>
              <el-button type="primary" @click="goHome">返回重新输入</el-button>
            </template>
          </el-empty>
        </div>
      </div>

      <!-- 右侧：AI解读结果 或 多份对比解读页（多份报告解读） -->
      <div class="right-panel">
        <div class="panel-header">
          <h3>{{ reportListSourceTab === 'trend' ? '多份报告对比解读' : 'AI解读结果' }}</h3>
          <div class="interpret-meta" v-if="reportListSourceTab === 'trend' && multiInterpretResult">
            <span class="meta-primary">{{ multiInterpretResult.report_title }} · {{ multiInterpretResult.report_nos?.length || 0 }} 份</span>
            <span class="meta-secondary">{{ multiInterpretResult.model_name }} · {{ multiInterpretResult.latency_ms }}ms</span>
          </div>
          <div class="interpret-meta" v-else-if="interpretResult">
            <span class="meta-primary">报告编号：{{ interpretResult.report_no }}</span>
            <span class="meta-primary">解读时间：{{ interpretedAtLabel }}</span>
            <el-tooltip content="基于异常项覆盖与危急值情况评估，供参考" placement="top">
              <el-tag :type="confidenceType" size="small">可信度: {{ confidenceLabel }}</el-tag>
            </el-tooltip>
            <span class="meta-secondary">{{ interpretResult.model_name }} · {{ interpretResult.latency_ms }}ms</span>
          </div>
        </div>

        <!-- 多份对比解读页右侧：多份报告解读 -->
        <template v-if="reportListSourceTab === 'trend'">
          <div class="loading-state" v-if="multiInterpretLoading">
            <el-icon class="loading-icon" :size="32"><Loading /></el-icon>
            <p>正在生成多份报告对比解读…</p>
          </div>
          <div v-else-if="multiInterpretResult" class="interpret-result multi-interpret-result">
            <div class="result-actions">
              <el-button type="primary" link size="small" @click="copyMultiInterpret">复制解读结果</el-button>
            </div>
            <div class="result-section">
              <div class="section-title">对比与趋势总结</div>
              <div class="section-content" v-html="formatContent(multiInterpretResult.summary)"></div>
            </div>
            <div class="result-section">
              <div class="section-title">临床建议</div>
              <div class="section-content" v-html="formatContent(multiInterpretResult.suggestion)"></div>
            </div>
            <div class="result-disclaimer">
              多份报告对比解读为辅助分析，临床决策请结合患者完整信息。诊疗责任由医师承担。
            </div>
          </div>
          <div v-else class="empty-interpret">
            <p class="trend-placeholder">请从左侧选择「同类报告（≥2 份）」：多份报告将一起提交 AI 做对比解读。</p>
          </div>
        </template>

        <!-- 单份报告解读区（非趋势 Tab） -->
        <template v-else>
        <!-- 科室/类型切换提示 -->
        <div class="switch-hint" v-if="showSwitchHint">
          已切换科室或报告类型，请点击「开始AI解读」重新解读。
        </div>

        <!-- 加载状态：分步提示 -->
        <div class="loading-state" v-if="interpreting">
          <el-icon class="loading-icon" :size="32"><Loading /></el-icon>
          <p>{{ loadingStepText }}</p>
        </div>

        <!-- 解读失败：可重试 -->
        <div class="error-retry" v-else-if="interpretError">
          <el-alert :title="interpretError" type="error" show-icon :closable="false" />
          <el-button type="primary" @click="doInterpret" style="margin-top: 12px">重试解读</el-button>
        </div>

        <!-- 解读结果 -->
        <div class="interpret-result" v-else-if="interpretResult">
          <div class="result-actions">
            <el-button type="primary" link size="small" @click="copySingleInterpret">复制解读结果</el-button>
          </div>
          <div class="result-section">
            <div class="section-title">
              <el-icon color="#ff4d4f"><WarningFilled /></el-icon>
              <span>异常总结</span>
            </div>
            <div class="section-content" v-html="formatContent(interpretResult.abnormal_summary)"></div>
          </div>

          <div class="result-section">
            <div class="section-title">
              <el-icon color="#1677ff"><InfoFilled /></el-icon>
              <span>临床意义</span>
            </div>
            <div class="section-content" v-html="formatContent(interpretResult.clinical_significance)"></div>
          </div>

          <div class="result-section">
            <div class="section-title">
              <el-icon color="#52c41a"><CircleCheckFilled /></el-icon>
              <span>临床建议</span>
            </div>
            <div class="section-content" v-html="formatContent(interpretResult.clinical_suggestion)"></div>
          </div>

          <div class="result-disclaimer">
            本结果基于异常项与危急值覆盖情况评估，临床决策请结合患者完整信息。
          </div>
          <div class="result-disclaimer">
            ⚠ {{ interpretResult.disclaimer }}
          </div>
        </div>

        <!-- 未解读状态 -->
        <div class="empty-interpret" v-else-if="!interpreting && selectedReportNo && !interpretError">
          <el-button type="primary" size="large" @click="doInterpret">
            <el-icon><MagicStick /></el-icon>
            开始AI解读
          </el-button>
        </div>

        <div class="empty-interpret" v-else>
          <p style="color: #999">请先选择一份报告</p>
        </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getConfig, getReportList, getReportDetail, interpretReport, interpretMulti } from '@/api'
import { formatDate } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()

const patientInfo = ref(null)
const reportList = ref([])
const selectedReportNo = ref('')
const reportDetail = ref(null)
const interpretResult = ref(null)
const interpretError = ref('')
const reportType = ref('lab')
const departmentCode = ref('general')
const loading = ref(false)
const loadingStep = ref('fetch')
const interpreting = ref(false)
const searched = ref(false)
const mssqlHidResolver = ref(false)
const lastInterpretParams = ref(null)
const reportListSourceTab = ref('all') // all | lab | exam | trend
const selectedTrendGroup = ref(null)
const multiInterpretLoading = ref(false)
const multiInterpretResult = ref(null)

const patientIdLabel = computed(() => (mssqlHidResolver.value ? '患者标识' : '住院号'))
const confidenceLabel = computed(() => {
  const map = { high: '高', medium: '中', low: '低' }
  return map[interpretResult.value?.confidence] || ''
})
const confidenceType = computed(() => {
  const map = { high: 'success', medium: 'warning', low: 'danger' }
  return map[interpretResult.value?.confidence] || 'info'
})
const interpretedAtLabel = computed(() => {
  if (!interpretResult.value?.report_no) return ''
  return new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
})
const loadingStepText = computed(() =>
  loadingStep.value === 'fetch' ? '正在获取报告列表...' : 'AI正在解读报告，请稍候...'
)
const showSwitchHint = computed(() => {
  if (!interpretResult.value || !lastInterpretParams.value) return false
  return (
    departmentCode.value !== lastInterpretParams.value.department_code ||
    reportType.value !== lastInterpretParams.value.report_type
  )
})

const labReportCount = computed(() => reportList.value.filter((r) => r.report_source === 'lab').length)
const examReportCount = computed(() => reportList.value.filter((r) => r.report_source === 'exam').length)
const filteredReportList = computed(() => {
  if (reportListSourceTab.value === 'lab') return reportList.value.filter((r) => r.report_source === 'lab')
  if (reportListSourceTab.value === 'exam') return reportList.value.filter((r) => r.report_source === 'exam')
  return reportList.value
})
const selectedReport = computed(() =>
  reportList.value.find((r) => r.report_no === selectedReportNo.value)
)

const pdfIframeSrc = computed(() => {
  const url = selectedReport.value?.pdf_url
  if (!url) return ''
  return url
})

/** 同类报告≥2 的分组（按 report_title），用于多份对比解读页左侧列表 */
const trendGroups = computed(() => {
  const list = reportList.value || []
  const map = new Map()
  for (const r of list) {
    const title = r.report_title || '未命名报告'
    if (!map.has(title)) map.set(title, { title, report_nos: [], count: 0 })
    const g = map.get(title)
    g.report_nos.push(r.report_no)
    g.count += 1
  }
  return Array.from(map.values()).filter((g) => g.count >= 2).sort((a, b) => b.count - a.count)
})

watch([departmentCode, reportType], () => {
  if (interpretResult.value) {
    interpretResult.value = null
    interpretError.value = ''
  }
})
watch([reportListSourceTab, filteredReportList], () => {
  if (reportListSourceTab.value === 'trend') return
  const list = filteredReportList.value
  if (list.length === 0) return
  const stillInList = list.some((r) => r.report_no === selectedReportNo.value)
  if (!stillInList) selectedReportNo.value = list[0].report_no
}, { immediate: false })

/** 选中同类报告组，请求多份报告对比解读 */
async function selectTrendGroup(g) {
  if (!patientInfo.value || !g?.report_nos?.length) return
  selectedTrendGroup.value = g
  multiInterpretLoading.value = true
  multiInterpretResult.value = null
  try {
    const res = await interpretMulti(patientInfo.value.patient_id, g.report_nos)
    multiInterpretResult.value = res.data
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '多份报告解读失败')
  } finally {
    multiInterpretLoading.value = false
  }
}

onMounted(async () => {
  try {
    const cfg = await getConfig()
    mssqlHidResolver.value = !!cfg.data.mssql_hid_resolver
  } catch {}
  const pid = route.params.patientId
  if (pid) {
    await fetchReportList(pid)
  }
})

async function fetchReportList(patientId) {
  loading.value = true
  loadingStep.value = 'fetch'
  searched.value = true
  interpretError.value = ''
  try {
    const res = await getReportList(patientId)
    patientInfo.value = res.data.patient
    reportList.value = res.data.reports
    if (reportList.value.length > 0) {
      const q = route.query
      const wantNo = (q.report_no || q.reportNo || '').trim()
      const autoInterpret = q.auto_interpret === '1' || q.auto_interpret === 'true' || q.auto_interpret === 'yes'
      const found = wantNo ? reportList.value.find((r) => String(r.report_no) === String(wantNo)) : null
      selectedReportNo.value = found ? found.report_no : reportList.value[0].report_no
      interpretResult.value = null
      reportDetail.value = null
      const first = reportList.value.find((r) => r.report_no === selectedReportNo.value) || reportList.value[0]
      if (first && !first.pdf_url) {
        try {
          const detailRes = await getReportDetail(patientInfo.value.patient_id, first.report_no)
          reportDetail.value = detailRes.data
        } catch {}
      }
      if (autoInterpret && selectedReportNo.value) {
        nextTick(() => doInterpret())
      }
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

async function selectReport(report) {
  selectedReportNo.value = report.report_no
  interpretResult.value = null
  interpretError.value = ''
  reportDetail.value = null
  if (!report.pdf_url) {
    try {
      const res = await getReportDetail(patientInfo.value.patient_id, report.report_no)
      reportDetail.value = res.data
    } catch {}
  }
}

async function doInterpret() {
  if (!selectedReportNo.value || !patientInfo.value) return
  interpreting.value = true
  loadingStep.value = 'interpret'
  interpretError.value = ''
  try {
    const res = await interpretReport({
      patient_id: patientInfo.value.patient_id,
      report_no: selectedReportNo.value,
      department_code: departmentCode.value,
      report_type: reportType.value,
    })
    interpretResult.value = res.data
    lastInterpretParams.value = {
      department_code: departmentCode.value,
      report_type: reportType.value,
    }
  } catch (err) {
    interpretError.value = err.response?.data?.detail || 'AI解读失败，请重试'
  } finally {
    interpreting.value = false
  }
}

function goHome() {
  router.push('/')
}

function copySingleInterpret() {
  if (!interpretResult.value) return
  const r = interpretResult.value
  const lines = [
    `【异常总结】\n${r.abnormal_summary || ''}`,
    `【临床意义】\n${r.clinical_significance || ''}`,
    `【临床建议】\n${r.clinical_suggestion || ''}`,
    '',
    `报告编号：${r.report_no}`,
    r.disclaimer || 'AI 解读仅供参考，不替代临床判断，诊疗责任由医师承担。',
  ]
  const text = lines.join('\n\n')
  copyToClipboard(text)
}

function copyMultiInterpret() {
  if (!multiInterpretResult.value) return
  const m = multiInterpretResult.value
  const lines = [
    `【对比与趋势总结】\n${m.summary || ''}`,
    `【临床建议】\n${m.suggestion || ''}`,
    '',
    `报告类型：${m.report_title}，共 ${m.report_nos?.length || 0} 份`,
    '多份报告对比解读为辅助分析，临床决策请结合患者完整信息。诊疗责任由医师承担。',
  ]
  const text = lines.join('\n\n')
  copyToClipboard(text)
}

function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制到剪贴板')).catch(() => ElMessage.warning('复制失败'))
  } else {
    ElMessage.warning('当前浏览器不支持一键复制，请手动选择文字复制')
  }
}

function formatContent(text) {
  if (!text) return ''
  return text
    .replace(/\n/g, '<br/>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/- /g, '• ')
}

function getLevelTagType(level) {
  const map = { critical: 'danger', severe: 'danger', moderate: 'warning', mild: '' }
  return map[level] || 'info'
}

function getRowClassName({ row }) {
  if (row.abnormal_level === 'critical') return 'row-critical'
  if (row.abnormal_level === 'severe') return 'row-severe'
  return ''
}
</script>

<style scoped>
.interpret-container {
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
  gap: 16px;
}

.disclaimer-text {
  font-size: 12px;
  color: #ff4d4f;
  background: #fff2f0;
  padding: 4px 12px;
  border-radius: 4px;
}

.patient-bar {
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.main-content {
  flex: 1;
  display: flex;
  gap: 1px;
  background: #e8e8e8;
  overflow: hidden;
}

.left-panel, .right-panel {
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.left-panel {
  width: 50%;
  min-width: 400px;
}

.right-panel {
  width: 50%;
  min-width: 400px;
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
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.interpret-meta .meta-primary {
  color: #333;
}
.interpret-meta .meta-secondary {
  color: #999;
  font-size: 11px;
}
.report-detail-tip {
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}
.empty-state .empty-hint {
  font-size: 12px;
  color: #888;
  margin: 8px 0 12px;
}
.switch-hint {
  font-size: 12px;
  color: #fa8c16;
  background: #fff7e6;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 0 20px 12px;
}
.error-retry {
  padding: 20px;
}

.report-source-tabs {
  padding: 0 12px 4px;
  flex-shrink: 0;
}
.report-source-tabs :deep(.el-tabs__header) { margin-bottom: 8px; }
.report-source-tabs :deep(.el-tabs__item) { font-size: 13px; }
.report-source-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.tab-badge { margin-left: 4px; }
.report-list-empty-tab { padding: 12px; text-align: center; }
.empty-tab-hint { font-size: 12px; color: #909399; }

.trend-panel { padding: 12px; flex-shrink: 0; border-bottom: 1px solid #f0f0f0; }
.trend-groups-title { font-size: 13px; font-weight: 600; color: #333; margin-bottom: 8px; }
.trend-groups-hint { font-size: 11px; font-weight: 400; color: #909399; margin-left: 6px; }
.trend-groups-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; max-height: 240px; overflow-y: auto; }
.trend-group-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; border-radius: 6px; cursor: pointer; border: 1px solid #eee; }
.trend-group-item:hover { background: #f5f7fa; }
.trend-group-item.active { background: #ecf5ff; border-color: #409eff; }
.trend-group-name { font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.trend-groups-empty { font-size: 12px; color: #909399; padding: 12px 0; }
.trend-placeholder { color: #909399; font-size: 13px; line-height: 1.6; }
.multi-interpret-result .result-section { margin-bottom: 16px; }
.multi-interpret-result .section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: #333; }

.report-list {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.report-list-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-list-item:hover {
  background: #f5f7fa;
}

.report-list-item.active {
  background: #e6f4ff;
  border: 1px solid #91caff;
}

.report-item-title {
  font-size: 14px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-item-date {
  font-size: 12px;
  color: #999;
}

.report-pdf-wrap {
  flex: 1;
  min-height: 400px;
  padding: 12px;
  overflow: hidden;
}

.report-pdf-iframe {
  width: 100%;
  height: 100%;
  min-height: 500px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
}

.report-detail {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #1677ff;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.interpret-result {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.result-actions {
  margin-bottom: 12px;
}
.result-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

.section-content {
  font-size: 14px;
  line-height: 1.8;
  color: #555;
  padding-left: 8px;
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

.empty-interpret {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.row-critical) {
  background-color: #fff1f0 !important;
}

:deep(.row-severe) {
  background-color: #fff7e6 !important;
}
</style>
