package com.docflow;

import com.google.gson.*;
import okhttp3.*;

import java.io.File;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * DocFlow 费用报销场景示例
 *
 * <p>完整演示从零开始的业务流程：
 * <ol>
 *   <li>创建工作空间</li>
 *   <li>创建文件类别（含样本文件和字段配置）</li>
 *   <li>上传待分类抽取的文件</li>
 *   <li>轮询获取处理结果，展示分类与抽取结果</li>
 * </ol>
 *
 * <p>依赖：OkHttp 4.x、Gson（见 pom.xml）
 */
public class ExpenseReimbursement {

    // ============================================================
    // 配置项 — 请替换为您的实际值
    // ============================================================
    private static final String APP_ID      = "your-app-id";       // x-ti-app-id
    private static final String SECRET_CODE = "your-secret-code";  // x-ti-secret-code
    private static final long   ENTERPRISE_ID = 0L;                // 企业组织 ID

    private static final String BASE_URL = "https://docflow.textin.com";

    // 样本文件目录（相对 examples/ 根目录）
    private static final String SAMPLE_DIR =
            resolveDir("../sample_files/费用报销");

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
    // 辅助方法
    // ============================================================

    private static Headers authHeaders() {
        return new Headers.Builder()
                .add("x-ti-app-id", APP_ID)
                .add("x-ti-secret-code", SECRET_CODE)
                .build();
    }

    /**
     * 校验响应 code，不为 200 时抛出异常；否则返回整个 JSON 对象。
     */
    private static JsonObject checkResponse(String body, String action) {
        JsonObject obj = JsonParser.parseString(body).getAsJsonObject();
        if (obj.get("code").getAsInt() != 200) {
            throw new RuntimeException(action + " 失败: " + body);
        }
        return obj;
    }

