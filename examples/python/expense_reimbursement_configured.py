#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DocFlow 费用报销场景示例（已完成配置版）

适用于工作空间、文件类别、审核规则库均已配置完毕的场景。
流程：
  1. 上传待处理文件
  2. 轮询获取抽取结果，展示分类与字段抽取结果
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
    "..", "sample_files", "expense_reimbursement"
)

# ============================================================
# 工具辅助函数
# 以下函数不直接对应某个 API 端点，而是提供公共的 HTTP 头、
# 响应校验、MIME 类型推断等基础能力，供各 API 调用函数复用。
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
        ".xls":  "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pdf":  "application/pdf",
    }.get(ext, "application/octet-stream")


# ============================================================
# 批量追加字段
# REST API: POST /api/app-api/sip/platform/v2/category/fields/batch_add
# ============================================================

def batch_add_category_fields(
    workspace_id: str,
    category_id: str,
    fields: list,
    table_id: str = None,
) -> list:
    """
    在已有类别中批量追加字段。

    Args:
        fields:   字段列表，格式为 [{"name": "字段名"}, ...]
        table_id: 若要创建「表格字段」，先通过 category/fields/list 获取
                  table_id 后传入；不传则创建普通字段。

    Returns:
        field_ids 列表
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/fields/batch_add"
    payload = {
        "workspace_id": workspace_id,
        "category_id":  category_id,
        "fields":       fields,
    }
    if table_id is not None:
        payload["table_id"] = str(table_id)
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, "批量追加字段")
    result = data["result"]
    field_ids = [item["field_id"] for item in result]
    print(f"  批量追加字段成功  count={len(fields)}  field_ids={field_ids}")
    return field_ids


# ============================================================
# 批量更新字段
# REST API: POST /api/app-api/sip/platform/v2/category/fields/batch_update
# ============================================================

def batch_update_category_fields(
    workspace_id: str,
    category_id: str,
    fields: list,
    with_detail: bool = False,
) -> list:
    """
    批量更新已有字段的配置。

    Args:
        fields: 字段更新列表，每项须含 field_id，例如：
                [{"field_id": "123", "name": "新名称", "description": "新描述"}, ...]
        with_detail: 是否返回更新后的完整字段信息

    Returns:
        更新后的字段列表（with_detail=True 时）或 None
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/fields/batch_update"
    payload = {
        "workspace_id": workspace_id,
        "category_id":  category_id,
        "fields":       fields,
        "with_detail":  with_detail,
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, "批量更新字段")
    print(f"  批量更新字段成功  count={len(fields)}")
    return data.get("result")


# ============================================================
# 批量新增表格（支持内嵌字段一站式创建）
# REST API: POST /api/app-api/sip/platform/v2/category/tables/batch_add
# ============================================================

def batch_add_category_tables(
    workspace_id: str,
    category_id: str,
    tables: list,
    with_detail: bool = False,
) -> list:
    """
    批量新增表格，支持在每个表格中内嵌 fields 一站式创建表格字段。

    Args:
        tables: 表格列表，例如：
                [{"name": "明细表", "fields": [{"name": "品名"}, {"name": "数量"}]}, ...]
        with_detail: 是否返回完整详情（含字段列表）

    Returns:
        创建结果列表
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/tables/batch_add"
    payload = {
        "workspace_id": workspace_id,
        "category_id":  category_id,
        "tables":       tables,
        "with_detail":  with_detail,
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, "批量新增表格")
    result = data["result"]
    table_ids = [item["table_id"] for item in result]
    print(f"  批量新增表格成功  count={len(tables)}  table_ids={table_ids}")
    return result


# ============================================================
# 批量更新表格
# REST API: POST /api/app-api/sip/platform/v2/category/tables/batch_update
# ============================================================

def batch_update_category_tables(
    workspace_id: str,
    category_id: str,
    tables: list,
    with_detail: bool = False,
) -> list:
    """
    批量更新表格配置。

    Args:
        tables: 表格更新列表，每项须含 table_id，例如：
                [{"table_id": "123", "name": "新表格名", "prompt": "新提示词"}, ...]
        with_detail: 是否返回更新后的完整信息

    Returns:
        更新后的表格列表（with_detail=True 时）或 None
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/tables/batch_update"
    payload = {
        "workspace_id": workspace_id,
        "category_id":  category_id,
        "tables":       tables,
        "with_detail":  with_detail,
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, "批量更新表格")
    print(f"  批量更新表格成功  count={len(tables)}")
    return data.get("result")


# ============================================================
# 批量上传样本
# REST API: POST /api/app-api/sip/platform/v2/category/sample/batch_upload
# ============================================================

def batch_upload_category_samples(
    workspace_id: str,
    category_id: str,
    file_paths: list,
) -> list:
    """
    为指定类别批量上传样本文件（最多 20 个）。

    Args:
        file_paths: 样本文件路径列表

    Returns:
        上传结果（含 sample_id 列表）
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/sample/batch_upload"
    files = []
    for path in file_paths:
        files.append(("files", (os.path.basename(path), open(path, "rb"), _mime(path))))
    form_data = [
        ("workspace_id", (None, workspace_id)),
        ("category_id",  (None, category_id)),
    ]
    resp = requests.post(url, files=form_data + files, headers=_headers(), timeout=120)
    # 关闭文件句柄
    for _, (_, fh, _) in files:
        fh.close()
    data = _check(resp, "批量上传样本")
    result = data.get("result", {})
    print(f"  批量上传样本成功  count={len(file_paths)}")
    return result


# ============================================================
# 批量下载样本（ZIP）
# REST API: POST /api/app-api/sip/platform/v2/category/sample/batch_download
# ============================================================

def batch_download_category_samples(
    workspace_id: str,
    category_id: str,
    sample_ids: list = None,
    save_path: str = "samples.zip",
) -> str:
    """
    批量下载样本文件，打包为 ZIP。不传 sample_ids 时下载全部样本。

    Args:
        sample_ids: 要下载的样本 ID 列表（可选，不传则下载全部）
        save_path:  ZIP 保存路径

    Returns:
        保存路径
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/sample/batch_download"
    payload = {
        "workspace_id": workspace_id,
        "category_id":  category_id,
    }
    if sample_ids:
        payload["sample_ids"] = sample_ids
    resp = requests.post(url, json=payload, headers=_headers(), timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"批量下载样本失败: HTTP {resp.status_code}")
    with open(save_path, "wb") as f:
        f.write(resp.content)
    print(f"  批量下载样本成功  save_path={save_path}  size={len(resp.content)} bytes")
    return save_path


