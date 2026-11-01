// Builds both apps and copies the APKs to mobile/dist/.
//   node scripts/build.mjs debug     -> dist/kushalaya-ops-debug.apk, dist/kushalaya-family-debug.apk
//   node scripts/build.mjs release   -> signed if android/keystore.properties exists (see README)
//   node scripts/build.mjs bundle    -> .aab files for the Play Store
import { execSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const mode = process.argv[2] || "debug";
const android = join(root, "android");
const gradlew = process.platform === "win32" ? "gradlew.bat" : "./gradlew";
const dist = join(root, "dist");
mkdirSync(dist, { recursive: true });

// Toolchain: JAVA_HOME / ANDROID_HOME if set, else the portable installs in
// %USERPROFILE%\Android (jdk-21, Sdk) that README section 3 describes.
const home = process.env.USERPROFILE || process.env.HOME || "";
const env = { ...process.env };
if (!env.JAVA_HOME && existsSync(join(home, "Android", "jdk-21"))) env.JAVA_HOME = join(home, "Android", "jdk-21");
if (!env.ANDROID_HOME && existsSync(join(home, "Android", "Sdk"))) env.ANDROID_HOME = join(home, "Android", "Sdk");
if (env.ANDROID_HOME && !existsSync(join(android, "local.properties"))) {
  writeFileSync(join(android, "local.properties"), `sdk.dir=${env.ANDROID_HOME.replace(/\\/g, "/")}\n`);
}

const flavors = ["ops", "family"];
const cap = (s) => s[0].toUpperCase() + s.slice(1);
const type = mode === "debug" ? "Debug" : "Release";
const task = mode === "bundle" ? "bundle" : "assemble";
execSync(`"${join(android, gradlew)}" ${flavors.map((f) => `${task}${cap(f)}${type}`).join(" ")}`, { cwd: android, stdio: "inherit", env });

for (const f of flavors) {
  const lower = type.toLowerCase();
  const candidates =
    mode === "bundle"
      ? [join(android, `app/build/outputs/bundle/${f}${type}/app-${f}-${lower}.aab`)]
      : [
          join(android, `app/build/outputs/apk/${f}/${lower}/app-${f}-${lower}.apk`),
          join(android, `app/build/outputs/apk/${f}/${lower}/app-${f}-${lower}-unsigned.apk`),
        ];
  const found = candidates.find((p) => existsSync(p));
  if (!found) throw new Error(`No output for ${f}: looked in ${candidates.join(", ")}`);
  const ext = mode === "bundle" ? "aab" : "apk";
  const out = join(dist, `kushalaya-${f}-${mode === "bundle" ? "release" : lower}${found.includes("unsigned") ? "-unsigned" : ""}.${ext}`);
  copyFileSync(found, out);
  console.log(`-> ${out}`);

  // Signed release: also the files the server hands out for the in-app update
  // (backend app/api/v1/app_release.py). Copy dist/release/* to the server's releases dir.
  if (mode === "release" && !found.includes("unsigned")) {
    const rel = join(dist, "release");
    mkdirSync(rel, { recursive: true });
    copyFileSync(found, join(rel, `kushalaya-${f}.apk`));
    const gradle = readFileSync(join(android, "app/build.gradle"), "utf8");
    const manifest = {
      version_code: Number(gradle.match(/versionCode\s+(\d+)/)[1]),
      version_name: gradle.match(/versionName\s+"([^"]+)"/)[1],
      sha256: createHash("sha256").update(readFileSync(found)).digest("hex"),
      notes: process.env.RELEASE_NOTES || "",
    };
    writeFileSync(join(rel, `${f}.json`), JSON.stringify(manifest, null, 2) + "\n");
    console.log(`-> ${join(rel, `${f}.json`)} (version ${manifest.version_code})`);
  }
}
