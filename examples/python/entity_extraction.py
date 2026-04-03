#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TextIn 智能文档抽取 API 示例

演示两种抽取模式：
  1. Prompt 模式：提供自然语言 prompt，由大模型理解并自由抽取
  2. 字段模式：提供结构化的字段列表，进行精确可控抽取

支持格式：png, jpg, jpeg, pdf, bmp, tiff, webp, doc, docx, html,
          mhtml, xls, xlsx, csv, ppt, pptx, txt, ofd

依赖：
  pip install requests

使用前请先填写下方配置项，然后执行：
  python entity_extraction.py <文件路径>
"""

import base64
import json
import os
import sys

import requests

# ============================================================
# 配置项 — 请替换为您的实际值
# ============================================================
APP_ID      = "your-app-id"       # TextIn 控制台中的 x-ti-app-id
SECRET_CODE = "your-secret-code"  # TextIn 控制台中的 x-ti-secret-code

API_URL = "https://api.textin.com/ai/service/v2/entity_extraction"


# ============================================================
# 工具辅助函数
# ============================================================

def _headers() -> dict:
    """构造鉴权请求头。"""
    return {
        "x-ti-app-id":      APP_ID,
        "x-ti-secret-code": SECRET_CODE,
        "Content-Type":     "application/json",
    }


def _encode_file(file_path: str) -> str:
    """读取本地文件并转为 base64 字符串。"""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract(file_path: str, request_body: dict, url_params: dict = None) -> dict:
    """
    调用智能文档抽取 API。

    :param file_path:     待抽取的本地文件路径
    :param request_body:  请求体字段（不含 file 字段）
    :param url_params:    URL 参数（可选），例如 {"parse_mode": "scan"}
    :return:              解析后的 JSON 响应
    :raises RuntimeError: API 返回非 200 错误码时抛出
    """
    body = {**request_body, "file": _encode_file(file_path)}
    resp = requests.post(
        API_URL,
        params=url_params or {},
        headers=_headers(),
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 200:
        raise RuntimeError(f"API 错误 {result.get('code')}：{result.get('message')}")
    return result


# ============================================================
# 示例 1：Prompt 模式
# ============================================================

def demo_prompt_mode(file_path: str):
    """以 Prompt 模式对文档进行智能抽取。"""
    print("=" * 60)
    print("示例 1：Prompt 模式")
    print("=" * 60)

    result = extract(
        file_path,
        request_body={
            "prompt": "请抽取文件中的所有关键字段，以 JSON 格式返回",
        },
        url_params={"parse_mode": "scan"},
    )

    res = result.get("result", {})

    # llm_json：大模型直接返回的键值对，方便直接使用
    llm_json = res.get("llm_json", {})
    print("\n抽取结果 (llm_json)：")
    print(json.dumps(llm_json, ensure_ascii=False, indent=2))

    # usage：token 消耗统计
    usage = res.get("usage", {})
    if usage:
        print(f"\nToken 消耗：输入 {usage.get('prompt_tokens', 0)}，"
              f"输出 {usage.get('completion_tokens', 0)}，"
              f"合计 {usage.get('total_tokens', 0)}")


# ============================================================
# 示例 2：字段模式
# ============================================================

def demo_field_mode(file_path: str):
    """以自定义字段模式对文档进行精确抽取。"""
    print("=" * 60)
    print("示例 2：字段模式")
    print("=" * 60)

    result = extract(
        file_path,
        request_body={
            # fields：要抽取的单值字段列表
            "fields": [
                {"name": "发票号码"},
                {"name": "开票日期"},
                {"name": "购买方名称"},
                {"name": "销售方名称"},
                {"name": "合计金额"},
            ],
            # table_fields：要抽取的表格字段（可选）
            "table_fields": [
                {
                    "title": "货物明细",
                    "description": "发票中的货物或服务明细表格",
                    "fields": [
                        {"name": "项目名称"},
                        {"name": "数量"},
                        {"name": "单价"},
                        {"name": "金额"},
                    ],
                }
            ],
        },
        url_params={"parse_mode": "scan"},
    )

    res = result.get("result", {})

    # details：字段抽取结果
    details = res.get("details", {})
    print("\n抽取结果 (details)：")
    for key, val in details.items():
        if key == "row":
            rows = val if isinstance(val, list) else []
            print(f"  表格（货物明细）：共 {len(rows)} 行")
            for i, row in enumerate(rows, 1):
                print(f"    第 {i} 行：{json.dumps(row, ensure_ascii=False)}")
        elif isinstance(val, dict):
            print(f"  {key}：{val.get('value', '')}")

    print(f"\n处理页数：{res.get('page_count', '-')}")
    print(f"推理时间：{result.get('duration', '-')} ms")


# ============================================================
# 入口
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("用法：python entity_extraction.py <文件路径>")
        print("示例：python entity_extraction.py invoice.pdf")
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"文件不存在：{file_path}")
        sys.exit(1)

    demo_prompt_mode(file_path)
    print()
    demo_field_mode(file_path)


if __name__ == "__main__":
    main()
