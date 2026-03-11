# 报告AI解读系统 - HIS/EMR 对接说明

**文档版本**：1.0  
**适用对象**：HIS/EMR 厂商（如卫宁、东软等）实施与开发人员  
**约定**：下文中 `{BaseUrl}` 表示报告AI解读系统部署后的根地址，例如 `https://report-ai.医院域名` 或 `http://服务器IP:80`

---

## 一、对接方式概览

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| **前端页面集成** | 在 EMR/医生工作站中打开本系统页面（新窗口、iframe、弹窗）或注入悬浮球脚本 | 医生在 HIS 内点击「AI 解读」打开解读界面 |
| **后端 REST API** | 调用本系统 HTTP 接口获取报告列表、触发解读、获取结果 | HIS 需在自有界面展示解读结果或做深度集成 |
| **HL7 推送（可选）** | 集成平台向本系统推送 HL7 消息（MLLP），本系统接收后落库并可配置自动解读 | 院方有集成平台且希望报告自动同步到本系统 |

---

## 二、对接方式一：前端页面集成（推荐）

### 2.1 新窗口/标签页打开（患者接口）

在 EMR 患者详情、医嘱等页面增加按钮「AI 解读报告」，点击后打开：

```
{BaseUrl}/patient/{患者ID}
```

- **患者ID**：住院首页序号或门诊挂号序号（须与本院 LIS 使用的 HID/就诊号一致）。
- **行为**：进入本系统后**直接展示该患者报告列表**，医生**选中某条报告即解读该条**（左侧可展示 PDF，右侧为 AI 解读结果），无需再输入患者号。

**示例**：`https://report-ai.xxhospital.com/patient/4435923`

### 2.2 内嵌 iframe

在 EMR 某区域（如侧边栏、弹窗）内嵌：

```
{BaseUrl}/embed-inner?pid={患者ID}
```

- **行为**由院方配置决定：
  - **列表选读**：先展示报告列表，选中某条后解读该条；
  - **自动最新**：进入后自动解读该患者最新一条报告。

### 2.3 悬浮球方式

在 EMR 页面模板中注入脚本（由院方提供本系统域名或 IP）：

```html
<script src="{BaseUrl}/embed.js"></script>
```

- 页面右侧出现悬浮球，点击后侧边栏加载本系统嵌入页；若当前页面能提供患者 ID（URL 参数或页面元素），可带 `?pid={患者ID}`，实现「当前患者」上下文。
- 患者 ID 提取规则见 `embed.js` 内 `extractPatientId()`，可按本院 EMR 页面结构由驻场调整选择器。

### 2.4 患者 ID 约定

- 本系统将「患者 ID」统一视为**住院首页序号或门诊挂号序号**（与 LIS 使用的 HID/就诊号一致）。
- 请与院方确认：EMR 传递的「患者ID」与 LIS 使用的序号是否一致，以便正确拉取报告列表并解读。

---

## 三、对接方式二：后端 REST API

### 3.1 基础说明

- **基础路径**：`{BaseUrl}/api/v1`
- **请求**：JSON（需 body 的接口），编码 UTF-8。
- **认证**：当前版本无强制鉴权；若院方要求可后续增加 API Key 等，需提前约定。
- **完整接口文档（OpenAPI）**：`{BaseUrl}/docs`，HIS 厂商可据此查看请求/响应结构。

### 3.2 核心接口

#### 获取患者报告列表

```
GET /api/v1/report/list/{patient_id}
```

- **路径参数**：`patient_id` — 住院号/门诊号。
- **响应**（200）：

```json
{
  "patient": {
    "patient_id": "4435923",
    "name": "张*",
    "gender": "男",
    "age": 52,
    "department": "内科"
  },
  "reports": [
    {
      "report_no": "8617002",
      "report_title": "血常规+CRP(末梢血6岁以下)",
      "report_date": "2026-03-09T23:14:21",
      "has_abnormal": false,
      "has_critical": false,
      "has_interpretation": false,
      "pdf_url": "/api/v1/report/pdf?patient_id=4435923&report_no=8617002"
    }
  ],
  "total": 1
}
```

- **错误**：404 未找到患者；500 服务异常。

#### AI 解读报告

```
POST /api/v1/report/interpret
Content-Type: application/json
```

- **请求体**：

```json
{
  "patient_id": "4435923",
  "report_no": "8617002",
  "department_code": "general",
  "report_type": "lab"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| patient_id | string | 是 | 住院号/门诊号 |
| report_no | string | 否 | 报告编号；不传则解读该患者最新一条 |
| department_code | string | 否 | 科室，默认 general；可选 hematology/internal/respiratory |
| report_type | string | 否 | 报告类型，默认 lab；可选 ultrasound/ecg/eeg/pulmonary/ct/xray/mri |

- **响应**（200）：解读结果，包含 `abnormal_summary`、`clinical_significance`、`clinical_suggestion`、`abnormal_items` 等。
- **错误**：404 未找到患者或报告；500 解读服务异常。

#### 报告 PDF 流（用于左侧展示 PDF）

```
GET /api/v1/report/pdf?patient_id={patient_id}&report_no={report_no}
```

- **响应**：`Content-Type: application/pdf`，PDF 二进制流；可直接用于 iframe 或下载。
- **错误**：404 未找到报告；501 当前 LIS 适配器不支持 PDF 代理。

#### 患者搜索（可选）

```
GET /api/v1/report/patient/search?keyword={关键词}
```

- **响应**：`{ "data": [ PatientInfo, ... ], "total": n }`，用于按姓名/号检索患者（视本系统与 LIS 对接方式而定）。

### 3.3 其他接口

| 接口 | 说明 |
|------|------|
| GET /api/v1/system/config | 前端配置（医院名称、科室/报告类型枚举、embed_report_mode 等） |
| GET /api/v1/system/health | 健康检查（vLLM、OCR、LIS、HL7 状态） |
| GET /api/v1/system/lis-check | LIS 连通性检测 |

---

## 四、对接方式三：HL7 消息推送（可选）

- 仅当院方启用「集成平台 → 本系统」HL7 推送时适用。
- 本系统作为**接收端**：监听 **MLLP**（默认端口 **2575**），接收 HL7 消息（如 ORU^R01），回 ACK，解析后落库并可配置为自动解读。
- HIS/集成平台侧：按院方要求配置向本系统 `IP:2575` 推送 HL7；消息格式与字段以院方与集成平台约定为准，本系统支持通过配置文件映射常用段（如 PID、OBR、OBX）。

---

## 五、环境与前置条件

- 本系统由院方部署（独立服务器或 K8s），HIS 厂商仅需按上述方式调用或打开页面即可。
- 报告数据来源由院方配置本系统与 LIS/集成平台对接（如卫宁 ASMX、HL7 等），HIS 厂商无需直连 LIS；若需由 HIS/集成平台向本系统推送报告，则采用 HL7 或院方约定的接口。

---

## 六、对接清单（HIS 厂商自检）

- [ ] 确认对接方式：仅前端集成 / 仅 API / 前端 + API / 含 HL7。
- [ ] 确认患者 ID 含义（住院号/门诊号）与传参方式（URL 路径、query、或 API 参数）。
- [ ] 若使用「患者接口」固定为列表选读：统一使用 `{BaseUrl}/patient/{患者ID}`。
- [ ] 若使用 iframe/嵌入：确认 `{BaseUrl}`、是否带 `pid`、以及院方配置的「列表选读」或「自动最新一条」。
- [ ] 若调用 API：记录需用到的接口（list、interpret、pdf 等），并通过 `{BaseUrl}/docs` 核对最新请求/响应格式。
