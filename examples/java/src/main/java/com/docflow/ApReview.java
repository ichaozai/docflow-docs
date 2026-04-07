package com.docflow;

import com.google.gson.*;
import okhttp3.*;

import java.io.File;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * DocFlow AP 审单场景示例
 *
 * <p>完整演示从零开始的业务流程：
 * <ol>
 *   <li>创建工作空间</li>
 *   <li>创建文件类别（国内票-数电票、采购合同、入库单、验收单）</li>
 *   <li>上传待审核文件（发票、采购合同、入库单、验收单）</li>
 *   <li>轮询获取抽取结果，展示分类与字段抽取结果</li>
 *   <li>配置审核规则库（规则库 → 规则组 → 规则）</li>
 *   <li>提交审核任务</li>
 *   <li>轮询获取审核结果，展示审核结论</li>
 * </ol>
 *
 * <p>依赖：OkHttp 4.x、Gson（见 pom.xml）
 */
public class ApReview {

    // ============================================================
    // 配置项 — 请替换为您的实际值
    // ============================================================
    private static final String APP_ID        = "your-app-id";       // x-ti-app-id
    private static final String SECRET_CODE   = "your-secret-code";  // x-ti-secret-code

    private static final String BASE_URL = "https://docflow.textin.com";

    // 示例文件目录（相对 examples/ 根目录）
    private static final String SAMPLE_DIR =
            new File("../sample_files/ap_review").getAbsolutePath();

    // ============================================================
    // 全局工具对象
    // ============================================================
    private static final OkHttpClient HTTP = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
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
    // 步骤 2：创建文件类别
    // REST API: POST /api/app-api/sip/platform/v2/category/create
    // ============================================================

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
                .addFormDataPart("extract_model",   "Model 1")
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

    /**
     * 在已有类别中追加一个字段。
     *
     * @param tableId 若要创建表格字段，传入 "-1" 表示默认表格；否则传 null。
     */
    public static String addCategoryField(
            String workspaceId, String categoryId, String fieldName, String tableId) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/fields/add";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("category_id",  categoryId);
        payload.addProperty("name",         fieldName);
        if (tableId != null && !tableId.isEmpty()) {
            payload.addProperty("table_id", tableId);
        }

