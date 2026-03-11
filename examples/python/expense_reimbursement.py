#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DocFlow 费用报销场景示例
完整演示从零开始的业务流程：
  1. 创建工作空间
  2. 创建文件类别（含样本文件和字段配置）
  3. 上传待分类抽取的文件
  4. 轮询获取处理结果，展示分类与抽取结果

依赖：
  pip install requests

使用前请先填写下方配置项。
"""

import json
import os
import time

import requests

# ============================================================
# 配置项 — 请替换为您的实际值
# ============================================================
APP_ID = "your-app-id"           # TextIn 控制台中的 x-ti-app-id
SECRET_CODE = "your-secret-code" # TextIn 控制台中的 x-ti-secret-code
ENTERPRISE_ID = 0                # 企业组织 ID，可在 TextIn 控制台「账号与开发者信息」中查看

BASE_URL = "https://docflow.textin.com"

# 样本文件目录（相对本脚本的路径，已内置于 examples/sample_files/费用报销/）
SAMPLE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "sample_files", "费用报销"
)

# ============================================================
# 辅助函数
# ============================================================
def _headers():
    return {
        "x-ti-app-id": APP_ID,
        "x-ti-secret-code": SECRET_CODE,
    }


def _check(resp: requests.Response, action: str) -> dict:
    """校验响应状态，返回解析后的 JSON；失败时抛出 RuntimeError。"""
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"{action} 失败（code={data.get('code')}）: {data}")
    return data


def _mime(file_path: str) -> str:
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
# ============================================================
def create_workspace(name: str, description: str = "") -> str:
    """创建工作空间，返回 workspace_id。"""
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/workspace/create"
    payload = {
        "name": name,
        "description": description,
        "enterprise_id": ENTERPRISE_ID,
        "auth_scope": 0,   # 0: 仅自己可见；1: 企业成员可见
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, "创建工作空间")
    workspace_id = data["result"]["workspace_id"]
    print(f"[步骤1] 工作空间创建成功  workspace_id={workspace_id}")
    return workspace_id


# ============================================================
# 步骤 2：创建文件类别（含样本文件和字段配置）
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
        sample_file_path: 样本文件路径（至少 1 个）
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
            ("extract_model",   (None, "llm")),
            ("category_prompt", (None, category_prompt)),
            # fields 以 JSON 字符串形式传递
            ("fields",          (None, json.dumps(fields, ensure_ascii=False))),
            # 样本文件（可重复此项以传多个样本）
            ("sample_files",    (os.path.basename(sample_file_path), f, mime)),
        ]
        resp = requests.post(url, files=form_data, headers=_headers(), timeout=60)

    data = _check(resp, f"创建文件类别[{name}]")
    category_id = data["result"]["category_id"]
    print(f"[步骤2] 文件类别创建成功  name={name}  category_id={category_id}")
    return category_id


# ============================================================
# 步骤 2b：在已有类别中追加字段（可选）
# ============================================================
def add_category_field(
    workspace_id: str,
    category_id: str,
    field_name: str,
    table_id: str = None,
) -> str:
    """
    在已有类别中追加一个字段。

    Args:
        table_id: 若要创建「表格字段」，先通过 listCategoryFields 获取 table_id 后传入；
                  不传则创建普通字段。

    Returns:
        field_id
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/fields/add"
    payload = {
        "workspace_id": workspace_id,
        "category_id":  category_id,
        "name":         field_name,
    }
    if table_id:
        payload["table_id"] = table_id

    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    data = _check(resp, f"追加字段[{field_name}]")
    field_id = data["result"]["field_id"]
    print(f"  追加字段成功  name={field_name}  field_id={field_id}")
    return field_id


