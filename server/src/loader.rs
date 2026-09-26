use std::fs;
use std::path::Path;

/// Supported Minecraft loaders. `auto` means detect from assets / pack contents.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Loader {
    Auto,
    Forge,
    NeoForge,
    Fabric,
    Quilt,
}

impl Loader {
    pub fn parse(raw: &str) -> Self {
        match raw.trim().to_ascii_lowercase().as_str() {
            "forge" => Self::Forge,
            "neoforge" | "neo" => Self::NeoForge,
            "fabric" => Self::Fabric,
            "quilt" => Self::Quilt,
            _ => Self::Auto,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Forge => "forge",
            Self::NeoForge => "neoforge",
            Self::Fabric => "fabric",
            Self::Quilt => "quilt",
        }
    }
}

/// Resolve loader from config preference, then release asset names, then pack trees.
pub fn resolve(
    configured: &str,
    asset_names: &[String],
    pack_roots: &[&Path],
) -> Loader {
    let pref = Loader::parse(configured);
    if pref != Loader::Auto {
        return pref;
    }
    // Strong structural markers across all roots beat filename guesses.
    if let Some(hit) = detect_from_markers_multi(pack_roots) {
        return hit;
    }
    if let Some(hit) = detect_from_names(asset_names) {
        return hit;
    }
    for root in pack_roots {
        if let Some(hit) = detect_from_pack_names(root) {
            return hit;
        }
    }
    Loader::Auto
}

pub fn detect_from_names(names: &[String]) -> Option<Loader> {
    let joined = names.join(" ").to_ascii_lowercase();
    score_release_names(&joined)
}

pub fn detect_from_pack(root: &Path) -> Option<Loader> {
    if !root.is_dir() {
        return None;
    }
    if let Some(hit) = detect_from_markers(root) {
        return Some(hit);
    }
    detect_from_pack_names(root)
}

fn detect_from_markers_multi(roots: &[&Path]) -> Option<Loader> {
    // Prefer NeoForge / Quilt / Forge / Fabric by strong layout signals.
    for root in roots {
        if detect_neoforge_marker(root) {
            return Some(Loader::NeoForge);
        }
    }
    for root in roots {
        if detect_quilt_marker(root) {
            return Some(Loader::Quilt);
        }
    }
    for root in roots {
        if detect_forge_marker(root) {
            return Some(Loader::Forge);
        }
    }
    for root in roots {
        if detect_fabric_marker(root) {
            return Some(Loader::Fabric);
        }
    }
    None
}

fn detect_from_markers(root: &Path) -> Option<Loader> {
    if detect_neoforge_marker(root) {
        return Some(Loader::NeoForge);
    }
    if detect_quilt_marker(root) {
        return Some(Loader::Quilt);
    }
    if detect_forge_marker(root) {
        return Some(Loader::Forge);
    }
    if detect_fabric_marker(root) {
        return Some(Loader::Fabric);
    }
    None
}

fn detect_neoforge_marker(root: &Path) -> bool {
    path_contains(root, "libraries/net/neoforged")
        || root.join("neoforge.jar").is_file()
        || file_exists(root, "META-INF/neoforge.mods.toml")
}

fn detect_forge_marker(root: &Path) -> bool {
    root.join("forge.jar").is_file()
        || path_contains(root, "libraries/net/minecraftforge")
        || root.join("unix_args.txt").is_file()
        || root.join("run.bat").is_file() && path_contains(root, "libraries/net/minecraftforge")
}

fn detect_fabric_marker(root: &Path) -> bool {
    // Real Fabric packs ship fabric.mod.json (often under versions/) or fabric-loader jars.
    if file_exists(root, "fabric.mod.json") {
        return true;
    }
    if root.join("versions").is_dir() && walk_has_file_named(root, "fabric.mod.json") {
        return true;
    }
    mods_name_contains(root, &["fabric-loader-", "fabric-api-"])
}

fn detect_quilt_marker(root: &Path) -> bool {
    file_exists(root, "quilt.mod.json")
        || walk_has_file_named(root, "quilt.mod.json")
        || mods_name_contains(root, &["quilt-loader-"])
}

fn detect_from_pack_names(root: &Path) -> Option<Loader> {
    let mut name_blob = String::new();
    collect_names(root, root, 0, &mut name_blob);
    score_pack_names(&name_blob)
}

/// Scoring for Release asset names only — short strings, bare keywords OK.
fn score_release_names(text: &str) -> Option<Loader> {
    let lower = text.to_ascii_lowercase();
    let mut scores = [
        (Loader::NeoForge, weighted(&lower, &[("neoforge", 5), ("neoforged", 5), ("neo-forge", 5)])),
        (Loader::Quilt, weighted(&lower, &[("quilt-loader", 5), ("quilt", 3)])),
        (Loader::Fabric, weighted(&lower, &[("fabric-loader", 5), ("fabric-api", 4), ("fabric", 2)])),
        (Loader::Forge, weighted(&lower, &[("minecraftforge", 5), ("forge", 2)])),
    ];
    // If both forge-family and fabric appear in a dual name like Fabric+Forge, prefer Forge only when
    // "forge" is present without stronger fabric-loader signal — handled by weights.
    pick_best(&mut scores)
}

