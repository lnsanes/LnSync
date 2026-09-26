package com.lnsanes.lnsync;

import javax.swing.JOptionPane;
import java.awt.GraphicsEnvironment;
import java.lang.management.ManagementFactory;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

/**
 * Client-side gate: when this jar is loaded as a Minecraft mod, pull files
 * from the update server before / while the game starts.
 */
public final class LaunchHook {
    private LaunchHook() {}

    public static void markEarly() {
        System.setProperty("lnsync.early", "true");
    }

    public static void clientGate() {
        if (Boolean.getBoolean("lnsync.client.done")) {
            return;
        }
        if (isDedicatedServer()) {
            return;
        }
        synchronized (LaunchHook.class) {
            if (Boolean.getBoolean("lnsync.client.done")) {
                return;
            }
            try {
                runClientGate();
                System.setProperty("lnsync.client.done", "true");
            } catch (Exception error) {
                System.err.println("[LnSync] 客户端更新失败: " + error.getMessage());
                error.printStackTrace();
            }
        }
    }

    private static void runClientGate() throws Exception {
        Path instance = instanceDir();
        List<String> servers = candidateServers(instance);
        System.out.println("[LnSync] 实例目录 " + instance);
        log(instance, "实例目录 " + instance);
        Exception last = null;
        for (int attempt = 0; attempt < 8; attempt++) {
            for (String server : servers) {
                try {
                    System.out.println("[LnSync] 检查更新 " + server);
                    log(instance, "检查更新 " + server);
                    Sync.Client client = new Sync.Client(server, "client", instance, updateToken(instance));
                    Sync.Check check = Sync.inspect(instance, "client", client);
                    if (!check.needed) {
                        System.out.println("[LnSync] 客户端已是最新，直接进入游戏。");
                        log(instance, "已是最新");
                        return;
                    }
                    System.out.println("[LnSync] 发现文件改动，正在同步。");
                    log(instance, "需要更新，连接 " + server);
                    Sync.Result result = Sync.apply(instance, "client", client, line -> {
                        System.out.println("[LnSync] " + line);
                        log(instance, line);
                    }, false);
                    boolean early = Boolean.getBoolean("lnsync.early");
                    if (result != null && result.changed && check.modsChanged && !early) {
                        System.out.println("[LnSync] 模组文件已更新，请再次点击启动游戏。");
                        System.exit(0);
                    }
                    return;
                } catch (Exception error) {
                    last = error;
                    System.err.println("[LnSync] " + server + " 失败: " + error.getMessage());
                    log(instance, server + " 失败: " + error.getMessage());
                }
            }
            if (GraphicsEnvironment.isHeadless()) {
                break;
            }
            int choice = JOptionPane.showConfirmDialog(null,
                    "无法连接 LnSync 更新服务器。\n实例: " + instance + "\n地址: " + String.join(" ， ", servers)
                            + (last == null ? "" : "\n原因: " + last.getMessage())
                            + "\n\n请先启动更新服务器，然后点「是」重试。\n点「否」将带着缺文件继续启动。",
                    "LnSync", JOptionPane.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE);
            if (choice != JOptionPane.YES_OPTION) {
                return;
            }
        }
        if (last != null) {
            throw last;
        }
    }

    static Path instanceDir() throws Exception {
        List<Path> candidates = new ArrayList<>();
        Path jar = updaterJar();
        if (jar != null && jar.getParent() != null && "mods".equalsIgnoreCase(jar.getParent().getFileName().toString())) {
            candidates.add(jar.getParent().getParent());
        }
        Path gameDir = argumentValue("--gameDir", "--gameDir=");
        if (gameDir != null) {
            candidates.add(gameDir);
        }
        Path cwd = Path.of("").toAbsolutePath();
        Path current = cwd;
        for (int i = 0; i < 8; i++) {
            candidates.add(current);
            Path parent = current.getParent();
            if (parent == null) {
                break;
            }
            current = parent;
        }
        for (Path candidate : candidates) {
            if (candidate != null && Files.isRegularFile(candidate.resolve("lnsync.toml"))) {
                return configuredInstance(candidate);
            }
        }
        if (gameDir != null) {
            return configuredInstance(gameDir);
        }
        return configuredInstance(cwd);
    }

    private static Path configuredInstance(Path instance) throws Exception {
        Path configFile = instance.resolve("lnsync.toml");
        if (Files.isRegularFile(configFile)) {
            Map<String, Object> config = Toml.load(configFile);
            String instanceDir = Toml.str(config, "instance_dir", "");
            if (!instanceDir.isBlank() && !".".equals(instanceDir)) {
                Path configured = Path.of(instanceDir);
                instance = configured.isAbsolute() ? configured : instance.resolve(configured).normalize();
            }
        }
        return instance.toAbsolutePath().normalize();
    }

