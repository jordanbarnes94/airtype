plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Read .env from repo root (one level above the android/ project), fall back to real env vars
val dotEnv: Map<String, String> = run {
    val f = rootProject.rootDir.parentFile.resolve(".env")
    if (f.exists()) {
        f.readLines()
            .map { it.trim() }
            .filter { it.isNotEmpty() && !it.startsWith("#") && '=' in it }
            .associate { line -> line.substringBefore('=').trim() to line.substringAfter('=').trim() }
    } else emptyMap()
}
fun env(key: String): String? = dotEnv[key] ?: System.getenv(key)

android {
    namespace = "click.jordanbarnes.airtype"
    compileSdk = 36

    defaultConfig {
        applicationId = "click.jordanbarnes.airtype"
        minSdk = 26
        targetSdk = 36
        versionCode = 3
        versionName = "1.0.0"
    }

    signingConfigs {
        create("release") {
            storeFile = env("AIRTYPE_KEYSTORE_PATH")?.let { file(it) }
            storePassword = env("AIRTYPE_KEYSTORE_PASSWORD")
            keyAlias = env("AIRTYPE_KEY_ALIAS")
            keyPassword = env("AIRTYPE_KEY_PASSWORD")
        }
    }

    buildTypes {
        release {
            signingConfig = if (env("AIRTYPE_KEYSTORE_PATH") != null)
                signingConfigs.getByName("release") else null
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
    buildToolsVersion = "36.1.0"

    base {
        archivesName = "AirType"
    }

    applicationVariants.all {
        val variant = this
        outputs.all {
            (this as com.android.build.gradle.internal.api.BaseVariantOutputImpl)
            outputFileName = "AirType-${variant.buildType.name}.apk"
        }
    }
}

dependencies {
    // AndroidX
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.activity:activity-ktx:1.9.0")
    implementation("androidx.core:core-ktx:1.15.0")

    // WebSocket
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Testing
    testImplementation("junit:junit:4.13.2")
}
