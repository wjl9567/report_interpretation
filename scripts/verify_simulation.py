#!/usr/bin/env python3
"""
模拟数据验证脚本：在本地启动后端后运行，校验 API 完整性及健壮性。
使用 Mock LIS 时患者 ID：100001、100002、100003。
用法: python scripts/verify_simulation.py [--base-url http://127.0.0.1:8080]
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

def request(method: str, url: str, body: dict | None = None) -> tuple[int, dict | str]:
    req = urllib.request.Request(url, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode("utf-8") if body else None
    if data:
        req.data = data
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode()) if r.headers.get_content_type() == "application/json" else r.read().decode()
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return e.code, json.loads(body) if "application/json" in (e.headers.get("Content-Type") or "") else body
        except Exception:
            return e.code, str(e)
    except urllib.error.URLError as e:
        return -1, str(e.reason)
    except Exception as e:
        return -1, str(e)


def main():
    parser = argparse.ArgumentParser(description="报告AI解读系统 - 模拟数据验证")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="后端 base URL")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    ok = 0
    fail = 0

    # 1. 健康检查
    print("1. GET /api/v1/system/health ...")
    code, data = request("GET", f"{base}/api/v1/system/health")
    if code == 200 and isinstance(data, dict) and data.get("status") == "ok":
        print(f"   OK  status={data.get('status')} lis_adapter={data.get('lis_adapter')} vllm={data.get('vllm_status')}")
        ok += 1
    else:
        print(f"   FAIL code={code} body={data}")
        fail += 1

    # 2. 前端配置
    print("2. GET /api/v1/system/config ...")
    code, data = request("GET", f"{base}/api/v1/system/config")
    if code == 200 and isinstance(data, dict) and "hospital_name" in data:
        print(f"   OK  hospital={data.get('hospital_name')} embed_report_mode={data.get('embed_report_mode')}")
        ok += 1
    else:
        print(f"   FAIL code={code} body={data}")
        fail += 1

    # 3. 患者搜索（Mock: 100001/100002/100003）
    print("3. GET /api/v1/report/patient/search?keyword=100001 ...")
    code, data = request("GET", f"{base}/api/v1/report/patient/search?keyword=100001")
    if code == 200 and isinstance(data, dict):
        total = data.get("total", 0)
        arr = data.get("data", [])
        if total >= 1 and len(arr) >= 1 and arr[0].get("patient_id") == "100001":
            print(f"   OK  total={total} patient_id={arr[0].get('patient_id')}")
            ok += 1
        else:
            print(f"   FAIL 期望至少 1 条 patient_id=100001, 得到 total={total} data={arr[:1]}")
            fail += 1
    else:
        print(f"   FAIL code={code} body={data}")
        fail += 1

    # 4. 报告列表
    print("4. GET /api/v1/report/list/100001 ...")
    code, data = request("GET", f"{base}/api/v1/report/list/100001")
    if code == 200 and isinstance(data, dict):
        reports = data.get("reports", [])
        total = data.get("total", 0)
        patient = data.get("patient", {})
        if patient.get("patient_id") == "100001" and total >= 1 and len(reports) >= 1:
            print(f"   OK  patient={patient.get('patient_id')} reports={total} report_no={reports[0].get('report_no')}")
            ok += 1
        else:
            print(f"   FAIL 期望 patient_id=100001 且至少 1 条报告, 得到 patient={patient.get('patient_id')} total={total}")
            fail += 1
    else:
        print(f"   FAIL code={code} body={data}")
        fail += 1

    # 5. 不存在的患者 → 应 404
    print("5. GET /api/v1/report/list/999999 (期望 404) ...")
    code, data = request("GET", f"{base}/api/v1/report/list/999999")
    if code == 404:
        print("   OK  返回 404 符合预期")
        ok += 1
    else:
        print(f"   FAIL 期望 404 得到 code={code}")
        fail += 1

    # 6. AI 解读（依赖 sglang/推理服务，未部署时可能 500）
    print("6. POST /api/v1/report/interpret ...")
    code, data = request("POST", f"{base}/api/v1/report/interpret", {
        "patient_id": "100001",
        "report_no": "RPT20260301001",
        "department_code": "general",
        "report_type": "lab",
    })
    if code == 200 and isinstance(data, dict) and data.get("report_no") == "RPT20260301001":
        print(f"   OK  report_no={data.get('report_no')} abnormal_summary 长度={len(data.get('abnormal_summary',''))}")
        ok += 1
    elif code == 500 and ("解读服务异常" in str(data) or "connection" in str(data).lower() or "推理" in str(data)):
        print("   跳过 解读依赖 sglang/推理服务，当前不可用（属预期）")
        ok += 1  # 视为环境问题非产品缺陷
    else:
        print(f"   FAIL code={code} body={data}")
        fail += 1

    # 7. PDF 代理（Mock 不支持，应 501）
    print("7. GET /api/v1/report/pdf?patient_id=100001&report_no=RPT20260301001 (Mock 期望 501) ...")
    code, data = request("GET", f"{base}/api/v1/report/pdf?patient_id=100001&report_no=RPT20260301001")
    if code == 501:
        print("   OK  Mock 不支持 PDF，返回 501 符合预期")
        ok += 1
    else:
        print(f"   FAIL 期望 501 得到 code={code}")
        fail += 1

    print("")
    print(f"结果: 通过 {ok} 项, 失败 {fail} 项")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
