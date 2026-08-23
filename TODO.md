# TODO: Rename Android package from `click.jordanbarnes.airtype` to `uk.jordanbarnes.airtype`

Domain changed from `jordanbarnes.click` to `jordanbarnes.uk`. App is **not yet published** to Play Store, so `applicationId` can be changed freely. After first Play Store publish this becomes a one-way decision (changing it creates a new listing, orphans installs/reviews), so finish this before publishing.

## Scope

Rename the reverse-DNS identifier everywhere it appears: Android `namespace`, Android `applicationId`, Kotlin `package` declarations, the on-disk directory structure under `java/`, the custom-view FQN in the layout XML, the Windows AppUserModelID, and doc references.

## Files to change

### 1. `android/app/build.gradle.kts`
Lines 19 and 23:
- `namespace = "click.jordanbarnes.airtype"` → `namespace = "uk.jordanbarnes.airtype"`
- `applicationId = "click.jordanbarnes.airtype"` → `applicationId = "uk.jordanbarnes.airtype"`

### 2. Move Kotlin source directories

**Main source set** — move all files from:
`android/app/src/main/java/click/jordanbarnes/airtype/`
to:
`android/app/src/main/java/uk/jordanbarnes/airtype/`

Files (4):
- `AppendOnlyEditText.kt`
- `MainActivity.kt`
- `TextSyncProcessor.kt`
- `WebSocketClient.kt`

**Test source set** — move from:
`android/app/src/test/java/click/jordanbarnes/airtype/`
to:
`android/app/src/test/java/uk/jordanbarnes/airtype/`

Files (1):
- `TextSyncProcessorTest.kt`

After moving, delete the now-empty `click/jordanbarnes/airtype/`, `click/jordanbarnes/`, and `click/` directories in both source sets.

Use `git mv` to preserve history:
```
git mv android/app/src/main/java/click/jordanbarnes/airtype android/app/src/main/java/uk/jordanbarnes/airtype_tmp
mkdir -p android/app/src/main/java/uk/jordanbarnes
mv android/app/src/main/java/uk/jordanbarnes/airtype_tmp android/app/src/main/java/uk/jordanbarnes/airtype
```
(Adjust — the cleanest path is `git mv` the whole `click/` tree with a rename, but Git only tracks file-level moves. Easiest is two steps: `git mv` each `.kt` file, then delete the empty `click/` tree.)

### 3. Update `package` declarations

Line 1 of each of the 5 moved .kt files:
- `package click.jordanbarnes.airtype` → `package uk.jordanbarnes.airtype`

Files:
- `android/app/src/main/java/uk/jordanbarnes/airtype/AppendOnlyEditText.kt`
- `android/app/src/main/java/uk/jordanbarnes/airtype/MainActivity.kt`
- `android/app/src/main/java/uk/jordanbarnes/airtype/TextSyncProcessor.kt`
- `android/app/src/main/java/uk/jordanbarnes/airtype/WebSocketClient.kt`
- `android/app/src/test/java/uk/jordanbarnes/airtype/TextSyncProcessorTest.kt`

### 4. `android/app/src/main/res/layout/activity_main.xml`
Line 86 — custom view FQN:
- `<click.jordanbarnes.airtype.AppendOnlyEditText` → `<uk.jordanbarnes.airtype.AppendOnlyEditText`
- (And the matching closing tag if present further down.)

### 5. `windows/gui.py`
Line 56:
- `"click.jordanbarnes.airtype"` → `"uk.jordanbarnes.airtype"`

This is the `SetCurrentProcessExplicitAppUserModelID` call that controls the Windows taskbar icon grouping. Not strictly required to match the Android package ID, but keeping them aligned is the existing convention.

### 6. Docs

- `docs/android-app.md:7` — `android/app/src/main/java/click/jordanbarnes/airtype/` → `.../uk/jordanbarnes/airtype/`
- `docs/android-app.md:61` — `android/app/src/test/java/click/jordanbarnes/airtype/` → `.../uk/jordanbarnes/airtype/`
- `docs/windows-server.md:59` — the AppUserModelID string

## Verification

After changes:

1. `grep -r "click.jordanbarnes"` (or Grep tool) across the repo — should return **zero** hits.
2. From `android/`, run `./gradlew clean assembleDebug` — must succeed.
3. Run `./gradlew test` — `TextSyncProcessorTest` must still pass.
4. Install the debug APK on a device and confirm the app launches (the layout XML FQN change is the most error-prone part — a typo there crashes at inflate time).
5. Launch the Windows client and confirm the taskbar icon still shows AirType's icon (not python.exe).

## Out of scope / do not change

- **Signing key** — unaffected by package rename. Keep using the existing keystore.
- **ProGuard / R8 rules** — none currently reference the package by string.
- **`AndroidManifest.xml`** — inherits `namespace` from `build.gradle.kts`; no explicit `package=` attribute to update (verify this is still true; if a `package=` attribute exists on `<manifest>`, remove or update it).
- **User-facing URL references** — `play_store_notes.txt` already uses `jordanbarnes.uk`. A separate sweep for any lingering `jordanbarnes.click` **URLs** (distinct from the package ID) is worth doing but is a separate task from this rename.

## Commit strategy

Single commit: `Rename Android package to uk.jordanbarnes.airtype`. Body should note that the app is pre-publish so `applicationId` change is safe.
