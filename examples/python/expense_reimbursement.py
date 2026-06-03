#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DocFlow 费用报销场景示例

完整演示从零开始的业务流程：
  1. 创建工作空间
  2. 创建文件类别（含样本文件和字段配置）
  3. 上传待分类抽取的文件
  4. 轮询获取抽取结果，展示分类与字段抽取结果
  5. 配置审核规则库（规则库 → 规则组 → 规则）
  6. 提交审核任务
  7. 轮询获取审核结果，展示审核结论

依赖：
  pip install requests

使用前请先填写下方配置项。
"""

import json
import os
import time
from datetime import datetime

import requests

# ============================================================
# 配置项 — 请替换为您的实际值
# ============================================================
APP_ID        = "your-app-id"      # TextIn 控制台中的 x-ti-app-id
SECRET_CODE   = "your-secret-code" # TextIn 控制台中的 x-ti-secret-code

BASE_URL = "https://docflow.textin.com"

# 样本文件目录（相对本脚本的路径，已内置于 examples/sample_files/expense_reimbursement/）
SAMPLE_DIR = os.path.join(
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
# 步骤 1：创建工作空间
# REST API: POST /api/app-api/sip/platform/v2/workspace/create
# ============================================================

def create_workspace(name: str, description: str = "") -> str:
    """创建工作空间，返回 workspace_id。"""
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/workspace/create"
    payload = {
        "name":        name,
        "description": description,
        "auth_scope":  0,   # 0: 仅自己可见；1: 企业成员可见
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, "创建工作空间")
    workspace_id = data["result"]["workspace_id"]
    print(f"[步骤1] 工作空间创建成功  workspace_id={workspace_id}")
    return workspace_id


# ============================================================
# 步骤 2：创建文件类别（含样本文件和字段配置）
# REST API: POST /api/app-api/sip/platform/v2/category/create
# ============================================================

def create_category(
    workspace_id: str,
    name: str,
    sample_file_path: str,
    fields: list,
    category_prompt: str = "",
) -> str:
    """
    创建文件类别，同时上传样本文件并配置字段。

    Args:
        workspace_id:     工作空间 ID
        name:             类别名称
        sample_file_path: 样本文件路径
        fields:           字段列表，格式为 [{"name": "字段名"}, ...]
        category_prompt:  分类提示词（可选，帮助提升分类准确率）

    Returns:
        category_id
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/create"
    mime = _mime(sample_file_path)
    with open(sample_file_path, "rb") as f:
        form_data = [
            ("workspace_id",    (None, workspace_id)),
            ("name",            (None, name)),
            ("extract_model",   (None, "Model 1")),
            ("category_prompt", (None, category_prompt)),
            ("fields",          (None, json.dumps(fields, ensure_ascii=False))),
            ("sample_files",    (os.path.basename(sample_file_path), f, mime)),
        ]
        resp = requests.post(url, files=form_data, headers=_headers(), timeout=60)
    data = _check(resp, f"创建文件类别[{name}]")
    category_id = data["result"]["category_id"]
    print(f"[步骤2] 文件类别创建成功  name={name}  category_id={category_id}")
    return category_id


# ============================================================
# 步骤 2b：在已有类别中批量追加字段（可选）
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
# 步骤 2c：批量更新字段
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
# 步骤 2d：批量新增表格（支持内嵌字段一站式创建）
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
# 步骤 2e：批量更新表格
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
# 步骤 2f：批量上传样本
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
# 步骤 2g：批量下载样本（ZIP）
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


# ============================================================
# 步骤 3：上传待处理文件
# REST API: POST /api/app-api/sip/platform/v2/file/upload
# ============================================================

