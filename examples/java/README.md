# DocFlow Java 示例 — 费用报销场景

演示如何通过 DocFlow API 完成费用报销单据的全流程自动化处理：
创建空间 → 配置文件类别 → 上传文件 → 获取分类与抽取结果。

## 前置条件

- JDK 11+
- Maven 3.6+
- TextIn 账号（[注册](https://www.textin.com/)）
- 已获取 `x-ti-app-id` 和 `x-ti-secret-code`（登录后前往 [TextIn 控制台 - 账号与开发者信息](https://www.textin.com/console/dashboard/setting) 查看）
- 企业组织 ID（`enterprise_id`，可在控制台「企业管理」中查看）

## 配置

打开 `src/main/java/com/docflow/ExpenseReimbursement.java`，填写文件顶部的配置项：

```java
private static final String APP_ID        = "your-app-id";
private static final String SECRET_CODE   = "your-secret-code";
private static final long   ENTERPRISE_ID = 0L;   // 替换为企业组织 ID
```

## 编译与运行

```bash
# 进入 java 示例目录
cd examples/java

# 编译并打包为可执行 jar
mvn clean package -q

# 运行（从 examples/java 目录执行，样本文件路径基于此目录）
java -jar target/expense-reimbursement-1.0.0.jar
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

## 项目依赖

| 库 | 版本 | 用途 |
|---|---|---|
| OkHttp | 4.12.0 | HTTP 请求（含 multipart 文件上传） |
| Gson | 2.10.1 | JSON 序列化与解析 |