# ============================================================
# 步骤 3：上传待处理文件
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
# 步骤 4：轮询等待处理结果
# ============================================================
def wait_for_result(
    workspace_id: str,
    batch_number: str,
    timeout: int = 120,
    interval: int = 3,
) -> dict:
    """
    轮询直至文件识别完成，返回文件结果对象。

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


# ============================================================
# 展示分类与抽取结果
# ============================================================
def display_result(file_result: dict):
    """格式化输出文件的分类结果和字段抽取结果。"""
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

    # 表格行（items 为 行×列 二维数组，由系统自动识别）
    items = data.get("items") or []
    if items:
        print("\n── 表格行数据 ────────────────────────")
        for row_idx, row in enumerate(items, start=1):
            cells = "  |  ".join(
                f"{c.get('key')}={c.get('value', '')}" for c in row
            )
            print(f"  第{row_idx}行: {cells}")

    # 配置表格（tables，含手动配置的表格字段）
    tables = data.get("tables") or []
    for table in tables:
        tname = table.get("tableName", "")
        t_items = table.get("items") or []
        if t_items:
            print(f"\n── 表格[{tname}] ──────────────────────")
            for row_idx, row in enumerate(t_items, start=1):
                cells = "  |  ".join(
                    f"{c.get('key')}={c.get('value', '')}" for c in row
                )
                print(f"  第{row_idx}行: {cells}")


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("  DocFlow 费用报销场景示例")
    print("=" * 60)

    # ----------------------------------------------------------
    # 步骤 1：创建工作空间
    # ----------------------------------------------------------
    workspace_id = create_workspace(
        name="费用报销",
        description="费用报销单据自动化处理空间",
    )

    # ----------------------------------------------------------
    # 步骤 2：创建文件类别（含样本和字段）
    # ----------------------------------------------------------

    # 2.1 报销申请单
    baoxiao_id = create_category(
        workspace_id=workspace_id,
        name="报销申请单",
        sample_file_path=os.path.join(SAMPLE_DIR, "报销申请单.XLS"),
        fields=[
            {"name": "申请人"},
            {"name": "出差目的"},
            {"name": "报销期间"},
            {"name": "目的地"},
            {"name": "费用发生日期"},
            {"name": "费用项目"},
            {"name": "差旅费金额"},
            {"name": "税率"},
            {"name": "冲借款金额"},
            {"name": "申请付款金额"},
            {"name": "备注"},
            {"name": "税额"},
        ],
        category_prompt="",
    )

    # 2.2 酒店水单（普通字段 + 消费明细表格字段）
    hotel_id = create_category(
        workspace_id=workspace_id,
        name="酒店水单",
        sample_file_path=os.path.join(SAMPLE_DIR, "酒店水单.png"),
        fields=[
            {"name": "入住日期"},
            {"name": "离店日期"},
            {"name": "总金额"},
        ],
        category_prompt="",
    )
    # 追加表格字段
    # 说明：如需将以下字段挂载到特定表格下，先调用
    #   GET /category/fields/list 取得 table_id，再传入 table_id 参数。
    for field_name in ["日期", "费用类型", "金额", "备注"]:
        add_category_field(workspace_id, hotel_id, field_name, -1)

    # 2.3 支付记录
    payment_id = create_category(
        workspace_id=workspace_id,
        name="支付记录",
        sample_file_path=os.path.join(SAMPLE_DIR, "支付记录.png"),
        fields=[
            {"name": "交易流水号"},
            {"name": "交易授权码"},
            {"name": "付款卡种"},
            {"name": "收款方户名"},
            {"name": "付款方户名"},
            {"name": "交易时间"},
            {"name": "备注"},
            {"name": "收款方账户"},
            {"name": "收款方银行"},
            {"name": "交易金额"},
            {"name": "交易描述"},
            {"name": "付款银行"},
            {"name": "币种"},
            {"name": "交易账号/支付方式"},
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
        os.path.join(SAMPLE_DIR, "报销申请单.XLS"),
        os.path.join(SAMPLE_DIR, "酒店水单.png"),
        os.path.join(SAMPLE_DIR, "支付记录.png"),
    ]
    batch_numbers = [upload_file(workspace_id, p) for p in upload_targets]

    # ----------------------------------------------------------
    # 步骤 4：轮询获取结果并展示
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

    print("\n" + "=" * 60)
    print("  示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
