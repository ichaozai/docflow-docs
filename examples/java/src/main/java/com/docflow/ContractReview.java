package com.docflow;

import com.google.gson.*;
import okhttp3.*;

import java.io.File;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * DocFlow 合同审核场景示例
 *
 * <p>完整演示从零开始的业务流程：
 * <ol>
 *   <li>创建工作空间</li>
 *   <li>创建文件类别（采购合同，含字段配置）</li>
 *   <li>上传待审核合同文件</li>
 *   <li>轮询获取抽取结果，展示字段抽取结果</li>
 *   <li>配置审核规则库（规则库 → 规则组 → 规则）</li>
 *   <li>提交审核任务</li>
 *   <li>轮询获取审核结果，展示审核结论</li>
 * </ol>
 *
 * <p>依赖：OkHttp 4.x、Gson（见 pom.xml）
 */
public class ContractReview {

    // ============================================================
    // 配置项 — 请替换为您的实际值
    // ============================================================
    private static final String APP_ID        = "your-app-id";       // x-ti-app-id
    private static final String SECRET_CODE   = "your-secret-code";  // x-ti-secret-code
    private static final Long   ENTERPRISE_ID = null;                 // 企业组织 ID，不需要时留 null

    private static final String BASE_URL = "https://docflow.textin.com";

    // 示例文件目录（相对 examples/ 根目录）
    private static final String SAMPLE_DIR =
            new File("../sample_files/合同审核").getAbsolutePath();

    // ============================================================
    // 全局工具对象
    // ============================================================
    private static final OkHttpClient HTTP = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build();

    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();
    private static final MediaType JSON_TYPE = MediaType.get("application/json; charset=utf-8");

    // ============================================================
    // 工具辅助函数
    // ============================================================

    private static Headers authHeaders() {
        return new Headers.Builder()
                .add("x-ti-app-id", APP_ID)
                .add("x-ti-secret-code", SECRET_CODE)
                .build();
    }

    private static JsonObject checkResponse(String body, String action) {
        JsonObject obj = JsonParser.parseString(body).getAsJsonObject();
        if (obj.get("code").getAsInt() != 200) {
            throw new RuntimeException(action + " 失败: " + body);
        }
        return obj;
    }