    /** 根据文件扩展名返回 MIME 类型。 */
    private static String mimeType(String filename) {
        String lower = filename.toLowerCase();
        if (lower.endsWith(".png"))  return "image/png";
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".xls"))  return "application/vnd.ms-excel";
        if (lower.endsWith(".xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
        if (lower.endsWith(".pdf"))  return "application/pdf";
        return "application/octet-stream";
    }

    /** 构造一个仅含 name 的字段 Map（用于 fields 列表）。 */
    private static Map<String, String> field(String name) {
        Map<String, String> m = new LinkedHashMap<>();
        m.put("name", name);
        return m;
    }

    /** 将相对路径解析为绝对路径（基于本 class 文件所在 jar 的上级目录）。 */
    private static String resolveDir(String relative) {
        // 运行时以 java/ 目录为工作目录
        return new File(relative).getAbsolutePath();
    }

    // ============================================================
    // 步骤 1：创建工作空间
    // ============================================================

    /**
     * 创建工作空间。
     *
     * @return workspace_id
     */
    public static String createWorkspace(String name, String description) throws IOException {
        String url = BASE_URL + "/api/app-api/sip/platform/v2/workspace/create";

        JsonObject payload = new JsonObject();
        payload.addProperty("name", name);
        payload.addProperty("description", description);
        payload.addProperty("enterprise_id", ENTERPRISE_ID);
        payload.addProperty("auth_scope", 0); // 0: 仅自己可见

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
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
    // ============================================================

    /**
     * 创建文件类别，同时上传样本文件并配置字段。
     *
     * @param fields          字段列表，每个元素为 {"name": "字段名"}
     * @param categoryPrompt  分类提示词（可选）
     * @return category_id
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
                .addFormDataPart("extract_model",   "llm")
                .addFormDataPart("category_prompt", categoryPrompt)
                // fields 以 JSON 字符串形式传递
                .addFormDataPart("fields",          GSON.toJson(fields))
                .addFormDataPart("sample_files",    sampleFile.getName(),
                        RequestBody.create(sampleFile, MediaType.get(mimeType(sampleFile.getName()))))
                .build();

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
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
    // 步骤 2b：追加字段（可选）
    // ============================================================

    /**
     * 在已有类别中追加一个字段。
     *
     * <p>如需创建「表格字段」，先通过 listCategoryFields 接口获取 table_id，
     * 再传入 tableId 参数；传 null 则创建普通字段。
     *
     * @return field_id
     */
    public static String addCategoryField(
            String workspaceId,
            String categoryId,
            String fieldName,
            String tableId) throws IOException {

        String url = BASE_URL + "/api/app-api/sip/platform/v2/category/fields/add";

        JsonObject payload = new JsonObject();
        payload.addProperty("workspace_id", workspaceId);
        payload.addProperty("category_id",  categoryId);
        payload.addProperty("name",         fieldName);
        if (tableId != null && !tableId.isEmpty()) {
            payload.addProperty("table_id", tableId);
        }

        Request req = new Request.Builder()
                .url(url)
                .headers(authHeaders())
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
    // ============================================================

    /**
     * 上传文件至指定工作空间。
     *
     * @return batch_number
     */
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
                .url(url)
                .headers(authHeaders())
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
    // 步骤 4：轮询等待处理结果
    // ============================================================

    /**
     * 轮询直至文件识别完成，返回文件结果对象。
     *
     * <p>recognition_status: 0=待识别, 1=成功, 2=失败
     *
     * @param timeoutSec  最长等待秒数
     * @param intervalSec 轮询间隔秒数
     */
    public static JsonObject waitForResult(
            String workspaceId,
            String batchNumber,
            int timeoutSec,
            int intervalSec) throws IOException, InterruptedException {

        HttpUrl url = HttpUrl.parse(BASE_URL + "/api/app-api/sip/platform/v2/file/fetch")
                .newBuilder()
                .addQueryParameter("workspace_id", workspaceId)
                .addQueryParameter("batch_number",  batchNumber)
                .build();

        long deadline = System.currentTimeMillis() + (long) timeoutSec * 1000;
        System.out.print("[步骤4] 等待处理结果（batch_number=" + batchNumber + "）...");

        while (System.currentTimeMillis() < deadline) {
            Request req = new Request.Builder()
                    .url(url)
                    .headers(authHeaders())
                    .get()
                    .build();

            try (Response resp = HTTP.newCall(req).execute()) {
                JsonObject data = checkResponse(resp.body().string(), "获取处理结果");
                JsonArray files = data.getAsJsonObject("result").getAsJsonArray("files");
                if (files != null && files.size() > 0) {
                    JsonObject file = files.get(0).getAsJsonObject();
                    int status = file.get("recognition_status").getAsInt();
                    if (status == 1) {
                        System.out.println(" 完成");
                        return file;
                    } else if (status == 2) {
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
    // 展示分类与抽取结果
    // ============================================================

    /** 格式化输出文件的分类结果和字段抽取结果。 */
    public static void displayResult(JsonObject fileResult) {
        System.out.println("\n" + "=".repeat(60));
        System.out.println("文件名   : " + str(fileResult, "name"));
        System.out.println("分类结果 : " + str(fileResult, "category", "未分类"));

        if (!fileResult.has("data") || fileResult.get("data").isJsonNull()) return;
        JsonObject data = fileResult.getAsJsonObject("data");

        // 普通字段
        JsonArray fields = jsonArray(data, "fields");
        if (fields != null && fields.size() > 0) {
            System.out.println("\n── 普通字段 ──────────────────────────");
            for (JsonElement e : fields) {
                JsonObject f = e.getAsJsonObject();
                System.out.printf("  %-20s: %s%n", str(f, "key"), str(f, "value"));
            }
        }

        // 表格行（系统自动识别的 items，行×列 二维数组）
        JsonArray items = jsonArray(data, "items");
        if (items != null && items.size() > 0) {
            System.out.println("\n── 表格行数据 ────────────────────────");
            for (int i = 0; i < items.size(); i++) {
                JsonArray row = items.get(i).getAsJsonArray();
                StringBuilder sb = new StringBuilder("  第").append(i + 1).append("行: ");
                for (int j = 0; j < row.size(); j++) {
                    JsonObject cell = row.get(j).getAsJsonObject();
                    if (j > 0) sb.append("  |  ");
                    sb.append(str(cell, "key")).append("=").append(str(cell, "value"));
                }
                System.out.println(sb);
            }
        }

        // 配置表格（tables，含手动配置的表格字段）
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
    // 主流程
    // ============================================================
    public static void main(String[] args) throws Exception {
        System.out.println("=".repeat(60));
        System.out.println("  DocFlow 费用报销场景示例");
        System.out.println("=".repeat(60));

        // ----------------------------------------------------------
        // 步骤 1：创建工作空间
        // ----------------------------------------------------------
        String workspaceId = createWorkspace("费用报销", "费用报销单据自动化处理空间");

        // ----------------------------------------------------------
        // 步骤 2：创建文件类别（含样本和字段）
        // ----------------------------------------------------------

        // 2.1 报销申请单
        String baoxiaoId = createCategory(
                workspaceId, "报销申请单",
                SAMPLE_DIR + "/报销申请单.XLS",
                Arrays.asList(
                        field("申请人"), field("出差目的"), field("报销期间"),
                        field("目的地"), field("费用发生日期"), field("费用项目"),
                        field("差旅费金额"), field("税率"), field("冲借款金额"),
                        field("申请付款金额"), field("备注"), field("税额")
                ),
                ""
        );

        // 2.2 酒店水单（普通字段 + 消费明细表格字段）
        String hotelId = createCategory(
                workspaceId, "酒店水单",
                SAMPLE_DIR + "/酒店水单.png",
                Arrays.asList(
                        field("入住日期"), field("离店日期"), field("总金额")
                ),
                ""
        );
        // 追加表格字段
        // 说明：如需将以下字段挂载到特定表格下，先调用
        //   GET /category/fields/list 取得 table_id，再作为第 4 个参数传入。
        for (String fn : new String[]{"日期", "费用类型", "金额", "备注"}) {
            addCategoryField(workspaceId, hotelId, fn, "-1");
        }

        // 2.3 支付记录
        String paymentId = createCategory(
                workspaceId, "支付记录",
                SAMPLE_DIR + "/支付记录.png",
                Arrays.asList(
                        field("交易流水号"), field("交易授权码"), field("付款卡种"),
                        field("收款方户名"), field("付款方户名"), field("交易时间"),
                        field("备注"), field("收款方账户"), field("收款方银行"),
                        field("交易金额"), field("交易描述"), field("付款银行"),
                        field("币种"), field("交易账号/支付方式")
                ),
                ""
        );

        System.out.println("\n配置完成  workspace_id=" + workspaceId);
        System.out.println("  报销申请单: category_id=" + baoxiaoId);
        System.out.println("  酒店水单:   category_id=" + hotelId);
        System.out.println("  支付记录:   category_id=" + paymentId);

        // ----------------------------------------------------------
        // 步骤 3：上传待处理文件
        // ----------------------------------------------------------
        System.out.println("\n开始上传待处理文件...");
        String[] sampleFiles = {
                SAMPLE_DIR + "/报销申请单.XLS",
                SAMPLE_DIR + "/酒店水单.png",
                SAMPLE_DIR + "/支付记录.png"
        };
        List<String> batchNumbers = new ArrayList<>();
        for (String path : sampleFiles) {
            batchNumbers.add(uploadFile(workspaceId, path));
        }

        // ----------------------------------------------------------
        // 步骤 4：获取并展示结果
        // ----------------------------------------------------------
        System.out.println("\n开始获取处理结果...");
        for (String batchNumber : batchNumbers) {
            try {
                JsonObject result = waitForResult(workspaceId, batchNumber, 120, 3);
                displayResult(result);
            } catch (Exception e) {
                System.err.println("  异常: " + e.getMessage());
            }
        }

        System.out.println("\n" + "=".repeat(60));
        System.out.println("  示例运行完成");
        System.out.println("=".repeat(60));
    }

    // ============================================================
    // 私有工具方法
    // ============================================================

    private static String str(JsonObject obj, String key) {
        return str(obj, key, "");
    }

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
