package com.docflow;

import com.google.gson.*;
import okhttp3.*;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * TextIn 智能文档抽取 API 示例
 *
 * <p>演示两种抽取模式：
 * <ol>
 *   <li>Prompt 模式：提供自然语言 prompt，由大模型理解并自由抽取</li>
 *   <li>字段模式：提供结构化的字段列表，进行精确可控抽取</li>
 * </ol>
 *
 * <p>依赖：OkHttp 4.x、Gson（见 pom.xml）
 *
 * <p>运行方式：
 * <pre>
 *   cd examples/java
 *   mvn clean package -q
 *   java -cp target/docflow-examples-1.0.0.jar com.docflow.EntityExtraction &lt;文件路径&gt;
 * </pre>
 */
public class EntityExtraction {

    // ============================================================
    // 配置项 — 请替换为您的实际值
    // ============================================================
    private static final String APP_ID      = "your-app-id";       // x-ti-app-id
    private static final String SECRET_CODE = "your-secret-code";  // x-ti-secret-code

    private static final String API_URL = "https://api.textin.com/ai/service/v2/entity_extraction";

    // ============================================================
    // 全局工具对象
    // ============================================================
    private static final OkHttpClient HTTP = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build();

    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static final MediaType JSON_TYPE = MediaType.get("application/json; charset=utf-8");

    // ============================================================
    // 工具辅助函数
    // ============================================================

    /** 构造鉴权请求头。 */
    private static Headers authHeaders() {
        return new Headers.Builder()
                .add("x-ti-app-id", APP_ID)
                .add("x-ti-secret-code", SECRET_CODE)
                .build();
    }

    /** 读取本地文件并转为 base64 字符串。 */
    private static String encodeFile(String filePath) throws IOException {
        byte[] bytes = Files.readAllBytes(new File(filePath).toPath());
        return Base64.getEncoder().encodeToString(bytes);
    }

    /**
     * 调用智能文档抽取 API。
     *
     * @param filePath    待抽取的本地文件路径
     * @param body        请求体（不含 file 字段）
     * @param urlParams   URL 参数，例如 {"parse_mode": "scan"}
     * @return 解析后的 JSON 响应
     * @throws IOException          网络或文件读取异常
     * @throws RuntimeException     API 返回非 200 错误码时抛出
     */
    private static JsonObject callApi(String filePath, JsonObject body, Map<String, String> urlParams)
            throws IOException {
        body.addProperty("file", encodeFile(filePath));

        HttpUrl.Builder urlBuilder = Objects.requireNonNull(HttpUrl.parse(API_URL)).newBuilder();
        if (urlParams != null) {
            urlParams.forEach(urlBuilder::addQueryParameter);
        }

        Request req = new Request.Builder()
                .url(urlBuilder.build())
                .headers(authHeaders())
                .post(RequestBody.create(GSON.toJson(body), JSON_TYPE))
                .build();

        try (Response resp = HTTP.newCall(req).execute()) {
            String respBody = resp.body().string();
            JsonObject result = JsonParser.parseString(respBody).getAsJsonObject();
            if (result.get("code").getAsInt() != 200) {
                throw new RuntimeException("API 错误 " + result.get("code") + "："
                        + result.get("message").getAsString());
            }
            return result;
        }
    }

    // ============================================================
    // 示例 1：Prompt 模式
    // ============================================================

    public static void demoPromptMode(String filePath) throws IOException {
        System.out.println("=".repeat(60));
        System.out.println("示例 1：Prompt 模式");
        System.out.println("=".repeat(60));

        JsonObject body = new JsonObject();
        body.addProperty("prompt", "请抽取文件中的所有关键字段，以 JSON 格式返回");

        Map<String, String> params = new HashMap<>();
        params.put("parse_mode", "scan");

        JsonObject result = callApi(filePath, body, params);
        JsonObject res = result.getAsJsonObject("result");

        // llm_json：大模型直接返回的键值对，方便直接使用
        JsonElement llmJson = res.get("llm_json");
        System.out.println("\n抽取结果 (llm_json)：");
        System.out.println(GSON.toJson(llmJson));

        // usage：token 消耗统计
        JsonObject usage = res.getAsJsonObject("usage");
        if (usage != null) {
            System.out.printf("%nToken 消耗：输入 %d，输出 %d，合计 %d%n",
                    usage.get("prompt_tokens").getAsInt(),
                    usage.get("completion_tokens").getAsInt(),
                    usage.get("total_tokens").getAsInt());
        }
    }

    // ============================================================
    // 示例 2：字段模式
    // ============================================================

    public static void demoFieldMode(String filePath) throws IOException {
        System.out.println("=".repeat(60));
        System.out.println("示例 2：字段模式");
        System.out.println("=".repeat(60));

        JsonObject body = new JsonObject();

        // fields：要抽取的单值字段列表
        JsonArray fields = new JsonArray();
        for (String name : new String[]{"发票号码", "开票日期", "购买方名称", "销售方名称", "合计金额"}) {
            JsonObject f = new JsonObject();
            f.addProperty("name", name);
            fields.add(f);
        }
        body.add("fields", fields);

        // table_fields：要抽取的表格字段（可选）
        JsonArray tableFields = new JsonArray();
        JsonObject table = new JsonObject();
        table.addProperty("title", "货物明细");
        table.addProperty("description", "发票中的货物或服务明细表格");
        JsonArray tableCols = new JsonArray();
        for (String col : new String[]{"项目名称", "数量", "单价", "金额"}) {
            JsonObject c = new JsonObject();
            c.addProperty("name", col);
            tableCols.add(c);
        }
        table.add("fields", tableCols);
        tableFields.add(table);
        body.add("table_fields", tableFields);

        Map<String, String> params = new HashMap<>();
        params.put("parse_mode", "scan");

        JsonObject result = callApi(filePath, body, params);
        JsonObject res = result.getAsJsonObject("result");

        // details：字段抽取结果
        JsonObject details = res.getAsJsonObject("details");
        System.out.println("\n抽取结果 (details)：");
        if (details != null) {
            for (Map.Entry<String, JsonElement> entry : details.entrySet()) {
                if ("row".equals(entry.getKey())) {
                    JsonArray rows = entry.getValue().getAsJsonArray();
                    System.out.println("  表格（货物明细）：共 " + rows.size() + " 行");
                    for (int i = 0; i < rows.size(); i++) {
                        System.out.println("    第 " + (i + 1) + " 行：" + rows.get(i));
                    }
                } else if (entry.getValue().isJsonObject()) {
                    String val = entry.getValue().getAsJsonObject().get("value").getAsString();
                    System.out.println("  " + entry.getKey() + "：" + val);
                }
            }
        }

        System.out.println("\n处理页数：" + res.get("page_count").getAsInt());
        System.out.println("推理时间：" + result.get("duration").getAsInt() + " ms");
    }

    // ============================================================
    // 入口
    // ============================================================

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.out.println("用法：java EntityExtraction <文件路径>");
            System.out.println("示例：java EntityExtraction invoice.pdf");
            System.exit(1);
        }

        String filePath = args[0];
        if (!new File(filePath).exists()) {
            System.out.println("文件不存在：" + filePath);
            System.exit(1);
        }

        demoPromptMode(filePath);
        System.out.println();
        demoFieldMode(filePath);
    }
}
