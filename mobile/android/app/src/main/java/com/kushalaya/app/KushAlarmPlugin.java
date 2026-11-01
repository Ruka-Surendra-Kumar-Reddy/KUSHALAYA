package com.kushalaya.app;

import android.content.Intent;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.firebase.messaging.FirebaseMessaging;

/**
 * window.Capacitor.Plugins.KushAlarm, used by the website when it runs inside the
 * app (frontend/lib/native-app.ts). Keep the method names in step with that file.
 */
@CapacitorPlugin(name = "KushAlarm")
public class KushAlarmPlugin extends Plugin {

    @PluginMethod
    public void getToken(PluginCall call) {
        try {
            FirebaseMessaging.getInstance().getToken().addOnCompleteListener(task -> {
                JSObject out = new JSObject();
                String token = task.isSuccessful() ? task.getResult() : null;
                if (token != null) Session.saveFcmToken(getContext(), token);
                out.put("token", token == null ? "" : token);
                call.resolve(out);
            });
        } catch (Exception e) {
            // Firebase not set up yet (no google-services.json): the web siren still works.
            JSObject out = new JSObject();
            out.put("token", "");
            call.resolve(out);
        }
    }

    @PluginMethod
    public void setSession(PluginCall call) {
        String apiBase = call.getString("apiBase", "");
        String accessToken = call.getString("accessToken", "");
        String app = call.getString("app", BuildConfig.APP_KIND);
        if (accessToken == null || accessToken.isEmpty()) {
            call.reject("accessToken is required");
            return;
        }
        Session.save(getContext(), apiBase, accessToken, app);
        call.resolve();
    }

    @PluginMethod
    public void signOut(PluginCall call) {
        new Thread(() -> {
            Session.unregisterAndClear(getContext());
            call.resolve();
        }).start();
    }

    /** Print / Save as PDF: Android WebViews ignore window.print(), so use PrintManager. */
    @PluginMethod
    public void print(PluginCall call) {
        final String title = call.getString("title", "KushAlaya");
        getActivity().runOnUiThread(() -> {
            try {
                android.webkit.WebView web = getBridge().getWebView();
                android.print.PrintManager pm =
                    (android.print.PrintManager) getActivity().getSystemService(android.content.Context.PRINT_SERVICE);
                pm.print(title, web.createPrintDocumentAdapter(title),
                    new android.print.PrintAttributes.Builder()
                        .setMediaSize(android.print.PrintAttributes.MediaSize.ISO_A4)
                        .build());
                call.resolve();
            } catch (Exception e) {
                call.reject("Could not open printing: " + e.getMessage());
            }
        });
    }

    @PluginMethod
    public void stop(PluginCall call) {
        AlarmService.stop(getContext());
        call.resolve();
    }

    @PluginMethod
    public void openSetup(PluginCall call) {
        Intent i = new Intent(getContext(), SetupActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        getContext().startActivity(i);
        call.resolve();
    }
}
