#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DocFlow AP 审单场景示例

完整演示从零开始的业务流程：
  1. 创建工作空间
  2. 创建文件类别（国内票-数电票、采购合同、入库单、验收单）
  3. 上传待审核文件（发票、采购合同、入库单、验收单）
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

# 示例文件目录（相对本脚本的路径）
SAMPLE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "sample_files", "ap_review"
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
        "auth_scope":  0,
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
        category_prompt:  分类提示词（可选）

    Returns:
        category_id
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/create"
    mime = _mime(sample_file_path)
    with open(sample_file_path, "rb") as f:
        form_data = [
            ("workspace_id",    (None, workspace_id)),
            ("name",            (None, name)),
            ("extract_model",   (None, "Acgpt")),
            ("category_prompt", (None, category_prompt)),
            ("fields",          (None, json.dumps(fields, ensure_ascii=False))),
            ("sample_files",    (os.path.basename(sample_file_path), f, mime)),
        ]
        resp = requests.post(url, files=form_data, headers=_headers(), timeout=60)
    data = _check(resp, f"创建文件类别[{name}]")
    category_id = data["result"]["category_id"]
    print(f"[步骤2] 文件类别创建成功  name={name}  category_id={category_id}")
    return category_id


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
        table_id: 若要创建表格字段，传入 table_id（-1 表示默认表格）；
                  不传则创建普通基本信息字段。

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
# REST API: GET /api/app-api/sip/platform/v2/file/fetch
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
    """格式化输出文件的分类结果和字段抽取结果。"""
    print("\n" + "=" * 60)
    print(f"文件名   : {file_result.get('name')}")
    print(f"分类结果 : {file_result.get('category') or '未分类'}")
    data = file_result.get("data") or {}
    fields = data.get("fields") or []
    if fields:
        print("\n── 基本信息字段 ────────────────────────")
        for f in fields:
            print(f"  {f.get('key', ''):<25s}: {f.get('value', '')}")
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
        category_ids: 适用分类 ID 列表
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
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  DocFlow AP 审单场景示例")
    print("=" * 60)

    # ----------------------------------------------------------
    # 步骤 1：创建工作空间
    # ----------------------------------------------------------
    workspace_name = f"AP审单_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    workspace_id = create_workspace(
        name=workspace_name,
        description="AP审单业务自动化处理空间",
    )

    # ----------------------------------------------------------
    # 步骤 2：配置文件类别
    # ----------------------------------------------------------

    # 2.1 国内票-数电票（基本信息字段 + 明细表格字段）
    invoice_id = create_category(
        workspace_id=workspace_id,
        name="国内票-数电票",
        sample_file_path=os.path.join(SAMPLE_DIR, "sample_invoice.pdf"),
        fields=[
            {"name": "发票号码"},           {"name": "开票日期"},
            {"name": "价税合计"},           {"name": "税前金额"},
            {"name": "税额"},               {"name": "销售方名称"},
            {"name": "销售方纳税人识别号"}, {"name": "购买方名称"},
            {"name": "购买方纳税人识别号"}, {"name": "发票备注"},
        ],
        category_prompt="增值税电子发票（数电票），含发票号码、开票日期、购买方、销售方及价税合计等字段",
    )
    # 批量追加明细表格字段
    batch_add_category_fields(
        workspace_id, invoice_id,
        fields=[{"name": n} for n in ["商品名称", "规格型号", "单位", "数量", "单价", "金额", "税率", "税额"]],
        table_id="-1",
    )

    # 2.2 采购合同（基本信息字段 + 表格字段）
    contract_id = create_category(
        workspace_id=workspace_id,
        name="采购合同",
        sample_file_path=os.path.join(SAMPLE_DIR, "sample_contract.pdf"),
        fields=[
            {"name": "编号"},           {"name": "甲方"},           {"name": "乙方"},
            {"name": "签订日期"},       {"name": "合作期间"},       {"name": "支付条款"},
            {"name": "乙方银行账户信息"}, {"name": "开票信息"},     {"name": "违约金条款"},
            {"name": "采购物料/服务数量"}, {"name": "合同类型"},    {"name": "采购金额"},
            {"name": "采购单价"},       {"name": "税率"},           {"name": "乙方税号"},
            {"name": "采购物料/服务"},
        ],
    )
    # 批量追加表格字段（table_id="-1" 表示默认表格）
    contract_field_ids = batch_add_category_fields(
        workspace_id, contract_id,
        fields=[{"name": n} for n in ["产品型号", "产品说明", "单价", "数量", "金额"]],
        table_id="-1",
    )

    # 批量更新字段：为刚创建的表格字段补充描述
    batch_update_category_fields(
        workspace_id, contract_id,
        fields=[
            {"field_id": contract_field_ids[0], "description": "产品的具体型号"},
            {"field_id": contract_field_ids[1], "description": "产品的详细说明"},
            {"field_id": contract_field_ids[2], "description": "产品单价（含税）"},
            {"field_id": contract_field_ids[3], "description": "采购数量"},
            {"field_id": contract_field_ids[4], "description": "行金额小计"},
        ],
        with_detail=True,
    )

    # 批量新增表格（一站式创建表格 + 内嵌字段）
    batch_add_category_tables(
        workspace_id, contract_id,
        tables=[{
            "name": "付款计划",
            "prompt": "抽取合同中的分期付款安排",
            "fields": [
                {"name": "付款节点"},
                {"name": "付款比例"},
                {"name": "付款金额"},
            ],
        }],
        with_detail=True,
    )

    # 批量上传额外样本文件
    batch_upload_category_samples(
        workspace_id, contract_id,
        file_paths=[os.path.join(SAMPLE_DIR, "sample_contract.pdf")],
    )

    # 2.3 入库单（基本信息字段 + 表格字段）
    inbound_id = create_category(
        workspace_id=workspace_id,
        name="入库单",
        sample_file_path=os.path.join(SAMPLE_DIR, "sample_inbound.pdf"),
        fields=[
            {"name": "收货单编号"},     {"name": "收货日期"},       {"name": "对应合同号"},
            {"name": "供应商名称"},     {"name": "仓库／库位"},     {"name": "物流单号"},
            {"name": "入库总金额"},     {"name": "收货结论"},       {"name": "备注"},
            {"name": "仓库收货人"},     {"name": "仓库收货人日期"}, {"name": "质检确认"},
            {"name": "质检确认日期"},   {"name": "供应商送货人"},   {"name": "供应商送货人日期"},
            {"name": "供应商税号"},
        ],
    )
    batch_add_category_fields(
        workspace_id, inbound_id,
        fields=[{"name": n} for n in [
            "收货入库明细-物料编码", "收货入库明细-物料描述", "收货入库明细-单位",
            "收货入库明细-应收",    "收货入库明细-实收",    "收货入库明细-差异",
            "收货入库明细-质检",    "收货入库明细-签收人",
        ]],
        table_id="-1",
    )

    # 2.4 验收单（仅基本信息字段）
    acceptance_id = create_category(
        workspace_id=workspace_id,
        name="验收单",
        sample_file_path=os.path.join(SAMPLE_DIR, "sample_acceptance.pdf"),
        fields=[
            {"name": "项目名称"},   {"name": "合同编号"},   {"name": "甲方单位名称"},
            {"name": "乙方单位名称"}, {"name": "甲方验收人"}, {"name": "乙方施工人"},
            {"name": "交付内容"},   {"name": "验收说明"},   {"name": "验收结论"},
            {"name": "验收数量"},   {"name": "验收日期"},   {"name": "乙方税号"},
        ],
    )

    print(f"\n类别配置完成")
    print(f"  国内票-数电票: category_id={invoice_id}")
    print(f"  采购合同:      category_id={contract_id}")
    print(f"  入库单:        category_id={inbound_id}")
    print(f"  验收单:        category_id={acceptance_id}")

    # ----------------------------------------------------------
    # 步骤 3：上传待处理文件
    # ----------------------------------------------------------
    print("\n开始上传待处理文件...")
    upload_targets = [
        os.path.join(SAMPLE_DIR, "sample_invoice.pdf"),
        os.path.join(SAMPLE_DIR, "sample_contract.pdf"),
        os.path.join(SAMPLE_DIR, "sample_inbound.pdf"),
        os.path.join(SAMPLE_DIR, "sample_acceptance.pdf"),
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

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ap_review_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)
    print(f"\n原始抽取结果已保存至: {output_path}")

    # ----------------------------------------------------------
    # 步骤 5：配置审核规则库
    # ----------------------------------------------------------
    print("\n开始配置审核规则库...")
    repo_id = create_rule_repo(workspace_id, "AP审单场景审核规则库")

    # 规则组1：业务一致性审核
    group1_id = create_rule_group(workspace_id, repo_id, "业务一致性审核")

    create_rule(workspace_id, repo_id, group1_id,
        "供应商一致性",
        "若均存在税号字段：\n"
        "发票【销售方纳税人识别号】= 合同【乙方纳税人识别号】= 入库单【供应商税号】\n"
        "若任一单据无税号：\n"
        "发票【销售方名称】= 合同【乙方名称】= 入库单【供应商名称】",
        [invoice_id, contract_id, inbound_id], 10)

    create_rule(workspace_id, repo_id, group1_id,
        "金额匹配",
        "发票价税合计金额≤采购合同总金额；若合同为框架协议（金额为空或0），则不校验金额浮动。",
        [invoice_id, contract_id], 10)

    create_rule(workspace_id, repo_id, group1_id,
        "数量一致性（入库单维度）",
        "若发票包含商品明细，则发票数量合计 ≤ 入库单实收数量合计。",
        [invoice_id, inbound_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "标的一致性",
        "若采购合同中约定了具体规格型号，采购合同中约定的规格型号与入库单、发票中的规格型号必须完全一致；"
        "当合同未约定具体规格型号时，校验各单据中的标的物描述应指向同一商品或服务；"
        "服务类采购（如咨询、运维、人力外包）的验收单中的服务内容描述与合同约定的服务范围应一致",
        [invoice_id, contract_id, acceptance_id, inbound_id], 30)

    create_rule(workspace_id, repo_id, group1_id,
        "税率一致性",
        "校验发票各行商品的税率是否与采购合同中约定的该商品/服务适用税率一致。"
        "若合同未约定具体税率，则跳过校验。若发票存在多行，要求每一行的税率均与合同约定相符。",
        [invoice_id, contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "验收结论校验",
        "验收单的验收结论必须为{合格，通过，验收通过，同意验收}或类似认可状态。",
        [acceptance_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "数量一致性（验收单维度）",
        "若发票包含商品明细，则发票数量合计 ≤ 验收单中的合格数量合计。"
        "验收单如无明确列明合格数量，则忽视该条审核规则。",
        [invoice_id, acceptance_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "合同关联性",
        "入库单【合同编号】= 采购合同【编号】；验收单【合同编号】= 采购合同【编号】",
        [contract_id, acceptance_id, inbound_id], 20)

    # 规则组2：文档采集与预处理审核
    group2_id = create_rule_group(workspace_id, repo_id, "文档采集与预处理审核")

    create_rule(workspace_id, repo_id, group2_id,
        "信息完整性校验",
        "检查文档是否齐全（入库单、验收单、发票、采购合同），且每一文档的必填字段非空。\n"
        "必填字段清单：\n"
        "采购合同：合同编号、签订日期、合同总金额（框架协议可为空）、甲方名称、乙方名称；\n"
        "发票：发票号码、开票日期、价税合计金额、销售方名称、销售方纳税人识别号、购买方名称、购买方纳税人识别号；\n"
        "入库单：收货日期、对应合同号、物料编码、物料描述、应收、实收、供应商名称；\n"
        "验收单：验收日期、对应合同号（或PO号）、供应商名称、验收结论（合格/不合格）。",
        [invoice_id, contract_id, acceptance_id, inbound_id], 20)

    create_rule(workspace_id, repo_id, group2_id,
        "发票日期合规性",
        "发票【开票日期】≥ 合同【签订日期】",
        [invoice_id, contract_id], 20)

    create_rule(workspace_id, repo_id, group2_id,
        "购买方信息匹配",
        "发票【购买方名称】= 本企业工商登记名称（上海合合信息科技股份有限公司）\n"
        "发票【购买方纳税人识别号】= 本企业税号（91310110791485269J）",
        [invoice_id], 10)

    create_rule(workspace_id, repo_id, group2_id,
        "税率合规性校验",
        "校验发票税率与开票项目的匹配性：货物类应为13%，服务类应为6%，小规模纳税人应为1%或3%。",
        [invoice_id], 20)

    # ----------------------------------------------------------
    # 步骤 6：提交审核任务
    # ----------------------------------------------------------
    extract_task_ids = [r.get("task_id") for r in raw_results if r.get("task_id")]
    review_task_id = submit_review_task(
        workspace_id,
        f"AP审核_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        repo_id,
        extract_task_ids,
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
