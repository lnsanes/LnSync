package com.lnsanes.lnsync;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * LnSync client jar is a Minecraft mod. Double-click / bare launch is not supported.
 * Subprocess entry {@code fetch-job} is used only while the mod is syncing large packs.
 */
public final class Main {
    public static void main(String[] args) {
        Net.installJvmDefaults();
        if (args.length >= 1 && "fetch-job".equalsIgnoreCase(args[0])) {
            try {
                fetchJob();
            } catch (Exception error) {
                System.err.println(error.getMessage() == null ? error : error.getMessage());
                System.exit(1);
            }
            return;
        }
        // Internal / e2e: simulate early mod sync (same path as loader entrypoints).
        if (args.length >= 1 && "gate".equalsIgnoreCase(args[0])) {
            try {
                System.setProperty("lnsync.forceClient", "true");
                LaunchHook.markEarly();
                LaunchHook.clientGate();
            } catch (Exception error) {
                System.err.println(error.getMessage() == null ? error : error.getMessage());
                System.exit(1);
            }
            return;
        }
        System.err.println("LnSync 客户端只能作为 Minecraft 模组加载。");
        System.err.println("推荐：把 lnsync.jar（通用版）放入实例 mods/，Forge / NeoForge / Fabric / Quilt 均可。");
        System.err.println("也可使用专用包：lnsync-forge / neoforge / fabric / quilt.jar");
        System.err.println("并在实例根目录放置 lnsync.toml（update_server / update_token），用启动器开游戏。");
        System.exit(2);
    }

    private static void fetchJob() throws Exception {
        String text = new String(System.in.readAllBytes(), StandardCharsets.UTF_8);
        Map<String, Object> job = Json.object(Json.parse(text));
        if ("pack".equals(Json.str(job, "mode"))) {
            List<Map<String, Object>> jobs = new ArrayList<>();
            for (Object item : Json.array(job.get("jobs"))) {
                jobs.add(Json.object(item));
            }
            String label = Json.str(job, "label");
            int code = 0;
            try {
                Sync.Client client = new Sync.Client(Json.str(job, "server"), Json.str(job, "side"),
                        Path.of(Json.str(job, "instance")), Json.str(job, "token"));
                client.savePack(Path.of(Json.str(job, "instance")), Json.str(job, "sha256"), Json.lng(job, "size"),
                        Json.str(job, "lease"), jobs, System.out::println, Json.bool(job, "parallel"), label);
            } catch (Exception error) {
                System.err.println(error.getMessage());
                code = 1;
            }
            System.exit(code);
            return;
        }
        String url = Json.str(job, "url");
        Path dest = Path.of(Json.str(job, "dest"));
        String label = Json.str(job, "label");
        String expectSha = Json.str(job, "sha256");
        String token = Json.str(job, "token");
        long size = Json.lng(job, "size");
        if (expectSha.isBlank()) {
            throw new IllegalStateException("fetch-job 缺少 sha256");
        }
        java.net.http.HttpRequest.Builder request = java.net.http.HttpRequest.newBuilder(java.net.URI.create(url))
                .header("User-Agent", "lnsync-client")
                .timeout(java.time.Duration.ofMinutes(30));
        if (!token.isBlank()) {
            request.header("X-LnSync-Token", token);
        }
        Path partial = dest.resolveSibling(dest.getFileName() + ".lnsynctmp");
        try {
            Net.toFile(java.net.http.HttpClient.newHttpClient(), request, partial, size, label, System.out::println, true);
            if (!expectSha.isBlank()) {
                String got = Fs.sha256(partial);
                if (!Fs.sha256Hex(expectSha).equalsIgnoreCase(got)) {
                    Files.deleteIfExists(partial);
                    throw new IllegalStateException("哈希不一致 " + label);
                }
            }
            Files.createDirectories(dest.getParent());
            Files.move(partial, dest, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception error) {
            Files.deleteIfExists(partial);
            throw error;
        }
    }

    private Main() {}
}