def upload_file(workspace_id: str, file_path: str) -> str:
    """上传文件至指定工作空间，返回 batch_number。"""
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/file/upload"
    params = {"workspace_id": workspace_id}
    mime = _mime(file_path)
    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            params=params,
            files={"file": (os.path.basename(file_path), f, mime)},
            headers=_headers(),
            timeout=60,
        )
    data = _check(resp, f"上传文件[{os.path.basename(file_path)}]")
    batch_number = data["result"]["batch_number"]
    print(f"[步骤3] 文件上传成功  name={os.path.basename(file_path)}  batch_number={batch_number}")
    return batch_number


# ============================================================
# 步骤 3（替代）：同步上传文件（上传即返回抽取结果，无需轮询）
# REST API: POST /api/app-api/sip/platform/v2/file/upload/sync
# ============================================================

def upload_file_sync(workspace_id: str, file_path: str) -> dict:
    """
    同步上传文件至指定工作空间，等待处理完成后直接返回抽取结果。

    与异步 upload + 轮询 fetch 的效果相同，但无需轮询，适合对接简单或文件量少的场景。
    返回结构与 file/fetch 一致（含 task_id、category、data 等字段）。
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/file/upload/sync"
    params = {"workspace_id": workspace_id}
    mime = _mime(file_path)
    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            params=params,
            files={"file": (os.path.basename(file_path), f, mime)},
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
# 步骤 4：轮询等待抽取结果
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
    print(f"[步骤4] 等待处理结果（batch_number={batch_number}）...", end="", flush=True)
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


# ============================================================
# 步骤 5：配置审核规则库
# REST API: POST /api/app-api/sip/platform/v2/review/rule_repo/create
#           POST /api/app-api/sip/platform/v2/review/rule_group/create
#           POST /api/app-api/sip/platform/v2/review/rule/create
# ============================================================

def create_rule_repo(workspace_id: str, name: str) -> str:
    """创建审核规则库，返回 repo_id。"""
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/review/rule_repo/create"
    payload = {"workspace_id": workspace_id, "name": name}
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, "创建规则库")
    repo_id = data["result"]["repo_id"]
    print(f"[步骤5] 规则库创建成功  name={name}  repo_id={repo_id}")
    return repo_id


def create_rule_group(workspace_id: str, repo_id: str, name: str) -> str:
    """在规则库下创建规则组，返回 group_id。"""
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/review/rule_group/create"
    payload = {"workspace_id": workspace_id, "repo_id": repo_id, "name": name}
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, f"创建规则组[{name}]")
    group_id = data["result"]["group_id"]
    print(f"  规则组创建成功  name={name}  group_id={group_id}")
    return group_id


def create_rule(
    workspace_id: str,
    repo_id: str,
    group_id: str,
    name: str,
    prompt: str,
    category_ids: list,
    risk_level: int,
) -> str:
    """
    在规则组下创建审核规则，返回 rule_id。

    Args:
        category_ids: 适用分类 ID 列表，规则仅对这些分类的抽取任务生效
        risk_level:   风险等级，10=高风险 / 20=中风险 / 30=低风险
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/review/rule/create"
    payload = {
        "workspace_id": workspace_id,
        "repo_id":      repo_id,
        "group_id":     group_id,
        "name":         name,
        "prompt":       prompt,
        "category_ids": category_ids,
        "risk_level":   risk_level,
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, f"创建规则[{name}]")
    rule_id = data["result"]["rule_id"]
    print(f"    规则创建成功  name={name}  rule_id={rule_id}")
    return rule_id


# ============================================================
# 步骤 6：提交审核任务
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
    data = _check(resp, "提交审核任务")
    task_id = data["result"]["task_id"]
    print(f"[步骤6] 审核任务提交成功  task_id={task_id}")
    return task_id


