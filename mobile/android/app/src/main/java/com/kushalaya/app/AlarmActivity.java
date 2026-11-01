package com.kushalaya.app;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.TextView;

/**
 * Full-screen SOS, shown over the lock screen like an incoming call:
 * "SOS — <client>", who pressed it, and Acknowledge / Open.
 */
public class AlarmActivity extends Activity {
    private Bundle data = new Bundle();
    private TextView status;
    private Button ack;
    private Button open;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        } else {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                    | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON);
        }
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setContentView(R.layout.activity_alarm);
        status = findViewById(R.id.alarm_status);
        ack = findViewById(R.id.alarm_ack);
        open = findViewById(R.id.alarm_open);
        ack.setOnClickListener(v -> acknowledge());
        open.setOnClickListener(v -> openApp());
        show(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        show(intent); // a newer SOS replaces this one
    }

    private void show(Intent intent) {
        data = intent != null && intent.getExtras() != null ? intent.getExtras() : new Bundle();
        ((TextView) findViewById(R.id.alarm_title)).setText(SosAlarm.title(data));
        ((TextView) findViewById(R.id.alarm_body)).setText(SosAlarm.body(data));
        status.setText("");
        ack.setEnabled(true);
        open.setEnabled(true);
    }

    private void acknowledge() {
        AlarmService.stop(this);
        String alertId = data.getString(SosAlarm.EXTRA_ALERT_ID, "");
        if (alertId.isEmpty()) { // the test alarm from the setup screen
            finish();
            return;
        }
        ack.setEnabled(false);
        status.setText("Acknowledging…");
        new Thread(() -> {
            int code = Session.acknowledge(getApplicationContext(), alertId);
            runOnUiThread(() -> {
                if (code >= 200 && code < 300) {
                    status.setText("Acknowledged. The others can see you have it.");
                    status.postDelayed(this::finish, 1500);
                } else {
                    status.setText(code == 0 ? "No internet. Opening the app…" : "Please acknowledge in the app.");
                    status.postDelayed(this::openApp, 1200);
                }
            });
        }).start();
    }

    private void openApp() {
        AlarmService.stop(this);
        Runnable go = () -> {
            startActivity(new Intent(this, MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP));
            finish();
        };
        KeyguardManager km = getSystemService(KeyguardManager.class);
        if (km != null && km.isKeyguardLocked()) {
            km.requestDismissKeyguard(this, new KeyguardManager.KeyguardDismissCallback() {
                @Override
                public void onDismissSucceeded() {
                    go.run();
                }
            });
        } else {
            go.run();
        }
    }
}
