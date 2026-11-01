package com.kushalaya.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

/**
 * The SOS alarm: the "sos" notification channel, the notification itself (full
 * screen like an incoming call, with Acknowledge and Open), and ring() which the
 * push service calls. The sound is played by AlarmService on the ALARM stream, so
 * it rings on silent; the channel bypasses Do Not Disturb once the person allows it.
 */
final class SosAlarm {
    private static final String TAG = "KushSos";

    static final String CHANNEL_ID = "sos";
    static final int NOTIFICATION_ID = 4242;
    /** Like the website: the siren twice, 10 s apart. */
    static final int PLAYS = 2;
    static final long GAP_MS = 10_000L;
    static final long[] VIBRATE = {0, 800, 400, 800, 400, 800};

    static final String EXTRA_ALERT_ID = "alert_id";
    static final String EXTRA_TITLE = "title";
    static final String EXTRA_ELDER = "elder_name";
    static final String EXTRA_PRESSED_BY = "pressed_by";
    static final String EXTRA_STOP = "kush_stop_alarm";

    private SosAlarm() {}

    static Uri sirenUri(Context ctx) {
        return Uri.parse("android.resource://" + ctx.getPackageName() + "/" + R.raw.kushalaya_sos_siren);
    }

    static AudioAttributes alarmAttributes() {
        return new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build();
    }

    /** Safe to call often: re-applies "bypass Do Not Disturb" once the person grants access. */
    static void ensureChannel(Context ctx) {
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        if (nm == null) return;
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, ctx.getString(R.string.sos_channel_name), NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription(ctx.getString(R.string.sos_channel_desc));
        ch.setSound(sirenUri(ctx), alarmAttributes());
        ch.enableVibration(true);
        ch.setVibrationPattern(VIBRATE);
        ch.enableLights(true);
        ch.setLightColor(0xFFB71C1C);
        ch.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        ch.setBypassDnd(true);
        nm.createNotificationChannel(ch);
    }

    static String title(Bundle data) {
        String t = data == null ? null : data.getString(EXTRA_TITLE);
        return t == null || t.isEmpty() ? "SOS" : t;
    }

    static String body(Bundle data) {
        String by = data == null ? null : data.getString(EXTRA_PRESSED_BY);
        return by == null || by.isEmpty() ? "Someone needs help now." : "Pressed by " + by;
    }

    private static int flags() {
        return PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
    }

    /** @param silent true when AlarmService plays the siren itself (it then rings twice). */
    static Notification build(Context ctx, Bundle data, boolean silent) {
        Bundle extras = data == null ? new Bundle() : data;

        Intent full = new Intent(ctx, AlarmActivity.class).putExtras(extras)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent fullPi = PendingIntent.getActivity(ctx, 1, full, flags());

        Intent ack = new Intent(ctx, AckReceiver.class).putExtras(extras);
        PendingIntent ackPi = PendingIntent.getBroadcast(ctx, 2, ack, flags());

        Intent open = new Intent(ctx, MainActivity.class).putExtra(EXTRA_STOP, true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent openPi = PendingIntent.getActivity(ctx, 3, open, flags());

        NotificationCompat.Builder b = new NotificationCompat.Builder(ctx, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_sos)
                .setColor(0xFFB71C1C)
                .setContentTitle(title(extras))
                .setContentText(body(extras))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setFullScreenIntent(fullPi, true)
                .setContentIntent(fullPi)
                .setOngoing(true)
                .setAutoCancel(false)
                .addAction(0, ctx.getString(R.string.sos_ack), ackPi)
                .addAction(0, ctx.getString(R.string.sos_open), openPi);
        if (silent) {
            b.setSilent(true);
        } else {
            b.setSound(sirenUri(ctx)).setVibrate(VIBRATE);
        }
        return b.build();
    }

    /** Ring now. From a high-priority FCM message the app may start a foreground service. */
    static void ring(Context ctx, Bundle data) {
        ensureChannel(ctx);
        Intent svc = new Intent(ctx, AlarmService.class).putExtras(data);
        try {
            ContextCompat.startForegroundService(ctx, svc);
        } catch (Exception e) {
            // Not allowed to start the service (e.g. the push was deprioritised):
            // the notification still rings once with the channel's siren.
            Log.w(TAG, "alarm service not allowed, posting a ringing notification", e);
            notifyPlain(ctx, build(ctx, data, false));
        }
    }

    static void notifyPlain(Context ctx, Notification n) {
        try {
            NotificationManagerCompat.from(ctx).notify(NOTIFICATION_ID, n);
        } catch (SecurityException e) {
            Log.w(TAG, "notifications not allowed", e);
        }
    }

    static void cancel(Context ctx) {
        NotificationManagerCompat.from(ctx).cancel(NOTIFICATION_ID);
    }
}
