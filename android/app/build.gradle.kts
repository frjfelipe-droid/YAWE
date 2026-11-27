plugins {
    id("com.android.application")
}

android {
    namespace = "com.yawe.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.yawe.app"
        minSdk = 24
        targetSdk = 34
        // O GitHub Actions passa o número da execução, para cada APK novo ser uma "atualização".
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "1.0." + (System.getenv("GITHUB_RUN_NUMBER") ?: "0")
    }

    signingConfigs {
        create("yawe") {
            // Chave de assinatura só deste app pessoal (mantém a mesma assinatura entre atualizações).
            storeFile = file("../yawe.keystore")
            storePassword = "yawe-app"
            keyAlias = "yawe"
            keyPassword = "yawe-app"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("yawe")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