        Request req = new Request.Builder()
                .url(url).headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "追加字段[" + fieldName + "]");
            String fieldId = data.getAsJsonObject("result").get("field_id").getAsString();
            System.out.println("  追加字段成功  name=" + fieldName + "  field_id=" + fieldId);
            return fieldId;
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
                System.out.printf("  %-25s: %s%n", str(f, "key"), str(f, "value"));
            }
        }

        JsonArray tables = jsonArray(data, "tables");
        if (tables != null) {
            for (JsonElement te : tables) {
                JsonObject table = te.getAsJsonObject();
                String tname = str(table, "tableName");
                JsonArray tItems = jsonArray(table, "items");
                if (tItems != null && tItems.size() > 0) {
                    System.out.println("\n── 表格[" + tname + "] ──────────────────────");
                    for (int i = 0; i < tItems.size(); i++) {
                        JsonArray row = tItems.get(i).getAsJsonArray();
                        StringBuilder sb = new StringBuilder("  第").append(i + 1).append("行: ");
                        for (int j = 0; j < row.size(); j++) {
                            JsonObject cell = row.get(j).getAsJsonObject();
                            if (j > 0) sb.append("  |  ");
                            sb.append(str(cell, "key")).append("=").append(str(cell, "value"));
                        }
                        System.out.println(sb);
                    }
                }
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
        System.out.println("  DocFlow AP 审单场景示例");
        System.out.println("=".repeat(60));

        // 步骤 1：创建工作空间
        String workspaceName = "AP审单_" + new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
        String workspaceId = createWorkspace(workspaceName, "AP审单业务自动化处理空间");

        // 步骤 2：配置文件类别

        // 2.1 国内票-数电票（基本信息字段 + 明细表格字段）
        String invoiceId = createCategory(
                workspaceId, "国内票-数电票",
                SAMPLE_DIR + "/sample_invoice.pdf",
                Arrays.asList(
                        field("发票号码"), field("开票日期"),
                        field("价税合计"), field("税前金额"),
                        field("税额"), field("销售方名称"),
                        field("销售方纳税人识别号"), field("购买方名称"),
                        field("购买方纳税人识别号"), field("发票备注")
                ),
                "增值税电子发票（数电票），含发票号码、开票日期、购买方、销售方及价税合计等字段");
        for (String fn : new String[]{"商品名称", "规格型号", "单位", "数量", "单价", "金额", "税率", "税额"}) {
            addCategoryField(workspaceId, invoiceId, fn, "-1");
        }

        // 2.2 采购合同
        String contractId = createCategory(
                workspaceId, "采购合同",
                SAMPLE_DIR + "/sample_contract.pdf",
                Arrays.asList(
                        field("编号"), field("甲方"), field("乙方"),
                        field("签订日期"), field("合作期间"), field("支付条款"),
                        field("乙方银行账户信息"), field("开票信息"), field("违约金条款"),
                        field("采购物料/服务数量"), field("合同类型"), field("采购金额"),
                        field("采购单价"), field("税率"), field("乙方税号"),
                        field("采购物料/服务")
                ), "");
        for (String fn : new String[]{"产品型号", "产品说明", "单价", "数量", "金额"}) {
            addCategoryField(workspaceId, contractId, fn, "-1");
        }

        // 2.3 入库单
        String inboundId = createCategory(
                workspaceId, "入库单",
                SAMPLE_DIR + "/sample_inbound.pdf",
                Arrays.asList(
                        field("收货单编号"), field("收货日期"), field("对应合同号"),
                        field("供应商名称"), field("仓库／库位"), field("物流单号"),
                        field("入库总金额"), field("收货结论"), field("备注"),
                        field("仓库收货人"), field("仓库收货人日期"), field("质检确认"),
                        field("质检确认日期"), field("供应商送货人"), field("供应商送货人日期"),
                        field("供应商税号")
                ), "");
        for (String fn : new String[]{
                "收货入库明细-物料编码", "收货入库明细-物料描述", "收货入库明细-单位",
                "收货入库明细-应收", "收货入库明细-实收", "收货入库明细-差异",
                "收货入库明细-质检", "收货入库明细-签收人"}) {
            addCategoryField(workspaceId, inboundId, fn, "-1");
        }

        // 2.4 验收单
        String acceptanceId = createCategory(
                workspaceId, "验收单",
                SAMPLE_DIR + "/sample_acceptance.pdf",
                Arrays.asList(
                        field("项目名称"), field("合同编号"), field("甲方单位名称"),
                        field("乙方单位名称"), field("甲方验收人"), field("乙方施工人"),
                        field("交付内容"), field("验收说明"), field("验收结论"),
                        field("验收数量"), field("验收日期"), field("乙方税号")
                ), "");

        System.out.println("\n类别配置完成");
        System.out.println("  国内票-数电票: category_id=" + invoiceId);
        System.out.println("  采购合同:      category_id=" + contractId);
        System.out.println("  入库单:        category_id=" + inboundId);
        System.out.println("  验收单:        category_id=" + acceptanceId);

        // 步骤 3：上传待处理文件
        System.out.println("\n开始上传待处理文件...");
        String[] sampleFiles = {
                SAMPLE_DIR + "/sample_invoice.pdf",
                SAMPLE_DIR + "/sample_contract.pdf",
                SAMPLE_DIR + "/sample_inbound.pdf",
                SAMPLE_DIR + "/sample_acceptance.pdf"
        };
        List<String> batchNumbers = new ArrayList<>();
        for (String path : sampleFiles) {
            batchNumbers.add(uploadFile(workspaceId, path));
        }

        // 步骤 4：获取并展示抽取结果
        System.out.println("\n开始获取处理结果...");
        List<JsonObject> rawResults = new ArrayList<>();
        for (String batchNumber : batchNumbers) {
            try {
                JsonObject result = waitForResult(workspaceId, batchNumber, 120, 3);
                displayResult(result);
                rawResults.add(result);
            } catch (Exception e) {
                System.err.println("  异常: " + e.getMessage());
            }
        }

        // 步骤 5：配置审核规则库
        System.out.println("\n开始配置审核规则库...");
        String repoId = createRuleRepo(workspaceId, "AP审单场景审核规则库");

        // 规则组1：业务一致性审核
        String group1Id = createRuleGroup(workspaceId, repoId, "业务一致性审核");
        createRule(workspaceId, repoId, group1Id, "供应商一致性",
                "若均存在税号字段：\n发票【销售方纳税人识别号】= 合同【乙方纳税人识别号】= 入库单【供应商税号】\n"
                + "若任一单据无税号：\n发票【销售方名称】= 合同【乙方名称】= 入库单【供应商名称】",
                Arrays.asList(invoiceId, contractId, inboundId), 10);
        createRule(workspaceId, repoId, group1Id, "金额匹配",
                "发票价税合计金额≤采购合同总金额；若合同为框架协议（金额为空或0），则不校验金额浮动。",
                Arrays.asList(invoiceId, contractId), 10);
        createRule(workspaceId, repoId, group1Id, "数量一致性（入库单维度）",
                "若发票包含商品明细，则发票数量合计 ≤ 入库单实收数量合计。",
                Arrays.asList(invoiceId, inboundId), 20);
        createRule(workspaceId, repoId, group1Id, "标的一致性",
                "若采购合同中约定了具体规格型号，采购合同中约定的规格型号与入库单、发票中的规格型号必须完全一致；"
                + "当合同未约定具体规格型号时，校验各单据中的标的物描述应指向同一商品或服务；"
                + "服务类采购（如咨询、运维、人力外包）的验收单中的服务内容描述与合同约定的服务范围应一致",
                Arrays.asList(invoiceId, contractId, acceptanceId, inboundId), 30);
        createRule(workspaceId, repoId, group1Id, "税率一致性",
                "校验发票各行商品的税率是否与采购合同中约定的该商品/服务适用税率一致。"
                + "若合同未约定具体税率，则跳过校验。若发票存在多行，要求每一行的税率均与合同约定相符。",
                Arrays.asList(invoiceId, contractId), 20);
        createRule(workspaceId, repoId, group1Id, "验收结论校验",
                "验收单的验收结论必须为{合格，通过，验收通过，同意验收}或类似认可状态。",
                Arrays.asList(acceptanceId), 20);
        createRule(workspaceId, repoId, group1Id, "数量一致性（验收单维度）",
                "若发票包含商品明细，则发票数量合计 ≤ 验收单中的合格数量合计。"
                + "验收单如无明确列明合格数量，则忽视该条审核规则。",
                Arrays.asList(invoiceId, acceptanceId), 20);
        createRule(workspaceId, repoId, group1Id, "合同关联性",
                "入库单【合同编号】= 采购合同【编号】；验收单【合同编号】= 采购合同【编号】",
                Arrays.asList(contractId, acceptanceId, inboundId), 20);

        // 规则组2：文档采集与预处理审核
        String group2Id = createRuleGroup(workspaceId, repoId, "文档采集与预处理审核");
        createRule(workspaceId, repoId, group2Id, "信息完整性校验",
                "检查文档是否齐全（入库单、验收单、发票、采购合同），且每一文档的必填字段非空。\n"
                + "必填字段清单：\n"
                + "采购合同：合同编号、签订日期、合同总金额（框架协议可为空）、甲方名称、乙方名称；\n"
                + "发票：发票号码、开票日期、价税合计金额、销售方名称、销售方纳税人识别号、购买方名称、购买方纳税人识别号；\n"
                + "入库单：收货日期、对应合同号、物料编码、物料描述、应收、实收、供应商名称；\n"
                + "验收单：验收日期、对应合同号（或PO号）、供应商名称、验收结论（合格/不合格）。",
                Arrays.asList(invoiceId, contractId, acceptanceId, inboundId), 20);
        createRule(workspaceId, repoId, group2Id, "发票日期合规性",
                "发票【开票日期】≥ 合同【签订日期】",
                Arrays.asList(invoiceId, contractId), 20);
        createRule(workspaceId, repoId, group2Id, "购买方信息匹配",
                "发票【购买方名称】= 本企业工商登记名称（上海合合信息科技股份有限公司）\n"
                + "发票【购买方纳税人识别号】= 本企业税号（91310110791485269J）",
                Arrays.asList(invoiceId), 10);
        createRule(workspaceId, repoId, group2Id, "税率合规性校验",
                "校验发票税率与开票项目的匹配性：货物类应为13%，服务类应为6%，小规模纳税人应为1%或3%。",
                Arrays.asList(invoiceId), 20);

        // 步骤 6：提交审核任务
        List<String> extractTaskIds = new ArrayList<>();
        for (JsonObject r : rawResults) {
            if (r.has("task_id") && !r.get("task_id").isJsonNull()) {
                extractTaskIds.add(r.get("task_id").getAsString());
            }
        }
        String ts = new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
        String reviewTaskId = submitReviewTask(workspaceId, "AP审核_" + ts, repoId, extractTaskIds);

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