    static List<String> candidateServers(Path instance) throws Exception {
        LinkedHashSet<String> urls = new LinkedHashSet<>();
        String configured = updateServer(instance);
        int port = 8765;
        if (configured != null && !configured.isBlank()) {
            configured = Net.normalizeHttpBase(configured);
            if (configured.endsWith("/")) {
                configured = configured.substring(0, configured.length() - 1);
            }
            urls.add(configured);
            try {
                URI uri = URI.create(configured);
                if (uri.getPort() > 0) {
                    port = uri.getPort();
                }
            } catch (Exception ignored) {
                // keep default
            }
        }
        urls.add("http://127.0.0.1:" + port);
        urls.add("http://localhost:" + port);
        return new ArrayList<>(urls);
    }

    static String updateServer(Path instance) throws Exception {
        String server = "http://127.0.0.1:8765";
        Path configFile = instance.resolve("lnsync.toml");
        if (Files.isRegularFile(configFile)) {
            Map<String, Object> config = Toml.load(configFile);
            server = Toml.str(config, "update_server", server);
        }
        return server;
    }

    static String updateToken(Path instance) {
        try {
            Path configFile = instance.resolve("lnsync.toml");
            if (Files.isRegularFile(configFile)) {
                return Toml.str(Toml.load(configFile), "update_token", "");
            }
        } catch (Exception ignored) {
            // no token
        }
        return "";
    }

    static Path updaterJar() {
        Path direct = jarFile(LaunchHook.class.getProtectionDomain().getCodeSource().getLocation());
        if (direct != null) {
            return direct;
        }
        try {
            java.net.URL resource = LaunchHook.class.getResource("LaunchHook.class");
            if (resource != null) {
                String text = resource.toString();
                int bang = text.indexOf("!/");
                if (text.startsWith("jar:") && bang > 4) {
                    return jarFile(java.net.URI.create(text.substring(4, bang)).toURL());
                }
            }
        } catch (Exception ignored) {
            // fall through
        }
        return null;
    }

    static Path updaterJar(Path instanceDir) {
        Path found = updaterJar();
        if (found != null) {
            return found;
        }
        if (instanceDir == null) {
            return null;
        }
        Path mods = instanceDir.resolve("mods");
        String[] names = {
                "lnsync.jar",
                "lnsync-universal.jar",
                "lnsync-forge.jar",
                "lnsync-neoforge.jar",
                "lnsync-fabric.jar",
                "lnsync-quilt.jar"
        };
        for (String name : names) {
            Path candidate = mods.resolve(name).toAbsolutePath();
            if (Files.isRegularFile(candidate)) {
                return candidate;
            }
        }
        try (var stream = Files.list(mods)) {
            return stream
                    .filter(path -> {
                        String name = path.getFileName().toString().toLowerCase();
                        return name.startsWith("lnsync") && name.endsWith(".jar") && Files.isRegularFile(path);
                    })
                    .map(Path::toAbsolutePath)
                    .findFirst()
                    .orElse(null);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static Path jarFile(java.net.URL location) {
        if (location == null) {
            return null;
        }
        try {
            Path path = Path.of(location.toURI());
            if (Files.isRegularFile(path) && path.getFileName().toString().toLowerCase().endsWith(".jar")) {
                return path.toAbsolutePath();
            }
        } catch (Exception ignored) {
            // not a plain file URL
        }
        return null;
    }

    static Path argumentValue(String... keys) {
        List<String> args = new ArrayList<>();
        String command = System.getProperty("sun.java.command", "");
        if (!command.isBlank()) {
            for (String part : command.split(" ")) {
                if (!part.isBlank()) {
                    args.add(part);
                }
            }
        }
        try {
            ProcessHandle.current().info().arguments().ifPresent(items -> args.addAll(List.of(items)));
        } catch (Exception ignored) {
            // keep property args
        }
        for (int i = 0; i < args.size(); i++) {
            String arg = args.get(i);
            for (String key : keys) {
                if (key.endsWith("=") && arg.startsWith(key)) {
                    return Path.of(arg.substring(key.length())).toAbsolutePath().normalize();
                }
                if (key.equals(arg) && i + 1 < args.size()) {
                    return Path.of(args.get(i + 1)).toAbsolutePath().normalize();
                }
            }
        }
        return null;
    }

    static boolean isDedicatedServer() {
        if (Boolean.getBoolean("lnsync.forceClient")) {
            return false;
        }
        if (Boolean.getBoolean("lnsync.forceServer")) {
            return true;
        }
        String command = System.getProperty("sun.java.command", "").toLowerCase();
        if (command.contains("forgeserver") || command.contains("minecraftserver") || command.contains("nogui")) {
            return true;
        }
        String joined = String.join(" ", ManagementFactory.getRuntimeMXBean().getInputArguments()).toLowerCase();
        return joined.contains("fml.dist=dedicated") || joined.contains("forge.launch.dist=server");
    }

    private static void log(Path instance, String line) {
        try {
            Path logFile = instance.resolve("logs").resolve("lnsync.log");
            Files.createDirectories(logFile.getParent());
            Files.writeString(logFile, line + System.lineSeparator(),
                    java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
        } catch (Exception ignored) {
            // keep going
        }
    }
}
