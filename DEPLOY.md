# 报告AI解读系统 - 部署说明（部署人员）

面向运维/部署人员：镜像构建、Kubernetes 部署、PostgreSQL、自动建表与基本验证。

---

## 一、上线前置条件（必读）

**达到「上线给用户使用」目标，须同时满足：**

| 条件 | 说明 |
|------|------|
| **PostgreSQL** | 生产必须使用 PostgreSQL，连接串由 Secret 或 .env 配置；不得使用 SQLite。 |
| **推理服务可达** | **VLLM_BASE_URL** 必须指向院内已部署的**安诊儿推理服务**。**本次实施采用 sglang 部署安诊儿模型**（本系统按 OpenAI 兼容 chat 接口调用；若使用 vLLM 部署亦可兼容）。 |

- **仅配置 Mock LIS 且未配置/不可达推理服务时**：可打开首页、查演示号报告列表，但「AI 解读」会失败，**仅适合演示或联调，不可作为正式上线**。
- **Docker Compose 部署**：复制 `.env.example` 为 `.env` 后修改 `VLLM_BASE_URL`、`HOSPITAL_NAME` 等；详见下文「八、普通服务器部署」。

---

## 二、环境要求

- Docker（构建镜像）
- Kubernetes 集群（1.24+），已安装 Ingress Controller（如 nginx-ingress）
- 可选：集群内部署 PostgreSQL，或使用已有外部 PostgreSQL
- **推理服务**：**本次实施使用 sglang + 安诊儿模型**，本系统通过 `VLLM_BASE_URL` 调用（OpenAI 兼容接口）；PaddleOCR 可在集群内或内网访问（上传图片解读时需要）

---

## 三、构建与推送镜像

在项目根目录执行：

```bash
# 后端
docker build -t report-ai-backend:latest ./backend

# 前端
docker build -t report-ai-frontend:latest ./frontend
```

推送到私有仓库（按实际仓库地址修改）：

```bash
export REGISTRY=your-registry.com/your-namespace

docker tag report-ai-backend:latest $REGISTRY/report-ai-backend:latest
docker push $REGISTRY/report-ai-backend:latest

docker tag report-ai-frontend:latest $REGISTRY/report-ai-frontend:latest
docker push $REGISTRY/report-ai-frontend:latest
```

若使用私有仓库，需在 K8s 中配置 `imagePullSecrets`（见各 Deployment 注释）。

---

## 四、PostgreSQL 与自动建表

- **生产环境使用 PostgreSQL**，连接串通过 Secret 注入，**不得使用 SQLite**。
- **建表**：应用启动时自动执行 `init_db()`，在配置的 PostgreSQL 中创建所需表（departments、patients、reports、interpretations、audit_logs 等），**无需手动执行 SQL**。
- 两种方式二选一：
  - **集群内 PostgreSQL**：使用本仓库提供的 `k8s/postgres.yaml`，与 `k8s/secret.example.yaml` 中的 `POSTGRES_*` 及 `DATABASE_URL` 配合使用。
  - **外部 PostgreSQL**：自建或使用云 RDS，仅在 Secret 中配置 `DATABASE_URL` 即可。

---

## 五、Kubernetes 部署步骤

### 5.1 创建 Secret（必做）

```bash
# 复制模板，按实际环境修改
cp k8s/secret.example.yaml k8s/secret.yaml
# 编辑 k8s/secret.yaml：填写 DATABASE_URL（及若用集群内 PG 则填 POSTGRES_USER/POSTGRES_PASSWORD）
# 注意：secret.yaml 不要提交到代码仓库

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
```

- 使用**集群内 PostgreSQL**：Secret 中需包含 `POSTGRES_USER`、`POSTGRES_PASSWORD`、`DATABASE_URL`（主机填 `report-ai-postgres`）。
- 使用**外部 PostgreSQL**：Secret 中仅需 `DATABASE_URL`，格式：`postgresql+asyncpg://用户:密码@主机:5432/库名`。

### 5.2 修改 ConfigMap

编辑 `k8s/configmap.yaml`，按院内环境修改：

- `VLLM_BASE_URL`：安诊儿推理服务地址（**本次实施为 sglang 部署**，本系统按 OpenAI 兼容接口调用）
- `OCR_SERVICE_URL`：OCR 服务地址（不用上传/解析图片可暂留默认）
- `HOSPITAL_NAME`：医院名称（界面展示）
- `LIS_ADAPTER` / `LIS_USE_ASMX` / `LIS_API_BASE_URL`：对接 LIS 时由实施人员或部署按文档修改

然后：

```bash
kubectl apply -f k8s/configmap.yaml
```

### 5.3 可选：部署集群内 PostgreSQL

仅当使用集群内数据库时执行：