def display_result(file_result: dict):
    """格式化输出文件的分类结果和字段抽取结果（工具辅助函数）。"""
    print("\n" + "=" * 60)
    print(f"文件名   : {file_result.get('name')}")
    print(f"分类结果 : {file_result.get('category') or '未分类'}")
    data = file_result.get("data") or {}
    # 普通字段
    fields = data.get("fields") or []
    if fields:
        print("\n── 普通字段 ──────────────────────────")
        for f in fields:
            print(f"  {f.get('key', ''):<20s}: {f.get('value', '')}")
    # 表格行（items 为行×列二维数组，由系统自动识别）
    items = data.get("items") or []
    if items:
        print("\n── 表格行数据 ────────────────────────")
        for row_idx, row in enumerate(items, start=1):
            cells = "  |  ".join(f"{c.get('key')}={c.get('value', '')}" for c in row)
            print(f"  第{row_idx}行: {cells}")
    # 配置表格（tables，含手动配置的表格字段）
    tables = data.get("tables") or []
    for table in tables:
        tname = table.get("tableName", "")
        t_items = table.get("items") or []
        if t_items:
            print(f"\n── 表格[{tname}] ──────────────────────")
            for row_idx, row in enumerate(t_items, start=1):
                cells = "  |  ".join(f"{c.get('key')}={c.get('value', '')}" for c in row)
                print(f"  第{row_idx}行: {cells}")


def display_review_result(review_result: dict):
    """格式化输出审核任务的结论和各规则审核结果（工具辅助函数）。"""
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
# 步骤 1（替代）：同步上传文件（上传即返回抽取结果，无需轮询）
# REST API: POST /api/app-api/sip/platform/v2/file/upload/sync
# ============================================================

def upload_file_sync(workspace_id: str, file_path: str) -> dict:
    """
    同步上传文件至指定工作空间，等待处理完成后直接返回抽取结果。

    与异步 upload + 轮询 fetch 的效果相同，但无需轮询，适合对接简单或文件量少的场景。
    返回结构与 file/fetch 一致（含 task_id、category、data 等字段）。
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/file/upload/sync"
    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            params={"workspace_id": workspace_id},
            files={"file": (os.path.basename(file_path), f, _mime(file_path))},
            headers=_headers(),
            timeout=300,
        )
    data = _check(resp, f"同步上传文件[{os.path.basename(file_path)}]")
    files = data.get("result", {}).get("files", [])
    if not files:
        raise RuntimeError(f"同步上传未返回文件结果: {data}")
    file_result = files[0]
    print(f"[同步上传] 处理完成  name={os.path.basename(file_path)}"
          f"  category={file_result.get('category', '未分类')}")
    return file_result


# ============================================================
# 步骤 2：轮询等待抽取结果
# REST API: GET /api/app-api/sip/platform/v2/file/fetch（封装了轮询逻辑）
# ============================================================

def wait_for_result(
    workspace_id: str,
    batch_number: str,
    timeout: int = 120,
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
# REST API: POST /api/app-api/sip/platform/v2/review/task/result（封装了轮询逻辑）
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
    print("  DocFlow 费用报销场景示例（已完成配置版）")
    print("=" * 60)
    print(f"工作空间: {WORKSPACE_ID}")
    print(f"规则库:   {REPO_ID}")

    # ----------------------------------------------------------
    # 步骤 1：上传待处理文件
    # ----------------------------------------------------------
    print("\n开始上传待处理文件...")
    upload_targets = [
        os.path.join(FILES_DIR, "sample_expense_form.xls"),
        os.path.join(FILES_DIR, "sample_hotel_receipt.png"),
        os.path.join(FILES_DIR, "sample_payment_record.pdf"),
    ]
    batch_numbers = [upload_file(WORKSPACE_ID, p) for p in upload_targets]

    # ----------------------------------------------------------
    # 步骤 2：轮询获取抽取结果并展示
    # ----------------------------------------------------------
    print("\n开始获取处理结果...")
    raw_results = []
    for batch_number in batch_numbers:
        result = wait_for_result(WORKSPACE_ID, batch_number)
        raw_results.append(result)
        display_result(result)

    # ----------------------------------------------------------
    # 步骤 3：提交审核任务
    # ----------------------------------------------------------
    print("\n开始审核...")
    task_name = f"费用报销审核_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    extract_task_ids = [r.get("task_id") for r in raw_results if r.get("task_id")]
    review_task_id = submit_review_task(WORKSPACE_ID, task_name, REPO_ID, extract_task_ids)

    # ----------------------------------------------------------
    # 步骤 4：轮询获取审核结果并展示
    # ----------------------------------------------------------
    review_result = wait_for_review(WORKSPACE_ID, review_task_id)
    display_review_result(review_result)



if __name__ == "__main__":
    main()
