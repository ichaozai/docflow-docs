#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DocFlow 合同审核场景示例（已完成配置版）

适用于工作空间、文件类别、审核规则库均已配置完毕的场景。
流程：
  1. 上传待审核合同文件
  2. 轮询获取抽取结果，展示字段抽取结果
  3. 提交审核任务
  4. 轮询获取审核结果，展示审核结论

依赖：
  pip install requests

使用前请先填写下方配置项。
"""

import os
import time
from datetime import datetime

import requests

# ============================================================
# 配置项 — 请替换为您的实际值
# ============================================================
APP_ID        = "your-app-id"        # TextIn 控制台中的 x-ti-app-id
SECRET_CODE   = "your-secret-code"   # TextIn 控制台中的 x-ti-secret-code

WORKSPACE_ID = "your-workspace-id"  # 已创建的工作空间 ID
REPO_ID      = "your-repo-id"       # 已配置的审核规则库 ID

BASE_URL = "https://docflow.textin.com"

# 待处理文件目录（默认指向内置示例文件，可替换为您自己的文件路径）
FILES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "sample_files", "contract_review"
)

# ============================================================
# 工具辅助函数
# ============================================================

def _headers() -> dict:
    return {
        "x-ti-app-id":      APP_ID,
        "x-ti-secret-code": SECRET_CODE,
    }


def _check(resp: requests.Response, action: str) -> dict:
    """校验响应状态，返回解析后的 JSON；失败时抛出 RuntimeError。"""
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"{action} 失败（code={data.get('code')}）: {data}")
    return data


def _mime(file_path: str) -> str:
    """根据文件扩展名返回 MIME 类型。"""
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "application/octet-stream")


def display_result(file_result: dict):
    """格式化输出文件的分类结果和字段抽取结果。"""
    print("\n" + "=" * 60)
    print(f"文件名   : {file_result.get('name')}")
    print(f"分类结果 : {file_result.get('category') or '未分类'}")
    data = file_result.get("data") or {}
    fields = data.get("fields") or []
    if fields:
        print("\n── 基本信息字段 ────────────────────────")
        for f in fields:
            val = f.get('value', '')
            display_val = (val[:80] + "...") if len(str(val)) > 80 else val
            print(f"  {f.get('key', ''):<25s}: {display_val}")


def display_review_result(review_result: dict):
    """格式化输出审核任务的结论和各规则审核结果。"""
    STATUS_MAP = {
        0: "未审核", 1: "审核通过", 2: "审核失败",
        3: "审核中", 4: "审核不通过", 5: "识别中",
        6: "排队中", 7: "识别失败",
    }
    RISK_MAP = {10: "高风险", 20: "中风险", 30: "低风险"}

    stats = review_result.get("statistics", {})
    print("\n" + "=" * 60)
    print(f"审核任务状态  : {STATUS_MAP.get(review_result.get('status'), '未知')}")
    print(f"规则通过数    : {stats.get('pass_count', 0)}")
    print(f"规则不通过数  : {stats.get('failure_count', 0)}")

    for group in review_result.get("groups", []):
        print(f"\n── 规则组：{group.get('group_name')} ───────────────────")
        for rt in group.get("review_tasks", []):
            result_text = STATUS_MAP.get(rt.get("review_result"), "未知")
            risk_text   = RISK_MAP.get(rt.get("risk_level"), "未知")
            icon = "✓" if rt.get("review_result") == 1 else "✗"
            print(f"  {icon} [{risk_text}] {rt.get('rule_name')}: {result_text}")
            reasoning = rt.get("reasoning", "")
            if reasoning:
                print(f"    依据: {reasoning[:100]}{'...' if len(reasoning) > 100 else ''}")


# ============================================================
# 步骤 1：上传待处理文件
# REST API: POST /api/app-api/sip/platform/v2/file/upload
# ============================================================

def upload_file(workspace_id: str, file_path: str) -> str:
    """上传待处理文件至工作空间，返回 batch_number。"""
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/file/upload"
    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            params={"workspace_id": workspace_id},
            files={"file": (os.path.basename(file_path), f, _mime(file_path))},
            headers=_headers(),
            timeout=60,
        )
    batch_number = _check(resp, "上传文件")["result"]["batch_number"]
    print(f"[步骤1] 文件上传成功  name={os.path.basename(file_path)}"
          f"  batch_number={batch_number}")
    return batch_number


# ============================================================
# 步骤 2：轮询等待抽取结果
# REST API: GET /api/app-api/sip/platform/v2/file/fetch
# ============================================================

def wait_for_result(
    workspace_id: str,
    batch_number: str,
    timeout: int = 180,
    interval: int = 3,
) -> dict:
    """
    轮询直至文件识别完成，返回文件结果对象（含 task_id）。

    recognition_status: 0=待识别, 1=成功, 2=失败
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/file/fetch"
    params = {"workspace_id": workspace_id, "batch_number": batch_number}
    deadline = time.time() + timeout
    print(f"[步骤2] 等待处理结果（batch_number={batch_number}）...", end="", flush=True)
    while time.time() < deadline:
        resp = requests.get(url, params=params, headers=_headers(), timeout=30)
        data = _check(resp, "获取处理结果")
        files = data.get("result", {}).get("files", [])
        if files:
            status = files[0].get("recognition_status")
            if status == 1:
                print(" 完成")
                return files[0]
            elif status == 2:
                raise RuntimeError(f"文件处理失败: {files[0].get('failure_causes')}")
        print(".", end="", flush=True)
        time.sleep(interval)
    raise TimeoutError(f"等待处理结果超时（{timeout}s）")


