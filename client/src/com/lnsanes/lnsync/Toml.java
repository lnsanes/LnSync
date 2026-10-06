package com.lnsanes.lnsync;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Minimal TOML reader for instance `lnsync.toml`. */
final class Toml {
    private Toml() {}

    static Map<String, Object> load(Path path) throws Exception {
        return parse(Files.readString(path));
    }

    static Map<String, Object> parse(String text) {
        if (text != null && !text.isEmpty() && text.charAt(0) == '\uFEFF') {
            text = text.substring(1);
        }
        Map<String, Object> root = new LinkedHashMap<>();
        Map<String, Object> current = root;
        for (String raw : text.split("\n")) {
            String line = stripComment(raw).trim();
            if (line.isEmpty()) {
                continue;
            }
            if (line.startsWith("[") && line.endsWith("]") && !line.startsWith("[[")) {
                current = table(root, line.substring(1, line.length() - 1).trim());
                continue;
            }
            int eq = line.indexOf('=');
            if (eq < 0) {
                continue;
            }
            current.put(line.substring(0, eq).trim(), scalar(line.substring(eq + 1).trim()));
        }
        return root;
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> table(Map<String, Object> root, String name) {
        Map<String, Object> cursor = root;
        for (String part : name.split("\\.")) {
            Object existing = cursor.get(part);
            if (!(existing instanceof Map<?, ?>)) {
                Map<String, Object> next = new LinkedHashMap<>();
                cursor.put(part, next);
                cursor = next;
            } else {
                cursor = (Map<String, Object>) existing;
            }
        }
        return cursor;
    }

    static String str(Map<String, Object> object, String key, String fallback) {
        Object value = object.get(key);
        return value == null ? fallback : String.valueOf(value);
    }

    private static Object scalar(String raw) {
        if (raw.startsWith("\"") && raw.endsWith("\"") && raw.length() >= 2) {
            return raw.substring(1, raw.length() - 1)
                    .replace("\\\"", "\"")
                    .replace("\\\\", "\\");
        }
        if ("true".equals(raw) || "false".equals(raw)) {
            return Boolean.parseBoolean(raw);
        }
        try {
            if (raw.contains(".")) {
                return Double.parseDouble(raw);
            }
            return Long.parseLong(raw);
        } catch (Exception ignored) {
            return raw;
        }
    }

    private static String stripComment(String line) {
        boolean inString = false;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"' && (i == 0 || line.charAt(i - 1) != '\\')) {
                inString = !inString;
            } else if (ch == '#' && !inString) {
                return line.substring(0, i);
            }
        }
        return line;
    }
}
