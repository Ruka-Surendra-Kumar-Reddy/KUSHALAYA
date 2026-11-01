package com.kushalaya.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;

/**
 * Self-update from our own server (backend app/api/v1/app_release.py). On start the app
 * asks for the latest version; if it is newer: "Update available" → download → Android's
 * own Install screen. Sign-in and permissions are kept (same signing key required).
 */
final class UpdateCheck {
    private static final String PREFS = "kush_update";
    private static final long EVERY_MS = 6 * 60 * 60 * 1000L;
    private static boolean busy;

    private UpdateCheck() {}

    /** At most every 6 hours, unless {@code force}. Never blocks the UI. */
    static void run(Activity a, boolean force) {
        long last = a.getSharedPreferences(PREFS, Activity.MODE_PRIVATE).getLong("checked", 0);
        if (busy || (!force && System.currentTimeMillis() - last < EVERY_MS)) return;
        busy = true;
        new Thread(() -> {
            try {
                JSONObject j = new JSONObject(new String(get(BuildConfig.SERVER_URL
                        + "/api/v1/app-release/android/" + BuildConfig.APP_KIND), "UTF-8"));
                a.getSharedPreferences(PREFS, Activity.MODE_PRIVATE).edit()
                        .putLong("checked", System.currentTimeMillis()).apply();
                if (j.getInt("version_code") > BuildConfig.VERSION_CODE) {
                    a.runOnUiThread(() -> offer(a, j));
                }
            } catch (Exception e) {
                /* offline, or nothing published: try again next start */
            } finally {
                busy = false;
            }
        }).start();
    }

    private static void offer(Activity a, JSONObject j) {
        if (a.isFinishing()) return;
        String notes = j.optString("notes", "");
        new AlertDialog.Builder(a)
                .setTitle(R.string.update_title)
                .setMessage(a.getString(R.string.update_body, j.optString("version_name", ""))
                        + (notes.isEmpty() ? "" : "\n\n" + notes))
                .setPositiveButton(R.string.update_now, (d, w) -> download(a, j))
                .setNegativeButton(R.string.update_later, null)
                .show();
    }

    private static void download(Activity a, JSONObject j) {
        if (Build.VERSION.SDK_INT >= 26 && !a.getPackageManager().canRequestPackageInstalls()) {
            // One time: Android asks to allow installs from this app; then tap Update again.
            a.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + a.getPackageName())));
            a.getSharedPreferences(PREFS, Activity.MODE_PRIVATE).edit().putLong("checked", 0).apply();
            return;
        }
        AlertDialog wait = new AlertDialog.Builder(a)
                .setMessage(R.string.update_downloading).setCancelable(false).show();
        new Thread(() -> {
            String err = null;
            File apk = new File(new File(a.getCacheDir(), "updates"), "kushalaya-update.apk");
            try {
                byte[] bytes = get(BuildConfig.SERVER_URL + j.getString("url"));
                String want = j.optString("sha256", "");
                if (!want.isEmpty() && !want.equalsIgnoreCase(sha256(bytes))) {
                    throw new IllegalStateException("checksum");
                }
                apk.getParentFile().mkdirs();
                try (FileOutputStream out = new FileOutputStream(apk)) {
                    out.write(bytes);
                }
            } catch (Exception e) {
                err = e.getMessage();
            }
            String failed = err;
            a.runOnUiThread(() -> {
                wait.dismiss();
                if (failed != null) {
                    new AlertDialog.Builder(a).setMessage(R.string.update_failed)
                            .setPositiveButton(android.R.string.ok, null).show();
                    return;
                }
                Uri uri = FileProvider.getUriForFile(a, a.getPackageName() + ".fileprovider", apk);
                a.startActivity(new Intent(Intent.ACTION_VIEW)
                        .setDataAndType(uri, "application/vnd.android.package-archive")
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK));
            });
        }).start();
    }

    private static byte[] get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(60000);
        try {
            if (c.getResponseCode() != 200) throw new IllegalStateException("HTTP " + c.getResponseCode());
            try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[64 * 1024];
                for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
                return out.toByteArray();
            }
        } finally {
            c.disconnect();
        }
    }

    private static String sha256(byte[] b) throws Exception {
        StringBuilder s = new StringBuilder();
        for (byte x : MessageDigest.getInstance("SHA-256").digest(b)) s.append(String.format("%02x", x));
        return s.toString();
    }
}