/// Scoring for full pack file trees — avoid false positives like tetra/materials/fabric.
fn score_pack_names(text: &str) -> Option<Loader> {
    let lower = text.to_ascii_lowercase();
    // Strip known false positives before scoring.
    let cleaned = lower
        .replace("materials/fabric", " ")
        .replace("material/fabric", " ")
        .replace("tetra\\materials\\fabric", " ")
        .replace("fabric+forge", " forge ")
        .replace("fabric-forge", " forge ")
        .replace("forge+fabric", " forge ");
    let mut scores = [
        (Loader::NeoForge, weighted(&cleaned, &[("neoforge", 6), ("neoforged", 6), ("neo-forge", 6)])),
        (Loader::Quilt, weighted(&cleaned, &[("quilt-loader", 6), ("quilt.mod.json", 6)])),
        (
            Loader::Fabric,
            weighted(
                &cleaned,
                &[
                    ("fabric-loader", 6),
                    ("fabric-api", 5),
                    ("fabric.mod.json", 6),
                    // bare "fabric" is too noisy inside Forge packs; keep tiny weight
                    ("fabric", 1),
                ],
            ),
        ),
        (
            Loader::Forge,
            weighted(
                &cleaned,
                &[
                    ("minecraftforge", 6),
                    ("forge.jar", 6),
                    ("unix_args.txt", 4),
                    ("forge", 2),
                ],
            ),
        ),
    ];
    pick_best(&mut scores)
}

fn weighted(text: &str, needles: &[(&str, i32)]) -> i32 {
    needles
        .iter()
        .map(|(needle, weight)| if text.contains(needle) { *weight } else { 0 })
        .sum()
}

fn pick_best(scores: &mut [(Loader, i32)]) -> Option<Loader> {
    scores.sort_by(|a, b| b.1.cmp(&a.1));
    if scores[0].1 <= 0 {
        return None;
    }
    // Require a clear winner when the top signal is only the weak bare "fabric"/bare "forge".
    if scores[0].1 < 3 && scores.len() > 1 && scores[1].1 > 0 {
        // ambiguous weak hits
        return None;
    }
    Some(scores[0].0)
}

fn collect_names(root: &Path, dir: &Path, depth: usize, out: &mut String) {
    if depth > 6 {
        return;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        out.push(' ');
        out.push_str(&name);
        let path = entry.path();
        if path.is_dir() {
            // Skip huge / noisy trees.
            if matches!(
                name.as_str(),
                "objects" | ".git" | "cache" | "logs" | "world" | "saves" | "libraries" | "assets" | "data"
            ) {
                // Still record the directory name itself (already pushed), but don't descend into data/
                // except we need libraries for markers — markers use path_contains separately.
                if name == "libraries" || name == "data" {
                    continue;
                }
                continue;
            }
            collect_names(root, &path, depth + 1, out);
        }
    }
}

fn file_exists(root: &Path, rel: &str) -> bool {
    root.join(rel).is_file()
}

fn walk_has_file_named(root: &Path, file_name: &str) -> bool {
    let target = file_name.to_ascii_lowercase();
    walk_find(root, 0, &mut |path| {
        path.file_name()
            .map(|name| name.to_string_lossy().to_ascii_lowercase() == target)
            .unwrap_or(false)
            && path.is_file()
    })
}

fn mods_name_contains(root: &Path, needles: &[&str]) -> bool {
    for mods in [root.join("mods"), root.join("overrides/mods")] {
        let Ok(entries) = fs::read_dir(&mods) else {
            continue;
        };
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_ascii_lowercase();
            if needles.iter().any(|needle| name.contains(needle)) {
                return true;
            }
        }
    }
    false
}

fn walk_find(dir: &Path, depth: usize, pred: &mut dyn FnMut(&Path) -> bool) -> bool {
    if depth > 8 {
        return false;
    }
    let Ok(entries) = fs::read_dir(dir) else {
        return false;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if pred(&path) {
            return true;
        }
        if path.is_dir() {
            let name = entry.file_name().to_string_lossy().to_string();
            if matches!(name.as_str(), "objects" | ".git" | "cache" | "logs" | "world" | "saves") {
                continue;
            }
            if walk_find(&path, depth + 1, pred) {
                return true;
            }
        }
    }
    false
}

fn path_contains(root: &Path, rel: &str) -> bool {
    root.join(rel).exists()
}

