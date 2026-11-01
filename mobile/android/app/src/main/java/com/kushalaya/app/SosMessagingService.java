package com.kushalaya.app;

import android.os.Bundle;

import androidx.annotation.NonNull;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * Receives the server's SOS push (backend/app/livewell/push.py): a data-only,
 * high-priority FCM message, so this runs even when the app is closed.
 */
public class SosMessagingService extends FirebaseMessagingService {
    @Override
    public void onMessageReceived(@NonNull RemoteMessage message) {
        Map<String, String> data = message.getData();
        if (!"sos".equals(data.get("type"))) return;
        Bundle b = new Bundle();
        for (Map.Entry<String, String> e : data.entrySet()) b.putString(e.getKey(), e.getValue());
        SosAlarm.ring(this, b);
    }

    @Override
    public void onNewToken(@NonNull String token) {
        // Runs on a background thread: safe to call the API.
        Session.saveFcmToken(this, token);
        Session.registerDevice(this);
    }
}
