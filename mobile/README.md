# KushAlaya Android apps

Two apps from one code base:

| App | Package | Loads |
| --- | --- | --- |
| **KushAlaya Ops** (staff, caregivers at `/caregiver`) | `com.kushalaya.ops` | https://ops.kushalaya.com |
| **KushAlaya Family** | `com.kushalaya.family` | https://family.kushalaya.com |

They show the live website, so website changes reach the apps with no app update.
What the apps add is the **SOS alarm**: an SOS rings like an alarm clock even when
the app is closed, the screen is locked, or the phone is on silent or Do Not Disturb.

## How it works

```
SOS pressed ─► backend sos_siren (rows per person) ─► app/livewell/push.py
             ─► FCM HTTP v1, data-only + HIGH priority, one message per phone
             ─► SosMessagingService ─► AlarmService (siren ×2, 10 s gap, ALARM stream, full volume)
                                    └► full-screen AlarmActivity "SOS — <client>"  [Acknowledge] [Open]
```

- **Who gets it:** exactly the people who get a siren row (start, watch "confirm
  emergency", 2-minute escalation to the heads). Nobody else.
- **Acknowledge** calls the existing `POST /api/v1/sos-siren/{id}/acknowledge`
  with the session the page handed to the app. If that fails (signed out, offline),
  the app opens so they can acknowledge on the page.
- **Registering the phone:** when a signed-in page loads inside the app,
  `frontend/components/useNativePush.ts` (mounted by `SosSiren`) gets the FCM token
  from the native `KushAlarm` plugin and calls `POST /api/v1/push/devices`. Signing
  out (`clearAuth`) unregisters it. A shared phone rings only for whoever signed in last.
- **Why Capacitor, not a TWA:** the page must hand its token and session to native
  code, and the caregiver pages need camera, file upload and location in the WebView.
  Capacitor does both; a TWA (Chrome tab) can do neither.
- **No Firebase yet?** The apps still work as the website with the normal web
  siren; the backend sends nothing and logs nothing.

Code: `android/app/src/main/java/com/kushalaya/app/` (the alarm),
`android/app/build.gradle` (the two flavors), `scripts/` (sync and build).

## 1. Firebase (owner)

1. https://console.firebase.google.com → **Add project** → "KushAlaya" (Analytics not needed).
2. **Add app → Android**, package `com.kushalaya.ops`. Then add a second Android app,
   package `com.kushalaya.family`, in the **same** project.
3. Download **google-services.json** (after adding both apps, so it lists both) and put it at
   `mobile/android/app/google-services.json`. Without it the build still works but no push arrives.
4. **Project settings → Service accounts → Generate new private key.** This JSON is a
   secret for the server only. Never put it in the app, the repo or the website.
5. Cloud Messaging API (V1) is on by default for new projects; check it says *Enabled*
   under Project settings → Cloud Messaging.

Send both files to the developer privately (not by email in clear text, not in the repo).

## 2. Server env vars

Put the service-account key on the VM, readable only by the app user:

```bash
sudo install -o safehomeops -g safehomeops -m 600 fcm-service-account.json \
     /opt/safehomeops/app/backend/fcm-service-account.json
```

Add to `backend/.env` on the VM (never to the repo, never shipped in the deploy tarball):

```
FCM_SERVICE_ACCOUNT_FILE=/opt/safehomeops/app/backend/fcm-service-account.json
# optional, defaults to project_id inside the JSON:
# FCM_PROJECT_ID=kushalaya
```

`FCM_SERVICE_ACCOUNT_JSON='{...}'` (the JSON inline) works instead of the file.
Restart `safehomeops-api` **and** `safehomeops-jobs` (escalation runs there).

Deploy the backend with `--backend-migrate`: it adds one table, `push_devices`
(`migrate_push_devices` in `backend/app/db_migrate.py`). No existing table changes.

## 3. Build tools

**Installed on the owner's PC (27 Oct 2026), no admin rights needed:** JDK 21 in
`C:\Users\ASUS\Android\jdk-21` and the Android SDK (platform 35, build-tools 35,
platform-tools) in `C:\Users\ASUS\Android\Sdk`. `scripts/build.mjs` finds them on its own;
on another machine set `JAVA_HOME` / `ANDROID_HOME`, or install as below.

The build needs about 4–5 GB:

| Tool | Version | Get it |
| --- | --- | --- |
| JDK | 21 | `winget install Microsoft.OpenJDK.21` |
| Android SDK | platform 35, build-tools 35 | Android Studio (easiest), or command-line tools only |
| Node | 20+ (installed) | — |

Command-line tools only (no Android Studio, ~2 GB):

```powershell
winget install Microsoft.OpenJDK.21
# Download "Command line tools only" for Windows from https://developer.android.com/studio#command-tools
# unzip to C:\Android\cmdline-tools\latest\  then:
setx ANDROID_HOME C:\Android
setx JAVA_HOME "C:\Program Files\Microsoft\jdk-21..."   # the folder winget created
# new terminal:
C:\Android\cmdline-tools\latest\bin\sdkmanager.bat "platform-tools" "platforms;android-35" "build-tools;35.0.0"
C:\Android\cmdline-tools\latest\bin\sdkmanager.bat --licenses
```

## 4. Build

```bash
cd mobile
npm install
npm run build:debug      # -> dist/kushalaya-ops-debug.apk, dist/kushalaya-family-debug.apk
```

`npm run sync` alone copies the Capacitor config into `android/` and writes the
per-app `capacitor.config.json` (ops / family). Run it after changing
`capacitor.config.json` or upgrading Capacitor. Android Studio can open `mobile/android`
and run the `opsDebug` / `familyDebug` variants on a phone.

### Signing (release)

Create one upload key and keep it safe (losing it means a new app listing for
direct-APK users, and a key reset request on Play):

```bash
keytool -genkeypair -v -keystore kushalaya-upload.jks -alias kushalaya -keyalg RSA -keysize 2048 -validity 10000
```

Create `mobile/android/keystore.properties` (git-ignored):

```
storeFile=C:/secure/kushalaya-upload.jks
storePassword=...
keyAlias=kushalaya
keyPassword=...
```

```bash
npm run build:release    # signed APKs -> dist/kushalaya-ops-release.apk, dist/kushalaya-family-release.apk
npm run build:bundle     # signed .aab for the Play Store -> dist/
```

Raise `versionCode` / `versionName` in `android/app/build.gradle` for every release.

## 5. Play Store or direct APK (owner to decide)

| | Play Store | Direct APK (WhatsApp / website link) |
| --- | --- | --- |
| Install | Normal, trusted | User must allow "Install unknown apps"; Play Protect may warn |
| Updates | Automatic | Manual: send a new APK each time (rare: the content is the live website) |
| Cost / time | $25 once; new personal accounts need 12 testers × 14 days of closed testing; review days | None |
| Full-screen alert | Must declare "alarm / safety" use of `USE_FULL_SCREEN_INTENT` in the Console; staff turn it on in the setup screen on Android 14+ | Same setup screen |
| Target SDK | Must meet Play's yearly minimum (now 35; this project targets 35 — if Play asks for 36, upgrade to Capacitor 8, which needs Node 22) | No requirement |

Suggestion: direct APK for staff now (small, known group), Play Store for families.

Play Console declarations to expect: foreground service type *media playback*
(reason: plays the SOS siren), full-screen intent (safety alerts), Do Not Disturb
access, data safety form (FCM token, account email).

## 6. Test on a phone

1. Install, open, go through the setup screen (allow notifications, full-screen alerts,
   Do Not Disturb, battery "Unrestricted"), tap **Test the alarm**.
2. Sign in. On the server: `select user_id, app from push_devices;` shows the phone.
3. Lock the phone, put it on silent, then raise an SOS for a client that user covers.
   It must ring twice (10 s apart) and show the red SOS screen. **Acknowledge** must
   clear it on the web for that person too.
4. Xiaomi / Oppo / Vivo / Realme: also turn on **Autostart** for the app in system
   settings, or pushes can be held back when the app is swiped away.

## Known limits

- The phone rings only when Google delivers the push (needs internet; Google may delay
  pushes for apps the user hasn't opened in weeks). The web siren and the
  escalation (email / SMS) still run as before.
- The lock-screen Acknowledge uses the page's last access token. If it has expired,
  the app opens instead so the person acknowledges on the page.
- iOS is not built (the backend accepts `platform: "ios"` for later).
