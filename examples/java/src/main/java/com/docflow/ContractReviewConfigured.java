package com.docflow;

import com.google.gson.*;
import okhttp3.*;

import java.io.File;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * DocFlow 合同审核场景示例（已完成配置版）
 *
 * <p>适用于工作空间、文件类别、审核规则库均已配置完毕的场景。
 * <ol>
 *   <li>上传待审核合同文件</li>
 *   <li>轮询获取抽取结果，展示字段抽取结果</li>
 *   <li>提交审核任务</li>
 *   <li>轮询获取审核结果，展示审核结论</li>
 * </ol>
 *
 * <p>依赖：OkHttp 4.x、Gson（见 pom.xml）
 */
public class ContractReviewConfigured {

    // ============================================================
    // 配置项 — 请替换为您的实际值
    // ============================================================
    private static final String APP_ID        = "your-app-id";        // x-ti-app-id
    private static final String SECRET_CODE   = "your-secret-code";   // x-ti-secret-code

    private static final String WORKSPACE_ID = "your-workspace-id";  // 已创建的工作空间 ID
    private static final String REPO_ID      = "your-repo-id";       // 已配置的审核规则库 ID

    private static final String BASE_URL = "https://docflow.textin.com";

    // 待处理文件目录
    private static final String FILES_DIR =
            new File("../sample_files/contract_review").getAbsolutePath();

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

    // ============================================================
    // 批量追加字段
    // REST API: POST /api/app-api/sip/platform/v2/category/fields/batch_add
    // ============================================================