# ============================================================
# 步骤 7：轮询等待审核结果
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
    print(f"[步骤7] 等待审核结果（task_id={task_id}）...", end="", flush=True)
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
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  DocFlow 费用报销场景示例")
    print("=" * 60)

    # ----------------------------------------------------------
    # 步骤 1：创建工作空间（名称含时间戳，避免重名）
    # ----------------------------------------------------------
    workspace_name = f"费用报销_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    workspace_id = create_workspace(
        name=workspace_name,
        description="费用报销单据自动化处理空间",
    )

    # ----------------------------------------------------------
    # 步骤 2：创建文件类别（含样本和字段）
    # ----------------------------------------------------------

    # 2.1 报销申请单
    baoxiao_id = create_category(
        workspace_id=workspace_id,
        name="报销申请单",
        sample_file_path=os.path.join(SAMPLE_DIR, "sample_expense_form.xls"),
        fields=[
            {"name": "申请人"},     {"name": "出差目的"},   {"name": "报销期间"},
            {"name": "目的地"},     {"name": "费用发生日期"}, {"name": "费用项目"},
            {"name": "差旅费金额"}, {"name": "税率"},        {"name": "冲借款金额"},
            {"name": "申请付款金额"}, {"name": "备注"},      {"name": "税额"},
        ],
        category_prompt="",
    )

    # 2.2 酒店水单（普通字段 + 消费明细表格字段）
    hotel_id = create_category(
        workspace_id=workspace_id,
        name="酒店水单",
        sample_file_path=os.path.join(SAMPLE_DIR, "sample_hotel_receipt.png"),
        fields=[
            {"name": "入住日期"}, {"name": "离店日期"}, {"name": "总金额"},
        ],
        category_prompt="",
    )
    # 批量追加表格字段（传 table_id="-1" 归入默认表格）
    field_ids = batch_add_category_fields(
        workspace_id, hotel_id,
        fields=[{"name": n} for n in ["日期", "费用类型", "金额", "备注"]],
        table_id="-1",
    )

    # 批量更新字段：为刚创建的表格字段补充描述
    batch_update_category_fields(
        workspace_id, hotel_id,
        fields=[
            {"field_id": field_ids[0], "description": "消费日期"},
            {"field_id": field_ids[1], "description": "餐饮/住宿/交通等"},
            {"field_id": field_ids[2], "description": "单笔消费金额"},
            {"field_id": field_ids[3], "description": "备注信息"},
        ],
        with_detail=True,
    )

    # 批量新增表格（含内嵌字段，一站式创建）
    batch_add_category_tables(
        workspace_id, hotel_id,
        tables=[{
            "name": "房费明细",
            "prompt": "抽取每日房费明细",
            "fields": [
                {"name": "日期"},
                {"name": "房型"},
                {"name": "房价"},
            ],
        }],
        with_detail=True,
    )

    # 批量上传额外样本文件
    batch_upload_category_samples(
        workspace_id, hotel_id,
        file_paths=[os.path.join(SAMPLE_DIR, "sample_hotel_receipt.png")],
    )

    # 2.3 支付记录
    payment_id = create_category(
        workspace_id=workspace_id,
        name="支付记录",
        sample_file_path=os.path.join(SAMPLE_DIR, "sample_payment_record.pdf"),
        fields=[
            {"name": "交易流水号"}, {"name": "交易授权码"}, {"name": "付款卡种"},
            {"name": "收款方户名"}, {"name": "付款方户名"}, {"name": "交易时间"},
            {"name": "备注"},       {"name": "收款方账户"}, {"name": "收款方银行"},
            {"name": "交易金额"},   {"name": "交易描述"},   {"name": "付款银行"},
            {"name": "币种"},       {"name": "交易账号/支付方式"},
        ],
        category_prompt="",
    )

    print(f"\n配置完成  workspace_id={workspace_id}")
    print(f"  报销申请单: category_id={baoxiao_id}")
    print(f"  酒店水单:   category_id={hotel_id}")
    print(f"  支付记录:   category_id={payment_id}")

    # ----------------------------------------------------------
    # 步骤 3：上传待处理文件
    # ----------------------------------------------------------
    print("\n开始上传待处理文件...")
    upload_targets = [
        os.path.join(SAMPLE_DIR, "sample_expense_form.xls"),
        os.path.join(SAMPLE_DIR, "sample_hotel_receipt.png"),
        os.path.join(SAMPLE_DIR, "sample_payment_record.pdf"),
    ]
    batch_numbers = [upload_file(workspace_id, p) for p in upload_targets]

    # ----------------------------------------------------------
    # 步骤 4：轮询获取抽取结果并展示
    # ----------------------------------------------------------
    print("\n开始获取处理结果...")
    raw_results = []
    for batch_number in batch_numbers:
        try:
            result = wait_for_result(workspace_id, batch_number)
            display_result(result)
            raw_results.append(result)
        except Exception as exc:
            print(f"  异常: {exc}")

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)
    print(f"\n原始抽取结果已保存至: {output_path}")

    # ----------------------------------------------------------
    # 步骤 5：配置审核规则库
    # ----------------------------------------------------------
    print("\n开始配置审核规则库...")
    repo_id = create_rule_repo(workspace_id, "费用报销审核规则库")

    # 规则组1：报销申请单合规性检查
    group1_id = create_rule_group(workspace_id, repo_id, "报销申请单合规性检查")
    create_rule(workspace_id, repo_id, group1_id,
        "行报销金额校验",
        "行申请付款金额 ≤ 行差旅费金额（含税）- 行冲借款金额，如冲借款金额为空则冲借款金额视为0",
        [baoxiao_id], 10)
    create_rule(workspace_id, repo_id, group1_id,
        "报销总金额校验",
        "申请付款总金额 ≤ Σ行申请付款金额",
        [baoxiao_id], 10)
    create_rule(workspace_id, repo_id, group1_id,
        "报销期间与费用日期匹配",
        "\"费用发生日期\"应在\"报销期间\"所覆盖的日期范围内",
        [baoxiao_id], 20)
    create_rule(workspace_id, repo_id, group1_id,
        "必填字段完整性校验",
        "\"申请人\"、\"费用发生日期\"、\"费用项目\"、\"申请付款金额\"均不为空，任一字段为空则审核不通过",
        [baoxiao_id], 10)

    # 规则组2：差旅费用政策匹配审核
    group2_id = create_rule_group(workspace_id, repo_id, "差旅费用政策匹配审核")
    create_rule(workspace_id, repo_id, group2_id,
        "城市差标匹配",
        "酒店住宿单价≤目的地城市差旅标准：一线城市（北京/上海/广州/深圳）≤800元/晚，省会及计划单列市≤500元/晚，其他城市≤300元/晚",
        [hotel_id], 20)
    create_rule(workspace_id, repo_id, group2_id,
        "酒店明细合计金额校验",
        "酒店水单中所有明细行\"金额\"的合计应等于\"总金额\"",
        [hotel_id], 20)

    # 规则组3：跨文档交叉审核
    group3_id = create_rule_group(workspace_id, repo_id, "跨文档交叉审核")
    create_rule(workspace_id, repo_id, group3_id,
        "跨文档金额匹配",
        "报销申请单的差旅费金额（含税）= 酒店水单的\"总金额\" = 支付记录的\"交易金额\"，允许±0.1元误差",
        [baoxiao_id, hotel_id, payment_id], 10)
    create_rule(workspace_id, repo_id, group3_id,
        "付款人身份与申请人一致性",
        "支付记录的\"付款方户名\"与报销申请单的\"申请人\"应为同一人",
        [baoxiao_id, payment_id], 20)

    # ----------------------------------------------------------
    # 步骤 6：提交审核任务
    # ----------------------------------------------------------
    # 从抽取结果中收集 task_id，传给审核接口
    extract_task_ids = [r.get("task_id") for r in raw_results if r.get("task_id")]
    review_task_id = submit_review_task(
        workspace_id, "费用报销审核", repo_id, extract_task_ids
    )

    # ----------------------------------------------------------
    # 步骤 7：轮询获取审核结果
    # ----------------------------------------------------------
    review_result = wait_for_review(workspace_id, review_task_id)
    display_review_result(review_result)

    print("\n" + "=" * 60)
    print("  示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
