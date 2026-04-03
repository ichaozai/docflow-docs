#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DocFlow 合同审核场景示例

完整演示从零开始的业务流程：
  1. 创建工作空间
  2. 创建文件类别（采购合同，含字段配置）
  3. 上传待审核合同文件
  4. 轮询获取抽取结果，展示字段抽取结果
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
ENTERPRISE_ID = 0                  # 企业组织 ID，可在 TextIn 控制台「账号与开发者信息」中查看

BASE_URL = "https://docflow.textin.com"

# 示例文件目录（相对本脚本的路径）
SAMPLE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "sample_files", "合同审核"
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
    if ENTERPRISE_ID:
        payload["enterprise_id"] = ENTERPRISE_ID
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

    合同审核场景使用 Model 2（复杂文档理解），适合合同这类长文档的深度理解和字段抽取。

    Returns:
        category_id
    """
    url = f"{BASE_URL}/api/app-api/sip/platform/v2/category/create"
    mime = _mime(sample_file_path)
    with open(sample_file_path, "rb") as f:
        form_data = [
            ("workspace_id",    (None, workspace_id)),
            ("name",            (None, name)),
            ("extract_model",   (None, "Model 2")),
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
# 步骤 4：轮询等待抽取结果
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

    合同文档通常较长，超时时间设置为 180s。
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
            val = f.get('value', '')
            # 长文本截断显示
            display_val = (val[:80] + "...") if len(str(val)) > 80 else val
            print(f"  {f.get('key', ''):<25s}: {display_val}")


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
    print("  DocFlow 合同审核场景示例")
    print("=" * 60)

    # ----------------------------------------------------------
    # 步骤 1：创建工作空间
    # ----------------------------------------------------------
    workspace_name = f"合同审核_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    workspace_id = create_workspace(
        name=workspace_name,
        description="采购合同智能审核空间",
    )

    # ----------------------------------------------------------
    # 步骤 2：创建文件类别（采购合同）
    # 合同审核场景只有一个文件类别，字段较多，使用 Model 2 进行复杂文档理解。
    # ----------------------------------------------------------
    contract_id = create_category(
        workspace_id=workspace_id,
        name="采购合同",
        sample_file_path=os.path.join(SAMPLE_DIR, "示例_采购合同.docx"),
        fields=[
            {"name": "合同编号"},               {"name": "合同名称"},
            {"name": "签订日期"},               {"name": "生效条件"},
            {"name": "甲方全称"},               {"name": "甲方统一社会信用代码"},
            {"name": "甲方联系方式"},           {"name": "甲方地址"},
            {"name": "乙方全称"},               {"name": "乙方统一社会信用代码"},
            {"name": "乙方联系方式"},           {"name": "乙方地址"},
            {"name": "乙方法定代表人/授权委托人"},
            {"name": "标的名称"},               {"name": "标的规格型号/标准"},
            {"name": "标的技术/质量标准"},      {"name": "标的数量/服务范围"},
            {"name": "含税总金额（大写）"},     {"name": "不含税金额"},
            {"name": "税额"},                   {"name": "税率"},
            {"name": "发票条款"},               {"name": "付款方式"},
            {"name": "付款条件"},               {"name": "付款比例"},
            {"name": "账期"},                   {"name": "收款账户信息"},
            {"name": "履约期限"},               {"name": "履约地点"},
            {"name": "交付/验收标准与流程"},   {"name": "违约责任"},
            {"name": "免责条款"},               {"name": "争议解决方式"},
            {"name": "合同解除与终止条件"},    {"name": "保密条款"},
            {"name": "知识产权声明"},           {"name": "合同份数"},
            {"name": "附件清单"},               {"name": "签约人签字/盖章"},
        ],
    )

    print(f"\n类别配置完成  采购合同: category_id={contract_id}")

    # ----------------------------------------------------------
    # 步骤 3：上传待处理文件
    # ----------------------------------------------------------
    print("\n开始上传待处理文件...")
    batch_number = upload_file(
        workspace_id,
        os.path.join(SAMPLE_DIR, "示例_采购合同.docx"),
    )

    # ----------------------------------------------------------
    # 步骤 4：轮询获取抽取结果并展示
    # ----------------------------------------------------------
    print("\n开始获取处理结果...")
    file_result = wait_for_result(workspace_id, batch_number)
    display_result(file_result)

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contract_review_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(file_result, f, ensure_ascii=False, indent=2)
    print(f"\n原始抽取结果已保存至: {output_path}")

    # ----------------------------------------------------------
    # 步骤 5：配置审核规则库
    # ----------------------------------------------------------
    print("\n开始配置审核规则库...")
    repo_id = create_rule_repo(workspace_id, "合同审核场景规则库")

    # 规则组1：财务条款审核
    group1_id = create_rule_group(workspace_id, repo_id, "财务条款审核")

    create_rule(workspace_id, repo_id, group1_id,
        "连带责任条款",
        "若存在开票方、付款方与签约主体不一致的情形（三方关系），则合同必须明确各方债权债务关系。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "履约保证金条款",
        "若约定履约保证金/质保金，必须明确退还条件、退还时间节点及不予退还的情形。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "滞纳金/违约金合理性",
        "若存在甲方逾期付款或乙方逾期交付的滞纳金/违约金条款，则日费率 ≤ 0.05%。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "验收/交付标准明确性",
        "合同必须明确交付完成的判定标准（如双方签署验收单、开通即交付、开通N天后无异议即交付等）。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "币别一致性",
        "合同全文中涉及金额的币别必须前后一致，若无提及币别信息，则视为一致。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "付款方式明确性",
        "付款方式必须明确，属于以下之一：银行转账、银行承兑汇票、商业承兑汇票、第三方支付。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "付款条件明确性",
        "付款节点需清晰（如【货到验收合格后】【合同签订后】）；付款期限需明确（如【30日内支付】【收到发票后15个工作日】）。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group1_id,
        "税率合理性",
        "税率必须为有效值：6%、9%、13%、1%、3%、免税、0%；税率需与合同标的类型匹配。",
        [contract_id], 10)

    create_rule(workspace_id, repo_id, group1_id,
        "付款比例合计",
        "若合同中存在分阶段付款比例（如预付款、进度款、尾款），则各阶段付款比例合计必须等于 100%。",
        [contract_id], 10)

    create_rule(workspace_id, repo_id, group1_id,
        "产品明细合计与总金额一致性",
        "若合同包含明细行：\n1. 各明细行【单价 x 数量 = 金额】；\n2. 所有明细行金额合计 = 合同总金额（允许±0.01元）。",
        [contract_id], 10)

    create_rule(workspace_id, repo_id, group1_id,
        "金额合规检测",
        "1. 不含税金额 x 税率 = 税额（允许±0.01元尾差）；\n2. 不含税金额 + 税额 = 含税总金额。",
        [contract_id], 10)

    create_rule(workspace_id, repo_id, group1_id,
        "合同金额大小写一致性",
        "若大小写金额均存在：两者必须一致；若仅存在大写金额：校验大写格式是否符合中文金额书写规范（如【壹万贰仟叁佰元整】）",
        [contract_id], 10)

    # 规则组2：法务合规审核
    group2_id = create_rule_group(workspace_id, repo_id, "法务合规审核")

    create_rule(workspace_id, repo_id, group2_id,
        "不可抗力条款",
        "包含不可抗力条款，且定义清晰（如列明不可抗力事件范围、通知时限、责任豁免方式）。",
        [contract_id], 30)

    create_rule(workspace_id, repo_id, group2_id,
        "保密条款完整性",
        "保密信息定义、保密期限、违约责任三项要素齐全。",
        [contract_id], 30)

    create_rule(workspace_id, repo_id, group2_id,
        "知识产权归属",
        "若合同涉及技术开发、委托设计、软件开发等内容，则必须存在知识产权归属条款且归属明确。",
        [contract_id], 30)

    create_rule(workspace_id, repo_id, group2_id,
        "违约金上限合理性",
        "违约金是否设置上限（如不超过合同总金额的20%），过高违约金存在法律风险。",
        [contract_id], 30)

    create_rule(workspace_id, repo_id, group2_id,
        "违约对等性检查",
        "比较甲乙双方的逾期违约金比例。若双方比例差异超过设定阈值（如相差≥50%），则标记提醒。",
        [contract_id], 30)

    create_rule(workspace_id, repo_id, group2_id,
        "合同日期合理性",
        "签订日期 ≤ 生效日期；生效日期 ≤ 到期日期（若有）；生效日期不得早于当前日期。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group2_id,
        "签约主体名称一致性",
        "合同首部、尾部签章处、正文中出现的签约主体名称必须完全一致。",
        [contract_id], 10)

    create_rule(workspace_id, repo_id, group2_id,
        "签约主体信息完整性",
        "甲乙双方以下字段非空：名称、地址、联系方式。",
        [contract_id], 10)

    create_rule(workspace_id, repo_id, group2_id,
        "必备条款完整性",
        "合同必须包含以下条款：\n"
        "1. 主体信息（双方名称、统一社会信用代码）；\n"
        "2. 标的（货物/服务名称）；\n"
        "3. 数量/服务范围；\n"
        "4. 质量（若有）；\n"
        "5. 价款/报酬（含税总金额）；\n"
        "6. 履行期限、地点和方式；\n"
        "7. 违约责任（有明确的违约情形和违约金）；\n"
        "8. 争议解决方式（诉讼或仲裁）。",
        [contract_id], 10)

    # 规则组3：文本质量与一致性审核
    group3_id = create_rule_group(workspace_id, repo_id, "文本质量与一致性审核")

    create_rule(workspace_id, repo_id, group3_id,
        "数字计算校验",
        "1. 单价 x 数量 = 金额（每行）；\n2. 各分项金额合计 = 合同总金额（允许±0.01元尾差）。",
        [contract_id], 30)

    create_rule(workspace_id, repo_id, group3_id,
        "内部一致性检测",
        "跨条款逻辑无矛盾：如付款条件与交付/验收条款不冲突；合同金额在正文、汇总表中前后一致；期限起止日期合理。",
        [contract_id], 20)

    create_rule(workspace_id, repo_id, group3_id,
        "错别字/语义错误检测",
        "检测合同文本中的错别字、用词不当、语义歧义",
        [contract_id], 30)

    # ----------------------------------------------------------
    # 步骤 6：提交审核任务
    # ----------------------------------------------------------
    extract_task_ids = [file_result.get("task_id")] if file_result.get("task_id") else []
    review_task_id = submit_review_task(
        workspace_id,
        f"合同审核_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
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
