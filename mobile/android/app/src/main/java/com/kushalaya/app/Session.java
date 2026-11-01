package com.kushalaya.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * What the native side knows about the signed-in person, handed over by the web
 * page (frontend/components/useNativePush.ts): the API base and access token, so
 * the lock-screen Acknowledge button can call the API without opening the app.
 * Stored in app-private preferences; wiped on sign-out.
 */
final class Session {
    private static final String TAG = "KushSession";
    private static final String PREFS = "kush_session";

    private Session() {}

    private static SharedPreferences prefs(Context ctx) {
        return ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static void save(Context ctx, String apiBase, String accessToken, String app) {
        prefs(ctx).edit()
                .putString("api_base", stripSlash(apiBase))
                .putString("access_token", accessToken)
                .putString("app", app)
                .apply();
    }

    static void clear(Context ctx) {
        prefs(ctx).edit().remove("api_base").remove("access_token").apply();
    }

    static void saveFcmToken(Context ctx, String token) {
        prefs(ctx).edit().putString("fcm_token", token).apply();
    }

    static String fcmToken(Context ctx) {
        return prefs(ctx).getString("fcm_token", "");
    }

    static boolean signedIn(Context ctx) {
        return !prefs(ctx).getString("access_token", "").isEmpty();
    }

    static String apiBase(Context ctx) {
        String base = prefs(ctx).getString("api_base", "");
        return base.isEmpty() ? BuildConfig.SERVER_URL : base;
    }

    private static String stripSlash(String s) {
        if (s == null) return "";
        return s.endsWith("/") ? s.substring(0, s.length() - 1) : s;
    }

    /** POST JSON to the API as the signed-in person. Returns the HTTP status (0 = no network). Call off the main thread. */
    static int post(Context ctx, String path, JSONObject body) {
        String token = prefs(ctx).getString("access_token", "");
        if (token.isEmpty()) return 401;
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(apiBase(ctx) + path).openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Authorization", "Bearer " + token);
            byte[] bytes = (body == null ? "{}" : body.toString()).getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(bytes);
            }
            return conn.getResponseCode();
        } catch (Exception e) {
            Log.w(TAG, "POST " + path + " failed", e);
            return 0;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    /** Tell the server this phone belongs to the signed-in person (also on FCM token rotation). */
    static void registerDevice(Context ctx) {
        String token = fcmToken(ctx);
        if (token.isEmpty() || !signedIn(ctx)) return;
        try {
            JSONObject body = new JSONObject()
                    .put("token", token)
                    .put("app", BuildConfig.APP_KIND)
                    .put("platform", "android");
            post(ctx, "/api/v1/push/devices", body);
        } catch (Exception e) {
            Log.w(TAG, "register failed", e);
        }
    }

    /** Stop this phone ringing for the person who signed out, then forget them. */
    static void unregisterAndClear(Context ctx) {
        String token = fcmToken(ctx);
        try {
            if (!token.isEmpty() && signedIn(ctx)) {
                post(ctx, "/api/v1/push/devices/unregister", new JSONObject().put("token", token));
            }
        } catch (Exception e) {
            Log.w(TAG, "unregister failed", e);
        }
        clear(ctx);
    }

    static int acknowledge(Context ctx, String alertId) {
        if (alertId == null || alertId.isEmpty()) return 404;
        return post(ctx, "/api/v1/sos-siren/" + alertId + "/acknowledge", null);
    }
}