# ============================================================
# 步骤 3：提交审核任务
# REST API: POST /api/app-api/sip/platform/v2/review/task/submit
# ============================================================

def submit_review_task(
    workspace_id: str,
    name: str,
    repo_id: str,
    extract_task_ids: list,
) -> str:
    """提交审核任务，返回审核任务 task_id。"""
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/review/task/submit"
    payload = {
        "workspace_id":     workspace_id,
        "name":             name,
        "repo_id":          repo_id,
        "extract_task_ids": extract_task_ids,
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    task_id = _check(resp, "提交审核任务")["result"]["task_id"]
    print(f"[步骤3] 审核任务提交成功  task_id={task_id}")
    return task_id


# ============================================================
# 步骤 4：轮询等待审核结果
# REST API: POST /api/app-api/sip/platform/v2/review/task/result
# ============================================================

def wait_for_review(
    workspace_id: str,
    task_id: str,
    timeout: int = 300,
    interval: int = 5,
) -> dict:
    """
    轮询直至审核任务完成，返回审核结果对象。

    终态: 1=审核通过, 2=审核失败, 4=审核不通过, 7=识别失败
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/review/task/result"
    payload = {"workspace_id": workspace_id, "task_id": task_id}
    deadline = time.time() + timeout
    print(f"[步骤4] 等待审核结果（task_id={task_id}）...", end="", flush=True)
    while time.time() < deadline:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
        data = _check(resp, "获取审核结果")
        result = data.get("result", {})
        if result.get("status") in (1, 2, 4, 7):
            print(" 完成")
            return result
        print(".", end="", flush=True)
        time.sleep(interval)
    raise TimeoutError(f"等待审核结果超时（{timeout}s）")


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  DocFlow 合同审核场景示例（已完成配置版）")
    print("=" * 60)
    print(f"工作空间: {WORKSPACE_ID}")
    print(f"规则库:   {REPO_ID}")

    # ----------------------------------------------------------
    # 步骤 1：上传待处理文件
    # ----------------------------------------------------------
    print("\n开始上传待处理文件...")
    batch_number = upload_file(
        WORKSPACE_ID,
        os.path.join(FILES_DIR, "sample_contract.docx"),
    )

    # ----------------------------------------------------------
    # 步骤 2：轮询获取抽取结果并展示
    # ----------------------------------------------------------
    print("\n开始获取处理结果...")
    file_result = wait_for_result(WORKSPACE_ID, batch_number)
    display_result(file_result)

    # ----------------------------------------------------------
    # 步骤 3：提交审核任务
    # ----------------------------------------------------------
    print("\n开始审核...")
    task_name = f"合同审核_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    extract_task_ids = [file_result.get("task_id")] if file_result.get("task_id") else []
    review_task_id = submit_review_task(WORKSPACE_ID, task_name, REPO_ID, extract_task_ids)

    # ----------------------------------------------------------
    # 步骤 4：轮询获取审核结果并展示
    # ----------------------------------------------------------
    review_result = wait_for_review(WORKSPACE_ID, review_task_id)
    display_review_result(review_result)


if __name__ == "__main__":
    main()
