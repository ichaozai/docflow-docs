# DocFlow Java 示例

演示如何通过 DocFlow API 完成文档的全流程自动化处理：
创建空间 → 配置文件类别 → 上传文件 → 获取分类与抽取结果 → 智能审核。

## 前置条件

- JDK 11+
- Maven 3.6+
- TextIn 账号（[注册](https://www.textin.com/)）
- 已获取 `x-ti-app-id` 和 `x-ti-secret-code`（登录后前往 [TextIn 控制台 - 账号与开发者信息](https://www.textin.com/console/dashboard/setting) 查看）

## 示例列表

### 费用报销场景

| 类名 | 说明 |
|---|---|
| `ExpenseReimbursement` | **从零开始**：创建空间 → 配置文件类别 → 上传文件 → 抽取结果 |
| `ExpenseReimbursementConfigured` | **已完成配置**：上传文件 → 抽取结果 → 智能审核 |

### AP 审单场景

| 类名 | 说明 |
|---|---|
| `ApReview` | **从零开始**：创建空间 → 配置文件类别与规则库 → 上传文件 → 抽取结果 → 智能审核 |
| `ApReviewConfigured` | **已完成配置**：上传文件 → 抽取结果 → 智能审核 |

### 合同审核场景

| 类名 | 说明 |
|---|---|
| `ContractReview` | **从零开始**：创建空间 → 配置文件类别与规则库 → 上传文件 → 抽取结果 → 智能审核 |
| `ContractReviewConfigured` | **已完成配置**：上传文件 → 抽取结果 → 智能审核 |

## 配置

每个 Java 类文件顶部都有配置区域，运行前需填写实际值。

**从零开始版本**需要：

```java
private static final String APP_ID        = "your-app-id";
private static final String SECRET_CODE   = "your-secret-code";
```

**已完成配置版本**需要：

```java
private static final String APP_ID       = "your-app-id";
private static final String SECRET_CODE  = "your-secret-code";
private static final String WORKSPACE_ID = "your-workspace-id";
private static final String REPO_ID      = "your-repo-id";
```

## 编译与运行

```bash
# 进入 java 示例目录
cd examples/java

# 编译
mvn clean compile -q

# 运行费用报销（从零开始）
mvn exec:java -Dexec.mainClass="com.docflow.ExpenseReimbursement"

# 运行 AP 审单（已完成配置）
mvn exec:java -Dexec.mainClass="com.docflow.ApReviewConfigured"

# 运行合同审核（已完成配置）
mvn exec:java -Dexec.mainClass="com.docflow.ContractReviewConfigured"
```

## 样本文件

示例中使用的样本文件已内置在 `../sample_files/` 目录下：

| 目录 | 文件 | 说明 |
|---|---|---|
| `expense_reimbursement/` | `sample_expense_form.xls` | 差旅费报销申请单 |
| | `sample_hotel_receipt.png` | 酒店住宿水单 |
| | `sample_payment_record.pdf` | 银行支付记录 |
| | `sample_rule_repo.xlsx` | 审核规则库配置模板 |
| `ap_review/` | `sample_invoice.pdf` | 增值税发票 |
| | `sample_contract.pdf` | 采购合同 |
| | `sample_inbound.pdf` | 入库单 |
| | `sample_acceptance.pdf` | 验收单 |
| `contract_review/` | `sample_contract.docx` | 采购合同 |

## 业务流程说明（从零开始版本）

| 步骤 | API | 说明 |
|---|---|---|
| 1 | `POST /workspace/create` | 创建工作空间 |
| 2 | `POST /category/create` | 创建文件类别，同步上传样本并配置字段 |
| 3 | `POST /file/upload` | 上传待处理单据 |
| 4 | `GET /file/fetch` | 轮询直至识别完成，获取分类与抽取结果 |
| 5 | `POST /review/task/submit` | 提交智能审核任务（AP 审单、合同审核） |
| 6 | `POST /review/task/result` | 轮询获取审核结论 |

## 项目依赖

| 库 | 版本 | 用途 |
|---|---|---|
| OkHttp | 4.12.0 | HTTP 请求（含 multipart 文件上传） |
| Gson | 2.10.1 | JSON 序列化与解析 |