    private static String mimeType(String filename) {
        String lower = filename.toLowerCase();
        if (lower.endsWith(".png"))  return "image/png";
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".pdf"))  return "application/pdf";
        if (lower.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        if (lower.endsWith(".xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
        return "application/octet-stream";
    }

    private static Map<String, String> field(String name) {
        Map<String, String> m = new LinkedHashMap<>();
        m.put("name", name);
        return m;
    }

    // ============================================================
    // 步骤 1：创建工作空间
    // REST API: POST /api/app-api/sip/platform/v2/workspace/create
    // ============================================================

    public static String createWorkspace(String name, String description) throws IOException {
        String url = BASE_URL + "/api/app-api/sip/platform/v2/workspace/create";
        JsonObject payload = new JsonObject();
        payload.addProperty("name", name);
        payload.addProperty("description", description);
        if (ENTERPRISE_ID != null) payload.addProperty("enterprise_id", ENTERPRISE_ID);
        payload.addProperty("auth_scope", 0);

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "创建工作空间");
            String workspaceId = data.getAsJsonObject("result").get("workspace_id").getAsString();
            System.out.println("[步骤1] 工作空间创建成功  workspace_id=" + workspaceId);
            return workspaceId;
        }
    }

    // ============================================================
    // 步骤 2：创建文件类别（含样本文件和字段配置）
    // REST API: POST /api/app-api/sip/platform/v2/category/create
    // ============================================================

    /**
     * 创建文件类别，同时上传样本文件并配置字段。
     *
     * <p>合同审核场景使用 Model 2（复杂文档理解），适合合同这类长文档的深度理解和字段抽取。
     */
    public static String createCategory(
            String workspaceId,
            String name,
            String sampleFilePath,
            List<Map<String, String>> fields,
            String categoryPrompt) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/create";
        File sampleFile = new File(sampleFilePath);

        MultipartBody body = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("workspace_id",    workspaceId)
                .addFormDataPart("name",            name)
                .addFormDataPart("extract_model",   "Model 2")
                .addFormDataPart("category_prompt", categoryPrompt)
                .addFormDataPart("fields",          GSON.toJson(fields))
                .addFormDataPart("sample_files",    sampleFile.getName(),
                        RequestBody.create(sampleFile, MediaType.get(mimeType(sampleFile.getName()))))
                .build();

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(body)
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "创建文件类别[" + name + "]");
            String categoryId = data.getAsJsonObject("result").get("category_id").getAsString();
            System.out.println("[步骤2] 文件类别创建成功  name=" + name + "  category_id=" + categoryId);
            return categoryId;
        }
    }

    // ============================================================
    // 步骤 3：上传待处理文件
    // REST API: POST /api/app-api/sip/platform/v2/file/upload
    // ============================================================

    public static String uploadFile(String workspaceId, String filePath) throws IOException {
        File file = new File(filePath);
        HttpUrl url = HttpUrl.parse(BASE_URL + "/api/app-api/sip/platform/v2/file/upload")
                .newBuilder()
                .addQueryParameter("workspace_id", workspaceId)
                .build();

        MultipartBody body = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", file.getName(),
                        RequestBody.create(file, MediaType.get(mimeType(file.getName()))))
                .build();

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(body)
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "上传文件[" + file.getName() + "]");
            String batchNumber = data.getAsJsonObject("result").get("batch_number").getAsString();
            System.out.println("[步骤3] 文件上传成功  name=" + file.getName()
                    + "  batch_number=" + batchNumber);
            return batchNumber;
        }
    }

    // ============================================================
    // 步骤 4：轮询等待抽取结果
    // REST API: GET /api/app-api/sip/platform/v2/file/fetch
    // ============================================================

    /**
     * 轮询直至文件识别完成，返回文件结果对象（含 task_id）。
     *
     * <p>合同文档通常较长，超时时间设置为 180s。
     */
    public static JsonObject waitForResult(
            String workspaceId, String batchNumber,
            int timeoutSec, int intervalSec) throws IOException, InterruptedException {

        HttpUrl url = HttpUrl.parse(BASE_URL + "/api/app-api/sip/platform/v2/file/fetch")
                .newBuilder()
                .addQueryParameter("workspace_id", workspaceId)
                .addQueryParameter("batch_number",  batchNumber)
                .build();

        long deadline = System.currentTimeMillis() + (long) timeoutSec * 1000;
        System.out.print("[步骤4] 等待处理结果（batch_number=" + batchNumber + "）...");

        while (System.currentTimeMillis() < deadline) {
            Request req = new Request.Builder()
                    .url(url).headers(authHeaders()).get().build();

            try (Response resp = HTTP.newCall(req).execute()) {
                JsonObject data = checkResponse(resp.body().string(), "获取处理结果");
                JsonArray files = data.getAsJsonObject("result").getAsJsonArray("files");
                if (files != null && files.size() > 0) {
                    JsonObject file = files.get(0).getAsJsonObject();
                    int status = file.get("recognition_status").getAsInt();
                    if (status == 1) { System.out.println(" 完成"); return file; }
                    if (status == 2) {
                        String cause = file.has("failure_causes")
                                ? file.get("failure_causes").getAsString() : "未知原因";
                        throw new RuntimeException("文件处理失败: " + cause);
                    }
                }
            }
            System.out.print(".");
            Thread.sleep((long) intervalSec * 1000);
        }
        throw new RuntimeException("等待处理结果超时（" + timeoutSec + "s）");
    }

    public static void displayResult(JsonObject fileResult) {
        System.out.println("\n" + "=".repeat(60));
        System.out.println("文件名   : " + str(fileResult, "name"));
        System.out.println("分类结果 : " + str(fileResult, "category", "未分类"));

        if (!fileResult.has("data") || fileResult.get("data").isJsonNull()) return;
        JsonObject data = fileResult.getAsJsonObject("data");

        JsonArray fields = jsonArray(data, "fields");
        if (fields != null && fields.size() > 0) {
            System.out.println("\n── 基本信息字段 ────────────────────────");
            for (JsonElement e : fields) {
                JsonObject f = e.getAsJsonObject();
                String val = str(f, "value");
                String display = val.length() > 80 ? val.substring(0, 80) + "..." : val;
                System.out.printf("  %-25s: %s%n", str(f, "key"), display);
            }
        }
    }

    // ============================================================
    // 步骤 5：配置审核规则库
    // ============================================================

    public static String createRuleRepo(String workspaceId, String name) throws IOException {
        String url = BASE_URL + "/api/app-api/sip/platform/v2/review/rule_repo/create";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("name", name);

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "创建规则库");
            String repoId = data.getAsJsonObject("result").get("repo_id").getAsString();
            System.out.println("[步骤5] 规则库创建成功  name=" + name + "  repo_id=" + repoId);
            return repoId;
        }
    }

    public static String createRuleGroup(
            String workspaceId, String repoId, String name) throws IOException {
        String url = BASE_URL + "/api/app-api/sip/platform/v2/review/rule_group/create";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("repo_id", repoId);
        payload.addProperty("name", name);

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "创建规则组[" + name + "]");
            String groupId = data.getAsJsonObject("result").get("group_id").getAsString();
            System.out.println("  规则组创建成功  name=" + name + "  group_id=" + groupId);
            return groupId;
        }
    }

    public static String createRule(
            String workspaceId, String repoId, String groupId,
            String name, String prompt, List<String> categoryIds, int riskLevel) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/review/rule/create";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("repo_id",      repoId);
        payload.addProperty("group_id",     groupId);
        payload.addProperty("name",         name);
        payload.addProperty("prompt",       prompt);
        JsonArray catArr = new JsonArray();
        categoryIds.forEach(catArr::add);
        payload.add("category_ids", catArr);
        payload.addProperty("risk_level", riskLevel);

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "创建规则[" + name + "]");
            String ruleId = data.getAsJsonObject("result").get("rule_id").getAsString();
            System.out.println("    规则创建成功  name=" + name + "  rule_id=" + ruleId);
            return ruleId;
        }
    }

    // ============================================================
    // 步骤 6：提交审核任务
    // REST API: POST /api/app-api/sip/platform/v2/review/task/submit
    // ============================================================

    public static String submitReviewTask(
            String workspaceId, String name, String repoId,
            List<String> extractTaskIds) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/review/task/submit";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("name",         name);
        payload.addProperty("repo_id",      repoId);
        JsonArray ids = new JsonArray();
        extractTaskIds.forEach(ids::add);
        payload.add("extract_task_ids", ids);

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "提交审核任务");
            String taskId = data.getAsJsonObject("result").get("task_id").getAsString();
            System.out.println("[步骤6] 审核任务提交成功  task_id=" + taskId);
            return taskId;
        }
    }

    // ============================================================
    // 步骤 7：轮询等待审核结果
    // REST API: POST /api/app-api/sip/platform/v2/review/task/result
    // ============================================================

    public static JsonObject waitForReview(
            String workspaceId, String taskId,
            int timeoutSec, int intervalSec) throws IOException, InterruptedException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/review/task/result";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("task_id",      taskId);

        long deadline = System.currentTimeMillis() + (long) timeoutSec * 1000;
        System.out.print("[步骤7] 等待审核结果（task_id=" + taskId + "）...");

        while (System.currentTimeMillis() < deadline) {
            Request req = new Request.Builder()
                    .url(url).headers(authHeaders())
                    .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                    .build();

            try (Response resp = HTTP.newCall(req).execute()) {
                JsonObject data = checkResponse(resp.body().string(), "获取审核结果");
                JsonObject result = data.getAsJsonObject("result");
                int status = result.get("status").getAsInt();
                if (status == 1 || status == 2 || status == 4 || status == 7) {
                    System.out.println(" 完成");
                    return result;
                }
            }
            System.out.print(".");
            Thread.sleep((long) intervalSec * 1000);
        }
        throw new RuntimeException("等待审核结果超时（" + timeoutSec + "s）");
    }

    public static void displayReviewResult(JsonObject reviewResult) {
        Map<Integer, String> statusMap = new LinkedHashMap<>();
        statusMap.put(0, "未审核");   statusMap.put(1, "审核通过");   statusMap.put(2, "审核失败");
        statusMap.put(3, "审核中");   statusMap.put(4, "审核不通过"); statusMap.put(5, "识别中");
        statusMap.put(6, "排队中");   statusMap.put(7, "识别失败");
        Map<Integer, String> riskMap = new LinkedHashMap<>();
        riskMap.put(10, "高风险"); riskMap.put(20, "中风险"); riskMap.put(30, "低风险");

        int status = reviewResult.get("status").getAsInt();
        JsonObject stats = reviewResult.has("statistics")
                ? reviewResult.getAsJsonObject("statistics") : new JsonObject();

        System.out.println("\n" + "=".repeat(60));
        System.out.println("审核任务状态  : " + statusMap.getOrDefault(status, "未知"));
        System.out.println("规则通过数    : " + (stats.has("pass_count")    ? stats.get("pass_count").getAsInt()    : 0));
        System.out.println("规则不通过数  : " + (stats.has("failure_count") ? stats.get("failure_count").getAsInt() : 0));

        JsonArray groups = jsonArray(reviewResult, "groups");
        if (groups != null) {
            for (JsonElement ge : groups) {
                JsonObject group = ge.getAsJsonObject();
                System.out.println("\n── 规则组：" + str(group, "group_name") + " ───────────────────");
                JsonArray tasks = jsonArray(group, "review_tasks");
                if (tasks != null) {
                    for (JsonElement te : tasks) {
                        JsonObject rt = te.getAsJsonObject();
                        int rv        = rt.has("review_result") ? rt.get("review_result").getAsInt() : 0;
                        int riskLevel = rt.has("risk_level")    ? rt.get("risk_level").getAsInt()    : 0;
                        String icon   = rv == 1 ? "✓" : "✗";
                        System.out.printf("  %s [%s] %s: %s%n",
                                icon, riskMap.getOrDefault(riskLevel, "未知"),
                                str(rt, "rule_name"), statusMap.getOrDefault(rv, "未知"));
                        String reasoning = str(rt, "reasoning");
                        if (!reasoning.isEmpty()) {
                            System.out.println("    依据: " + (reasoning.length() > 100
                                    ? reasoning.substring(0, 100) + "..." : reasoning));
                        }
                    }
                }
            }
        }
    }

    // ============================================================
    // 主流程
    // ============================================================
    public static void main(String[] args) throws Exception {
        System.out.println("=".repeat(60));
        System.out.println("  DocFlow 合同审核场景示例");
        System.out.println("=".repeat(60));

        // 步骤 1：创建工作空间
        String workspaceName = "合同审核_" + new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
        String workspaceId = createWorkspace(workspaceName, "采购合同智能审核空间");

        // 步骤 2：创建文件类别（采购合同）
        String contractId = createCategory(
                workspaceId, "采购合同",
                SAMPLE_DIR + "/示例_采购合同.docx",
                Arrays.asList(
                        field("合同编号"),               field("合同名称"),
                        field("签订日期"),               field("生效条件"),
                        field("甲方全称"),               field("甲方统一社会信用代码"),
                        field("甲方联系方式"),           field("甲方地址"),
                        field("乙方全称"),               field("乙方统一社会信用代码"),
                        field("乙方联系方式"),           field("乙方地址"),
                        field("乙方法定代表人/授权委托人"),
                        field("标的名称"),               field("标的规格型号/标准"),
                        field("标的技术/质量标准"),      field("标的数量/服务范围"),
                        field("含税总金额（大写）"),     field("不含税金额"),
                        field("税额"),                   field("税率"),
                        field("发票条款"),               field("付款方式"),
                        field("付款条件"),               field("付款比例"),
                        field("账期"),                   field("收款账户信息"),
                        field("履约期限"),               field("履约地点"),
                        field("交付/验收标准与流程"),   field("违约责任"),
                        field("免责条款"),               field("争议解决方式"),
                        field("合同解除与终止条件"),    field("保密条款"),
                        field("知识产权声明"),           field("合同份数"),
                        field("附件清单"),               field("签约人签字/盖章")
                ), "");

        System.out.println("\n类别配置完成  采购合同: category_id=" + contractId);

        // 步骤 3：上传待处理文件
        System.out.println("\n开始上传待处理文件...");
        String batchNumber = uploadFile(workspaceId, SAMPLE_DIR + "/示例_采购合同.docx");

        // 步骤 4：获取并展示抽取结果
        System.out.println("\n开始获取处理结果...");
        JsonObject fileResult = waitForResult(workspaceId, batchNumber, 180, 3);
        displayResult(fileResult);

        // 步骤 5：配置审核规则库
        System.out.println("\n开始配置审核规则库...");
        String repoId = createRuleRepo(workspaceId, "合同审核场景规则库");

        // 规则组1：财务条款审核
        String group1Id = createRuleGroup(workspaceId, repoId, "财务条款审核");
        createRule(workspaceId, repoId, group1Id, "连带责任条款",
                "若存在开票方、付款方与签约主体不一致的情形（三方关系），则合同必须明确各方债权债务关系。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group1Id, "履约保证金条款",
                "若约定履约保证金/质保金，必须明确退还条件、退还时间节点及不予退还的情形。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group1Id, "滞纳金/违约金合理性",
                "若存在甲方逾期付款或乙方逾期交付的滞纳金/违约金条款，则日费率 <= 0.05%。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group1Id, "验收/交付标准明确性",
                "合同必须明确交付完成的判定标准（如双方签署验收单、开通即交付、开通N天后无异议即交付等）。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group1Id, "币别一致性",
                "合同全文中涉及金额的币别必须前后一致，若无提及币别信息，则视为一致。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group1Id, "付款方式明确性",
                "付款方式必须明确，属于以下之一：银行转账、银行承兑汇票、商业承兑汇票、第三方支付。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group1Id, "付款条件明确性",
                "付款节点需清晰（如【货到验收合格后】【合同签订后】）；付款期限需明确（如【30日内支付】【收到发票后15个工作日】）。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group1Id, "税率合理性",
                "税率必须为有效值：6%、9%、13%、1%、3%、免税、0%；税率需与合同标的类型匹配。",
                Arrays.asList(contractId), 10);
        createRule(workspaceId, repoId, group1Id, "付款比例合计",
                "若合同中存在分阶段付款比例（如预付款、进度款、尾款），则各阶段付款比例合计必须等于 100%。",
                Arrays.asList(contractId), 10);
        createRule(workspaceId, repoId, group1Id, "产品明细合计与总金额一致性",
                "若合同包含明细行：\n1. 各明细行【单价 x 数量 = 金额】；\n2. 所有明细行金额合计 = 合同总金额（允许±0.01元）。",
                Arrays.asList(contractId), 10);
        createRule(workspaceId, repoId, group1Id, "金额合规检测",
                "1. 不含税金额 x 税率 = 税额（允许±0.01元尾差）；\n2. 不含税金额 + 税额 = 含税总金额。",
                Arrays.asList(contractId), 10);
        createRule(workspaceId, repoId, group1Id, "合同金额大小写一致性",
                "若大小写金额均存在：两者必须一致；若仅存在大写金额：校验大写格式是否符合中文金额书写规范（如【壹万贰仟叁佰元整】）",
                Arrays.asList(contractId), 10);

        // 规则组2：法务合规审核
        String group2Id = createRuleGroup(workspaceId, repoId, "法务合规审核");
        createRule(workspaceId, repoId, group2Id, "不可抗力条款",
                "包含不可抗力条款，且定义清晰（如列明不可抗力事件范围、通知时限、责任豁免方式）。",
                Arrays.asList(contractId), 30);
        createRule(workspaceId, repoId, group2Id, "保密条款完整性",
                "保密信息定义、保密期限、违约责任三项要素齐全。",
                Arrays.asList(contractId), 30);
        createRule(workspaceId, repoId, group2Id, "知识产权归属",
                "若合同涉及技术开发、委托设计、软件开发等内容，则必须存在知识产权归属条款且归属明确。",
                Arrays.asList(contractId), 30);
        createRule(workspaceId, repoId, group2Id, "违约金上限合理性",
                "违约金是否设置上限（如不超过合同总金额的20%），过高违约金存在法律风险。",
                Arrays.asList(contractId), 30);
        createRule(workspaceId, repoId, group2Id, "违约对等性检查",
                "比较甲乙双方的逾期违约金比例。若双方比例差异超过设定阈值（如相差>=50%），则标记提醒。",
                Arrays.asList(contractId), 30);
        createRule(workspaceId, repoId, group2Id, "合同日期合理性",
                "签订日期 <= 生效日期；生效日期 <= 到期日期（若有）；生效日期不得早于当前日期。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group2Id, "签约主体名称一致性",
                "合同首部、尾部签章处、正文中出现的签约主体名称必须完全一致。",
                Arrays.asList(contractId), 10);
        createRule(workspaceId, repoId, group2Id, "签约主体信息完整性",
                "甲乙双方以下字段非空：名称、地址、联系方式。",
                Arrays.asList(contractId), 10);
        createRule(workspaceId, repoId, group2Id, "必备条款完整性",
                "合同必须包含以下条款：\n"
                + "1. 主体信息（双方名称、统一社会信用代码）；\n"
                + "2. 标的（货物/服务名称）；\n"
                + "3. 数量/服务范围；\n"
                + "4. 质量（若有）；\n"
                + "5. 价款/报酬（含税总金额）；\n"
                + "6. 履行期限、地点和方式；\n"
                + "7. 违约责任（有明确的违约情形和违约金）；\n"
                + "8. 争议解决方式（诉讼或仲裁）。",
                Arrays.asList(contractId), 10);

        // 规则组3：文本质量与一致性审核
        String group3Id = createRuleGroup(workspaceId, repoId, "文本质量与一致性审核");
        createRule(workspaceId, repoId, group3Id, "数字计算校验",
                "1. 单价 x 数量 = 金额（每行）；\n2. 各分项金额合计 = 合同总金额（允许±0.01元尾差）。",
                Arrays.asList(contractId), 30);
        createRule(workspaceId, repoId, group3Id, "内部一致性检测",
                "跨条款逻辑无矛盾：如付款条件与交付/验收条款不冲突；合同金额在正文、汇总表中前后一致；期限起止日期合理。",
                Arrays.asList(contractId), 20);
        createRule(workspaceId, repoId, group3Id, "错别字/语义错误检测",
                "检测合同文本中的错别字、用词不当、语义歧义",
                Arrays.asList(contractId), 30);

        // 步骤 6：提交审核任务
        List<String> extractTaskIds = new ArrayList<>();
        if (fileResult.has("task_id") && !fileResult.get("task_id").isJsonNull()) {
            extractTaskIds.add(fileResult.get("task_id").getAsString());
        }
        String ts = new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
        String reviewTaskId = submitReviewTask(workspaceId, "合同审核_" + ts, repoId, extractTaskIds);

        // 步骤 7：轮询获取审核结果
        JsonObject reviewResult = waitForReview(workspaceId, reviewTaskId, 300, 5);
        displayReviewResult(reviewResult);

        System.out.println("\n" + "=".repeat(60));
        System.out.println("  示例运行完成");
        System.out.println("=".repeat(60));
    }

    // ============================================================
    // 私有工具方法
    // ============================================================

    private static String str(JsonObject obj, String key) { return str(obj, key, ""); }

    private static String str(JsonObject obj, String key, String defaultVal) {
        if (obj == null || !obj.has(key) || obj.get(key).isJsonNull()) return defaultVal;
        return obj.get(key).getAsString();
    }

    private static JsonArray jsonArray(JsonObject obj, String key) {
        if (obj == null || !obj.has(key) || obj.get(key).isJsonNull()) return null;
        JsonElement e = obj.get(key);
        return e.isJsonArray() ? e.getAsJsonArray() : null;
    }
}
