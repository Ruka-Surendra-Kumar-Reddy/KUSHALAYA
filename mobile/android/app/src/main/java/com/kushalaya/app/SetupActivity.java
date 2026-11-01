package com.kushalaya.app;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.widget.Button;

import androidx.core.app.NotificationManagerCompat;

/**
 * First run: explains why the app needs each permission and asks for it.
 * Shown again while notifications are off (an SOS could not ring at all).
 */
public class SetupActivity extends Activity {
    private static final String PREFS = "kush_setup";

    static boolean needed(Context ctx) {
        boolean done = ctx.getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean("done", false);
        // Battery saver too: on realme/Xiaomi it silently kills the alarm on a locked phone.
        PowerManager pm = ctx.getSystemService(PowerManager.class);
        boolean battery = pm == null || pm.isIgnoringBatteryOptimizations(ctx.getPackageName());
        return !done || !NotificationManagerCompat.from(ctx).areNotificationsEnabled() || !battery;
    }

    private Button notifyBtn;
    private Button fullBtn;
    private Button dndBtn;
    private Button batteryBtn;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);
        notifyBtn = findViewById(R.id.setup_notify_btn);
        fullBtn = findViewById(R.id.setup_fullscreen_btn);
        dndBtn = findViewById(R.id.setup_dnd_btn);
        batteryBtn = findViewById(R.id.setup_battery_btn);

        notifyBtn.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= 33) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
            } else {
                open(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName()));
            }
        });
        fullBtn.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= 34) {
                open(new Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,
                        Uri.parse("package:" + getPackageName())));
            }
        });
        dndBtn.setOnClickListener(v -> open(new Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)));
        // The direct one-tap "Allow" popup. The generic list hides this app on some phones
        // (realme/ColorOS shows only "Not optimised" apps), so never send people there.
        batteryBtn.setOnClickListener(v -> open(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                Uri.parse("package:" + getPackageName()))));
        findViewById(R.id.setup_test_btn).setOnClickListener(v -> {
            Bundle b = new Bundle();
            b.putString(SosAlarm.EXTRA_TITLE, "Test alarm — " + getString(R.string.app_name));
            b.putString(SosAlarm.EXTRA_PRESSED_BY, "you (test)");
            SosAlarm.ring(this, b);
        });
        findViewById(R.id.setup_done_btn).setOnClickListener(v -> {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean("done", true).apply();
            finish();
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        SosAlarm.ensureChannel(this); // picks up Do Not Disturb access once granted
        NotificationManager nm = getSystemService(NotificationManager.class);
        mark(notifyBtn, NotificationManagerCompat.from(this).areNotificationsEnabled());
        mark(fullBtn, Build.VERSION.SDK_INT < 34 || (nm != null && nm.canUseFullScreenIntent()));
        mark(dndBtn, nm != null && nm.isNotificationPolicyAccessGranted());
        PowerManager pm = getSystemService(PowerManager.class);
        mark(batteryBtn, pm != null && pm.isIgnoringBatteryOptimizations(getPackageName()));
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (!NotificationManagerCompat.from(this).areNotificationsEnabled()) {
            // Refused (or "don't ask again"): send them to the settings page instead.
            open(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName()));
        }
    }

    private void mark(Button b, boolean ok) {
        b.setEnabled(!ok);
        b.setText(ok ? R.string.setup_allowed : R.string.setup_allow);
    }

    private void open(Intent i) {
        try {
            startActivity(i);
        } catch (Exception e) {
            startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:" + getPackageName())));
        }
    }
}
