package com.lnsanes.lnsync;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Base64;
import java.util.Map;
import java.util.UUID;

/** Minimal server-side identity helpers (no Forge agent). */
final class Connections {
    private Connections() {}

    static String ensureInstanceId(Path instance) throws Exception {
        Map<String, Object> state = Sync.loadState(instance);
        String id = Json.str(state, "instance_id");
        if (!id.isBlank()) {
            return id;
        }
        id = UUID.randomUUID().toString();
        state.put("instance_id", id);
        Sync.writeState(instance, state);
        return id;
    }

    static String localHostname() {
        try {
            return java.net.InetAddress.getLocalHost().getHostName();
        } catch (Exception ignored) {
            return "";
        }
    }

    static String encodePath(String path) {
        if (path == null || path.isBlank()) {
            return "";
        }
        return Base64.getEncoder().encodeToString(path.getBytes(StandardCharsets.UTF_8));
    }
}
