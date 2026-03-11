# DocFlow Python 示例 — 费用报销场景

演示如何通过 DocFlow API 完成费用报销单据的全流程自动化处理：
创建空间 → 配置文件类别 → 上传文件 → 获取分类与抽取结果。

## 前置条件

- Python 3.8+
- TextIn 账号（[注册](https://www.textin.com/)）
- 已获取 `x-ti-app-id` 和 `x-ti-secret-code`（登录后前往 [TextIn 控制台 - 账号与开发者信息](https://www.textin.com/console/dashboard/setting) 查看）
- 企业组织 ID（`enterprise_id`，可在控制台「企业管理」中查看）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

打开 `expense_reimbursement.py`，填写文件顶部的配置项：

```python
APP_ID        = "your-app-id"      # x-ti-app-id
SECRET_CODE   = "your-secret-code" # x-ti-secret-code
ENTERPRISE_ID = 0                  # 企业组织 ID
```

## 运行

```bash
python expense_reimbursement.py
```

## 样本文件

示例中使用的样本文件已内置在 `../sample_files/费用报销/` 目录下：

| 文件名 | 说明 |
|---|---|
| 报销申请单.XLS | 差旅费报销申请单 |
| 酒店水单.png | 酒店住宿水单 |
| 支付记录.png | 银行支付记录 |

## 业务流程说明

| 步骤 | API | 说明 |
|---|---|---|
| 1 | `POST /workspace/create` | 创建「费用报销」工作空间 |
| 2 | `POST /category/create` | 分别创建三个文件类别，同步上传样本并配置字段 |
| 2b | `POST /category/fields/add` | 为酒店水单追加表格字段 |
| 3 | `POST /file/upload` | 上传三份待处理单据 |
| 4 | `GET /file/fetch` | 轮询直至识别完成，打印分类与抽取结果 |
