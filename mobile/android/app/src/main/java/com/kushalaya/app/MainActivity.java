package com.kushalaya.app;

import android.content.Intent;
import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

/** The website (ops or family, by flavor) in a Capacitor WebView, plus the SOS alarm. */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(KushAlarmPlugin.class);
        super.onCreate(savedInstanceState);
        SosAlarm.ensureChannel(this);
        handle(getIntent());
        if (SetupActivity.needed(this)) {
            startActivity(new Intent(this, SetupActivity.class));
        }
        UpdateCheck.run(this, true);
    }

    @Override
    public void onResume() {
        super.onResume();
        UpdateCheck.run(this, false); // back from the background: at most every 6 hours
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handle(intent);
    }

    /** "Open" on the SOS notification: stop the alarm; the page shows the SOS notice. */
    private void handle(Intent intent) {
        if (intent != null && intent.getBooleanExtra(SosAlarm.EXTRA_STOP, false)) {
            AlarmService.stop(this);
        }
    }
}