    /**
     * 在已有类别中批量追加字段。
     *
     * @param tableId    若要创建表格字段，传入 "-1" 表示默认表格；否则传 null。
     * @param fieldNames 字段名列表
     * @return field_ids 列表
     */
    public static List<String> batchAddCategoryFields(
            String workspaceId,
            String categoryId,
            String tableId,
            List<String> fieldNames) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/fields/batch_add";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("category_id",  categoryId);
        if (tableId != null && !tableId.isEmpty()) {
            payload.addProperty("table_id", tableId);
        }
        JsonArray fieldsArr = new JsonArray();
        for (String fn : fieldNames) {
            JsonObject f = new JsonObject();
            f.addProperty("name", fn);
            fieldsArr.add(f);
        }
        payload.add("fields", fieldsArr);

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "批量追加字段");
            JsonArray resultArr = data.getAsJsonArray("result");
            List<String> fieldIds = new ArrayList<>();
            for (JsonElement e : resultArr) {
                fieldIds.add(e.getAsJsonObject().get("field_id").getAsString());
            }
            System.out.println("  批量追加字段成功  count=" + fieldNames.size() + "  field_ids=" + fieldIds);
            return fieldIds;
        }
    }

    // ============================================================
    // 批量更新字段
    // REST API: POST /api/app-api/sip/platform/v2/category/fields/batch_update
    // ============================================================

    /**
     * 批量更新已有字段的配置。
     *
     * @param fields     字段更新列表，每项须含 field_id 及要更新的属性
     * @param withDetail 是否返回更新后的完整字段信息
     * @return 更新后的字段列表（withDetail=true 时）或 null
     */
    public static JsonArray batchUpdateCategoryFields(
            String workspaceId,
            String categoryId,
            JsonArray fields,
            boolean withDetail) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/fields/batch_update";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("category_id",  categoryId);
        payload.add("fields", fields);
        payload.addProperty("with_detail", withDetail);

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "批量更新字段");
            System.out.println("  批量更新字段成功  count=" + fields.size());
            return data.has("result") && !data.get("result").isJsonNull()
                    ? data.getAsJsonArray("result") : null;
        }
    }

    // ============================================================
    // 批量新增表格（支持内嵌字段一站式创建）
    // REST API: POST /api/app-api/sip/platform/v2/category/tables/batch_add
    // ============================================================

    /**
     * 批量新增表格，支持在每个表格中内嵌 fields 一站式创建表格字段。
     *
     * @param tables     表格列表 JSON 数组
     * @param withDetail 是否返回完整详情（含字段列表）
     * @return 创建结果列表
     */
    public static JsonArray batchAddCategoryTables(
            String workspaceId,
            String categoryId,
            JsonArray tables,
            boolean withDetail) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/tables/batch_add";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("category_id",  categoryId);
        payload.add("tables", tables);
        payload.addProperty("with_detail", withDetail);

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "批量新增表格");
            JsonArray result = data.getAsJsonArray("result");
            List<String> tableIds = new ArrayList<>();
            for (JsonElement e : result) {
                tableIds.add(e.getAsJsonObject().get("table_id").getAsString());
            }
            System.out.println("  批量新增表格成功  count=" + tables.size() + "  table_ids=" + tableIds);
            return result;
        }
    }

    // ============================================================
    // 批量更新表格
    // REST API: POST /api/app-api/sip/platform/v2/category/tables/batch_update
    // ============================================================

    /**
     * 批量更新表格配置。
     *
     * @param tables     表格更新列表 JSON 数组，每项须含 table_id
     * @param withDetail 是否返回更新后的完整信息
     * @return 更新后的表格列表（withDetail=true 时）或 null
     */
    public static JsonArray batchUpdateCategoryTables(
            String workspaceId,
            String categoryId,
            JsonArray tables,
            boolean withDetail) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/tables/batch_update";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("category_id",  categoryId);
        payload.add("tables", tables);
        payload.addProperty("with_detail", withDetail);

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "批量更新表格");
            System.out.println("  批量更新表格成功  count=" + tables.size());
            return data.has("result") && !data.get("result").isJsonNull()
                    ? data.getAsJsonArray("result") : null;
        }
    }

    // ============================================================
    // 批量上传样本
    // REST API: POST /api/app-api/sip/platform/v2/category/sample/batch_upload
    // ============================================================

    /**
     * 为指定类别批量上传样本文件（最多 20 个）。
     *
     * @param filePaths 样本文件路径列表
     * @return 上传结果 JSON 对象
     */
    public static JsonObject batchUploadCategorySamples(
            String workspaceId,
            String categoryId,
            List<String> filePaths) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/sample/batch_upload";
        MultipartBody.Builder bodyBuilder = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("workspace_id", workspaceId)
                .addFormDataPart("category_id",  categoryId);

        for (String path : filePaths) {
            File f = new File(path);
            bodyBuilder.addFormDataPart("files", f.getName(),
                    RequestBody.create(f, MediaType.get(mimeType(f.getName()))));
        }

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
                .post(bodyBuilder.build())
                .build();

        OkHttpClient longHttp = HTTP.newBuilder()
                .readTimeout(120, TimeUnit.SECONDS).build();
        try (Response resp = longHttp.newCall(req).execute()) {
            JsonObject data = checkResponse(resp.body().string(), "批量上传样本");
            System.out.println("  批量上传样本成功  count=" + filePaths.size());
            return data.has("result") ? data.getAsJsonObject("result") : new JsonObject();
        }
    }

    // ============================================================
    // 批量下载样本（ZIP）
    // REST API: POST /api/app-api/sip/platform/v2/category/sample/batch_download
    // ============================================================

    /**
     * 批量下载样本文件，打包为 ZIP。不传 sampleIds 时下载全部样本。
     *
     * @param sampleIds 要下载的样本 ID 列表（可选，传 null 下载全部）
     * @param savePath  ZIP 保存路径
     * @return 保存路径
     */
    public static String batchDownloadCategorySamples(
            String workspaceId,
            String categoryId,
            List<String> sampleIds,
            String savePath) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/sample/batch_download";
        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("category_id",  categoryId);
        if (sampleIds != null && !sampleIds.isEmpty()) {
            JsonArray ids = new JsonArray();
            sampleIds.forEach(ids::add);
            payload.add("sample_ids", ids);
        }

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(payload), JSON_TYPE))
                .build();

        OkHttpClient longHttp = HTTP.newBuilder()
                .readTimeout(120, TimeUnit.SECONDS).build();
        try (Response resp = longHttp.newCall(req).execute()) {
            if (resp.code() != 200) {
                throw new RuntimeException("批量下载样本失败: HTTP " + resp.code());
            }
            byte[] bytes = resp.body().bytes();
            java.nio.file.Files.write(java.nio.file.Paths.get(savePath), bytes);
            System.out.println("  批量下载样本成功  save_path=" + savePath
                    + "  size=" + bytes.length + " bytes");
            return savePath;
        }
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
    // 步骤 1：上传待处理文件
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
            System.out.println("[步骤1] 文件上传成功  name=" + file.getName()
                    + "  batch_number=" + batchNumber);
            return batchNumber;
        }
    }

    // ============================================================
    // 步骤 2：轮询等待抽取结果
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
        System.out.print("[步骤2] 等待处理结果（batch_number=" + batchNumber + "）...");

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

    // ============================================================
    // 步骤 3：提交审核任务
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
            System.out.println("[步骤3] 审核任务提交成功  task_id=" + taskId);
            return taskId;
        }
    }

    // ============================================================
    // 步骤 4：轮询等待审核结果
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
        System.out.print("[步骤4] 等待审核结果（task_id=" + taskId + "）...");

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

    // ============================================================
    // 主流程
    // ============================================================
    public static void main(String[] args) throws Exception {
        System.out.println("=".repeat(60));
        System.out.println("  DocFlow 合同审核场景示例（已完成配置版）");
        System.out.println("=".repeat(60));
        System.out.println("工作空间: " + WORKSPACE_ID);
        System.out.println("规则库:   " + REPO_ID);

        // 步骤 1：上传待处理文件
        System.out.println("\n开始上传待处理文件...");
        String batchNumber = uploadFile(WORKSPACE_ID, FILES_DIR + "/sample_contract.docx");

        // 步骤 2：获取并展示抽取结果
        System.out.println("\n开始获取处理结果...");
        JsonObject fileResult = waitForResult(WORKSPACE_ID, batchNumber, 180, 3);
        displayResult(fileResult);

        // 步骤 3：提交审核任务
        System.out.println("\n开始审核...");
        String taskName = "合同审核_" + new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
        List<String> extractTaskIds = new ArrayList<>();
        if (fileResult.has("task_id") && !fileResult.get("task_id").isJsonNull()) {
            extractTaskIds.add(fileResult.get("task_id").getAsString());
        }
        String reviewTaskId = submitReviewTask(WORKSPACE_ID, taskName, REPO_ID, extractTaskIds);

        // 步骤 4：轮询获取审核结果
        JsonObject reviewResult = waitForReview(WORKSPACE_ID, reviewTaskId, 300, 5);
        displayReviewResult(reviewResult);
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
