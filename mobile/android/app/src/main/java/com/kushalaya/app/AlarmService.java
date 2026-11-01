package com.kushalaya.app;

import android.app.Notification;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.Log;

/**
 * Plays the siren like an alarm clock: on the ALARM stream at full volume (so it
 * rings on silent), twice with a 10 s gap like the website, with vibration.
 * Runs as a foreground service so it keeps going with the app closed. Afterwards
 * the notification stays so Acknowledge is still one tap away.
 */
public class AlarmService extends Service {
    private static final String TAG = "KushAlarm";
    static final String ACTION_STOP = "com.kushalaya.app.STOP_ALARM";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private MediaPlayer player;
    private Vibrator vibrator;
    private int plays;
    private int savedVolume = -1;

    /** Silence it now (Acknowledge / Open / acknowledged on the page). */
    static void stop(Context ctx) {
        try {
            ctx.startService(new Intent(ctx, AlarmService.class).setAction(ACTION_STOP));
        } catch (Exception e) {
            // Not running: nothing to stop.
        }
        SosAlarm.cancel(ctx);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || ACTION_STOP.equals(intent.getAction())) {
            silence();
            stopForeground(STOP_FOREGROUND_REMOVE);
            SosAlarm.cancel(this);
            stopSelf();
            return START_NOT_STICKY;
        }
        Bundle data = intent.getExtras() == null ? new Bundle() : intent.getExtras();
        Notification n = SosAlarm.build(this, data, true);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(SosAlarm.NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
            } else {
                startForeground(SosAlarm.NOTIFICATION_ID, n);
            }
        } catch (Exception e) {
            Log.w(TAG, "startForeground failed; ringing notification instead", e);
            SosAlarm.notifyPlain(this, SosAlarm.build(this, data, false));
            stopSelf();
            return START_NOT_STICKY;
        }
        silence(); // a new SOS restarts the siren
        plays = 0;
        louder();
        vibrate();
        playOnce();
        return START_NOT_STICKY;
    }

    private void playOnce() {
        try {
            player = new MediaPlayer();
            player.setAudioAttributes(SosAlarm.alarmAttributes());
            player.setWakeMode(this, PowerManager.PARTIAL_WAKE_LOCK);
            player.setDataSource(this, SosAlarm.sirenUri(this));
            player.setOnCompletionListener(mp -> {
                releasePlayer();
                plays++;
                if (plays < SosAlarm.PLAYS) {
                    handler.postDelayed(this::playOnce, SosAlarm.GAP_MS);
                } else {
                    finishRinging();
                }
            });
            player.prepare();
            player.start();
        } catch (Exception e) {
            Log.e(TAG, "siren failed", e);
            releasePlayer();
            finishRinging();
        }
    }

    /** Done ringing: keep the notification (detached) so the person can still acknowledge. */
    private void finishRinging() {
        silence();
        stopForeground(STOP_FOREGROUND_DETACH);
        stopSelf();
    }

    private void louder() {
        AudioManager am = getSystemService(AudioManager.class);
        if (am == null) return;
        try {
            savedVolume = am.getStreamVolume(AudioManager.STREAM_ALARM);
            am.setStreamVolume(AudioManager.STREAM_ALARM, am.getStreamMaxVolume(AudioManager.STREAM_ALARM), 0);
        } catch (Exception e) {
            savedVolume = -1;
        }
    }

    private void vibrate() {
        vibrator = getSystemService(Vibrator.class);
        if (vibrator == null || !vibrator.hasVibrator()) return;
        try {
            vibrator.vibrate(VibrationEffect.createWaveform(SosAlarm.VIBRATE, 0), SosAlarm.alarmAttributes());
        } catch (Exception e) {
            Log.w(TAG, "vibrate failed", e);
        }
    }

    private void releasePlayer() {
        if (player != null) {
            try {
                player.stop();
            } catch (Exception ignored) {
                // not started
            }
            player.release();
            player = null;
        }
    }

    private void silence() {
        handler.removeCallbacksAndMessages(null);
        releasePlayer();
        if (vibrator != null) vibrator.cancel();
        if (savedVolume >= 0) {
            AudioManager am = getSystemService(AudioManager.class);
            try {
                if (am != null) am.setStreamVolume(AudioManager.STREAM_ALARM, savedVolume, 0);
            } catch (Exception ignored) {
                // DND rules can refuse; the user's volume stays at max
            }
            savedVolume = -1;
        }
    }

    @Override
    public void onDestroy() {
        silence();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
