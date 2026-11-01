package com.kushalaya.app;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.core.app.NotificationCompat;

/** The notification's Acknowledge button: silence the alarm and tell the server. */
public class AckReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        AlarmService.stop(ctx);
        String alertId = intent.getStringExtra(SosAlarm.EXTRA_ALERT_ID);
        if (alertId == null || alertId.isEmpty()) return; // the test alarm
        final Context app = ctx.getApplicationContext();
        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                int code = Session.acknowledge(app, alertId);
                if (code < 200 || code >= 300) {
                    // Signed out or offline: ask them to acknowledge in the app.
                    Intent open = new Intent(app, MainActivity.class)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                    PendingIntent pi = PendingIntent.getActivity(app, 4, open,
                            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
                    SosAlarm.notifyPlain(app, new NotificationCompat.Builder(app, SosAlarm.CHANNEL_ID)
                            .setSmallIcon(R.drawable.ic_stat_sos)
                            .setContentTitle("Could not acknowledge the SOS")
                            .setContentText("Tap to open the app and acknowledge it there.")
                            .setContentIntent(pi)
                            .setAutoCancel(true)
                            .setSilent(true)
                            .build());
                }
            } finally {
                pending.finish();
            }
        }).start();
    }
}