/// Simple `*` glob against a whole string (case-insensitive).
pub fn glob_match(pattern: &str, name: &str) -> bool {
    let pat = pattern.trim();
    if pat.is_empty() {
        return false;
    }
    let pat = pat.to_ascii_lowercase();
    let name = name.to_ascii_lowercase();
    let parts: Vec<&str> = pat.split('*').collect();
    if parts.len() == 1 {
        return name == pat;
    }
    let mut rest = name.as_str();
    if !parts[0].is_empty() {
        if !rest.starts_with(parts[0]) {
            return false;
        }
        rest = &rest[parts[0].len()..];
    }
    for (i, part) in parts.iter().enumerate().skip(1) {
        if part.is_empty() {
            continue;
        }
        if i == parts.len() - 1 {
            return rest.ends_with(part);
        }
        if let Some(at) = rest.find(part) {
            rest = &rest[at + part.len()..];
        } else {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn glob_client_zip() {
        assert!(glob_match("*Client*.zip", "Pack-Client-1.0.zip"));
        assert!(glob_match("*Server*.zip", "Pack-Server-1.0.zip"));
        assert!(!glob_match("*Client*.zip", "Pack-Server-1.0.zip"));
    }

    #[test]
    fn detect_neoforge_name() {
        assert_eq!(detect_from_names(&["MyPack-NeoForge-Client.zip".into()]), Some(Loader::NeoForge));
    }

    #[test]
    fn detect_fabric_name() {
        assert_eq!(
            detect_from_names(&["fabric-loader-0.15.jar".into(), "Client.zip".into()]),
            Some(Loader::Fabric)
        );
    }

    #[test]
    fn detect_quilt_name() {
        assert_eq!(detect_from_names(&["Quilt-Pack-Client.zip".into()]), Some(Loader::Quilt));
    }

    #[test]
    fn detect_forge_name() {
        assert_eq!(
            detect_from_names(&["Create-Delight-Remake-Forge-Server.zip".into()]),
            Some(Loader::Forge)
        );
    }

    #[test]
    fn resolve_manual_overrides_auto() {
        let tmp = std::env::temp_dir().join("lnsync-loader-manual");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(tmp.join("mods")).unwrap();
        std::fs::write(tmp.join("fabric.mod.json"), b"{}").unwrap();
        let got = resolve("neoforge", &["fabric-Client.zip".into()], &[&tmp]);
        assert_eq!(got, Loader::NeoForge);
    }

    #[test]
    fn detect_pack_fabric_marker() {
        let tmp = std::env::temp_dir().join("lnsync-loader-fabric");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(tmp.join("fabric.mod.json"), b"{}").unwrap();
        assert_eq!(detect_from_pack(&tmp), Some(Loader::Fabric));
    }

    #[test]
    fn detect_pack_quilt_marker() {
        let tmp = std::env::temp_dir().join("lnsync-loader-quilt");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(tmp.join("quilt.mod.json"), b"{}").unwrap();
        assert_eq!(detect_from_pack(&tmp), Some(Loader::Quilt));
    }

    #[test]
    fn detect_pack_neoforge_libs() {
        let tmp = std::env::temp_dir().join("lnsync-loader-neo");
        let _ = std::fs::remove_dir_all(&tmp);
        let lib = tmp.join("libraries/net/neoforged/neoforge");
        std::fs::create_dir_all(&lib).unwrap();
        std::fs::write(lib.join("neo.txt"), b"x").unwrap();
        assert_eq!(detect_from_pack(&tmp), Some(Loader::NeoForge));
    }

    #[test]
    fn detect_pack_forge_jar() {
        let tmp = std::env::temp_dir().join("lnsync-loader-forge");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();
        std::fs::write(tmp.join("forge.jar"), b"x").unwrap();
        assert_eq!(detect_from_pack(&tmp), Some(Loader::Forge));
    }

    #[test]
    fn cdr_style_false_fabric_folder_still_forge() {
        // Create Delight Remake has tetra/materials/fabric and Fabric+Forge dual jars,
        // but server ships forge.jar — must not resolve as Fabric.
        let base = std::env::temp_dir().join("lnsync-loader-cdr-false-fabric");
        let _ = std::fs::remove_dir_all(&base);
        let client = base.join("client");
        let server = base.join("server");
        std::fs::create_dir_all(client.join("overrides/kubejs/data/tetra/materials/fabric")).unwrap();
        std::fs::create_dir_all(server.join("mods")).unwrap();
        std::fs::write(server.join("forge.jar"), b"forge").unwrap();
        std::fs::write(server.join("mods/Towns-and-Towers-1.12-Fabric+Forge.jar"), b"mod").unwrap();
        let assets = vec![
            "Client-Create-Delight-Remake-v0.5.0.14-test.zip".into(),
            "Server-Create-Delight-Remake-v0.5.0.14-test.zip".into(),
        ];
        let got = resolve("auto", &assets, &[&client, &server]);
        assert_eq!(got, Loader::Forge);
    }
}
