package com.docflow;

import com.google.gson.*;
import okhttp3.*;

import java.io.File;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * DocFlow AP 审单场景示例（已完成配置版）
 *
 * <p>适用于工作空间、文件类别、审核规则库均已配置完毕的场景。
 * <ol>
 *   <li>上传待处理文件（发票、采购合同、入库单、验收单）</li>
 *   <li>轮询获取抽取结果，展示分类与字段抽取结果</li>
 *   <li>提交审核任务</li>
 *   <li>轮询获取审核结果，展示审核结论</li>
 * </ol>
 *
 * <p>依赖：OkHttp 4.x、Gson（见 pom.xml）
 */
public class ApReviewConfigured {

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
            new File("../sample_files/AP审单").getAbsolutePath();

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
        System.out.println("  DocFlow AP 审单场景示例（已完成配置版）");
        System.out.println("=".repeat(60));
        System.out.println("工作空间: " + WORKSPACE_ID);
        System.out.println("规则库:   " + REPO_ID);

        // 步骤 1：上传待处理文件
        System.out.println("\n开始上传待处理文件...");
        String[] sampleFiles = {
                FILES_DIR + "/示例_发票.pdf",
                FILES_DIR + "/示例_采购合同.pdf",
                FILES_DIR + "/示例_入库单.pdf",
                FILES_DIR + "/示例_验收单.pdf"
        };
        List<String> batchNumbers = new ArrayList<>();
        for (String path : sampleFiles) {
            batchNumbers.add(uploadFile(WORKSPACE_ID, path));
        }

        // 步骤 2：获取并展示抽取结果
        System.out.println("\n开始获取处理结果...");
        List<JsonObject> rawResults = new ArrayList<>();
        for (String batchNumber : batchNumbers) {
            JsonObject result = waitForResult(WORKSPACE_ID, batchNumber, 120, 3);
            rawResults.add(result);
            displayResult(result);
        }

        // 步骤 3：提交审核任务
        System.out.println("\n开始审核...");
        String taskName = "AP审核_" + new SimpleDateFormat("yyyyMMdd_HHmmss").format(new Date());
        List<String> extractTaskIds = new ArrayList<>();
        for (JsonObject r : rawResults) {
            if (r.has("task_id") && !r.get("task_id").isJsonNull()) {
                extractTaskIds.add(r.get("task_id").getAsString());
            }
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