```bash
kubectl apply -f k8s/postgres.yaml
# 等待 Postgres Pod 就绪
kubectl -n report-ai get pods -l component=postgres
```

### 5.4 部署应用

```bash
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
```

或一键（不含 secret，secret 需单独 apply）：

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
# 若用集群内 PG：kubectl apply -f k8s/postgres.yaml
```

### 5.5 配置 Ingress

编辑 `k8s/ingress.yaml`，将 `host` 改为实际域名或内网域名，按需配置 TLS，然后：

```bash
kubectl apply -f k8s/ingress.yaml
```

### 5.6 部署顺序小结

| 顺序 | 资源 | 说明 |
|------|------|------|
| 1 | namespace.yaml | 命名空间 report-ai |
| 2 | secret.yaml | 从 secret.example.yaml 复制并填写，含 DATABASE_URL |
| 3 | configmap.yaml | 非敏感配置 |
| 4 | postgres.yaml | 可选，仅集群内 PG 时使用 |
| 5 | backend-deployment + backend-service | 后端应用 |
| 6 | frontend-deployment + frontend-service | 前端应用 |
| 7 | ingress.yaml | 对外访问入口 |

---

## 六、验证

1. **Pod 与库表**
   ```bash
   kubectl -n report-ai get pods,svc
   kubectl -n report-ai logs -l component=backend -f
   ```
   日志中应无数据库连接错误；首次启动后 PostgreSQL 中应自动存在所需表。

2. **健康检查**
   - 浏览器访问：`https://你的域名/api/v1/system/health`
   - 应返回 `status: ok`，以及 `vllm_status`、`ocr_status` 等。
   - **说明**：若未配置或不可达 `VLLM_BASE_URL`，`vllm_status` 为 `disconnected` 属预期，此时 AI 解读会失败，仅适合演示环境。

3. **前端**
   - 访问：`https://你的域名/`
   - 能打开首页、患者搜索（mock 模式下可用 100001/100002/100003）、报告解读即视为部署成功。

---

## 七、持久化与存储

- **后端**：使用 PVC `report-ai-backend-data`、`report-ai-backend-uploads`（数据与上传目录）。使用 PostgreSQL 时，业务数据在库中，PVC 主要供上传文件等。
- **PostgreSQL（集群内）**：使用 PVC `report-ai-postgres-data`，建议按需调整容量并做备份策略。

---

## 八、镜像与资源

- 若镜像在私有仓库，在 `backend-deployment.yaml` 与 `frontend-deployment.yaml` 中修改 `image` 为完整地址，并配置 `imagePullSecrets`。
- 资源 requests/limits 已给出默认值，可按集群规模调整。

---

## 九、普通服务器部署（Docker Compose）

不采用 K8s 时，可使用 Docker Compose。**默认已包含 PostgreSQL，后端启动时自动建表。**

1. 在项目根目录复制 `.env.example` 为 `.env` 并修改（与 `docker-compose.yml` 同目录），设置：
   - `VLLM_BASE_URL`：安诊儿推理服务地址（**本次实施为 sglang 部署**）
   - `OCR_SERVICE_URL`：OCR 服务地址（可选）
   - `HOSPITAL_NAME`：医院名称
   - `POSTGRES_PASSWORD`：PostgreSQL 密码（默认 postgres）
   - 对接 LIS 时：`LIS_ADAPTER=winning`、`LIS_USE_ASMX=true`、`LIS_API_BASE_URL=卫宁 ASMX 地址`
2. 执行：`docker-compose up -d`。
3. 访问：`http://服务器IP:80`。
4. 使用外部 PostgreSQL 时：在 `.env` 中设置 `DATABASE_URL=postgresql+asyncpg://用户:密码@主机:5432/库名`，并修改 `docker-compose.yml` 中 backend 的 `depends_on`，去掉对 `postgres` 的依赖。

---

## 十、故障排查

| 现象 | 建议 |
|------|------|
| Backend Pod 启动失败 | 查看日志：`kubectl -n report-ai logs -l component=backend`；检查 Secret 中 DATABASE_URL 是否正确、PostgreSQL 是否可达。 |
| 健康检查报 vllm/ocr disconnected | 未配置推理服务时 `vllm_status: disconnected` 属预期；若已配置，检查 ConfigMap 中 VLLM_BASE_URL、OCR_SERVICE_URL 是否在集群或本机可访问。 |
| 表不存在 | 确认使用 PostgreSQL 且 DATABASE_URL 正确；重启 backend 让 init_db 再次执行。 |
| 启用 MSSQL 时构建/运行报错 | 可能需在 Dockerfile 或基础镜像中安装 pymssql 依赖（如 freetds 等系统库），参见《实施手册》中 MSSQL 与 pymssql 说明。 |
| Ingress 404 | 确认 Ingress Controller 已安装，host 与 path 配置正确。 |
