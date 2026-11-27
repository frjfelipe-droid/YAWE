package com.yawe.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.ArrayList;

/**
 * App Android do YAWE: abre o servidor do YAWE em tela cheia e oferece o microfone
 * nativo do Android (reconhecimento de voz do Google) para a página.
 */
public class MainActivity extends Activity {

    static final String EXTRA_ACTION = "yawe_action";
    private static final String PREFS = "yawe";
    private static final String KEY_URL = "server_url";
    private static final int REQ_SPEECH = 42;
    private static final int REQ_MIC = 43;
    private static final String SETUP_PAGE = "file:///android_asset/setup.html";
    private static final String OFFLINE_PAGE = "file:///android_asset/offline.html";

    private WebView web;
    private SharedPreferences prefs;

    // Escuta contínua (palavra de ativação) com o reconhecedor de voz do Android, sem janela.
    private final Handler handler = new Handler(Looper.getMainLooper());
    private SpeechRecognizer recognizer;
    private boolean wantListening = false;
    private boolean listening = false;
    private int statusBarPx = 0;
    private String pendingAction = null; // ação vinda do widget (falar, abrir curso)

    private int statusBarDp() {
        return Math.round(statusBarPx / getResources().getDisplayMetrics().density);
    }

    private void pushInsets() {
        js("document.documentElement.style.setProperty('--sat','" + statusBarDp() + "px')");
    }

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#000000"));
        web.setOverScrollMode(View.OVER_SCROLL_NEVER); // sem o "puxar" de página da web

        // Tela de ponta a ponta: o brilho do app passa por trás da barra de status, como app nativo.
        FrameLayout root = new FrameLayout(this);
        root.addView(web);
        setContentView(root);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            statusBarPx = insets.getSystemWindowInsetTop();
            // embaixo: barra de navegação ou teclado (o campo de texto nunca fica escondido)
            v.setPadding(0, 0, 0, insets.getSystemWindowInsetBottom());
            pushInsets();
            return insets.consumeSystemWindowInsets();
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false); // a voz toca sozinha após a resposta
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setUserAgentString(s.getUserAgentString() + " YAWEApp/1");
        s.setTextZoom(100); // o tamanho de fonte do sistema não deforma o layout

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);

        web.addJavascriptInterface(new Bridge(), "YAWEAndroid");
        web.setWebViewClient(new Client());

        pendingAction = getIntent().getStringExtra(EXTRA_ACTION);

        // App atualizado: apaga a cópia antiga das telas guardada pelo navegador interno
        // (login, memória e progresso ficam guardados à parte e não são apagados).
        int version = BuildConfig.VERSION_CODE;
        if (prefs.getInt("cache_version", -1) != version) {
            web.clearCache(true);
            prefs.edit().putInt("cache_version", version).apply();
        }

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            openStart();
        }
    }

    private String serverUrl() {
        return prefs.getString(KEY_URL, "");
    }

    private void openStart() {
        String url = serverUrl();
        web.loadUrl(url.isEmpty() ? SETUP_PAGE : url);
    }

    private boolean isServerPage(Uri uri) {
        String saved = serverUrl();
        if (saved.isEmpty() || uri == null || uri.getHost() == null) return false;
        Uri base = Uri.parse(saved);
        return uri.getHost().equalsIgnoreCase(base.getHost());
    }

    /** Navegação: páginas do servidor ficam no app; links externos abrem no navegador. */
    private class Client extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            String scheme = uri.getScheme() == null ? "" : uri.getScheme();
            if (scheme.equals("file") || isServerPage(uri)) return false;
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, uri));
            } catch (ActivityNotFoundException ignored) {
            }
            return true;
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            pushInsets();
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) view.loadUrl(OFFLINE_PAGE);
        }
    }

    /** Funções que a página pode chamar (window.YAWEAndroid). */
    private class Bridge {
        @JavascriptInterface
        public boolean isApp() {
            return true;
        }

        @JavascriptInterface
        public String getServerUrl() {
            return serverUrl();
        }

        @JavascriptInterface
        public void saveServerUrl(String url) {
            String clean = url == null ? "" : url.trim();
            if (!clean.startsWith("http://") && !clean.startsWith("https://")) clean = "https://" + clean;
            while (clean.endsWith("/")) clean = clean.substring(0, clean.length() - 1);
            final String finalUrl = clean;
            prefs.edit().putString(KEY_URL, finalUrl).apply();
            runOnUiThread(() -> web.loadUrl(finalUrl));
        }

        @JavascriptInterface
        public void changeServer() {
            runOnUiThread(() -> web.loadUrl(SETUP_PAGE));
        }

        @JavascriptInterface
        public void retry() {
            runOnUiThread(MainActivity.this::openStart);
        }

        /** Devolve (e limpa) a ação pedida pelo widget: "listen", "course" ou "open". */
        @JavascriptInterface
        public String takeAction() {
            String a = pendingAction;
            pendingAction = null;
            return a;
        }

        /** A página envia o estado atual (nome, humor, sequência...) para o widget da tela inicial. */
        @JavascriptInterface
        public void updateWidget(String json) {
            try {
                JSONObject o = new JSONObject(json);
                getSharedPreferences(YaweWidget.PREFS, MODE_PRIVATE).edit()
                        .putString("name", o.optString("name", ""))
                        .putString("mood", o.optString("mood", ""))
                        .putString("line", o.optString("line", ""))
                        .putInt("streak", o.optInt("streak", 0))
                        .putInt("todayXp", o.optInt("todayXp", 0))
                        .putInt("goal", o.optInt("goal", 30))
                        .apply();
                YaweWidget.refresh(MainActivity.this);
                YaweLiveWidget.refresh(MainActivity.this);
            } catch (Exception ignored) {
            }
        }

        @JavascriptInterface
        public int statusBarHeight() {
            return statusBarDp();
        }

        @JavascriptInterface
        public boolean hasNativeWake() {
            return true;
        }

        /** Começa a escutar sem parar; o texto vai para window.yaweOnPartial / window.yaweOnFinal. */
        @JavascriptInterface
        public void startWake() {
            runOnUiThread(() -> {
                wantListening = true;
                ensureMicThenListen();
            });
        }

        @JavascriptInterface
        public void stopWake() {
            runOnUiThread(() -> {
                wantListening = false;
                stopRecognizer();
            });
        }

        /** Abre o reconhecimento de voz do Android; o texto volta em window.yaweOnSpeech(texto). */
        @JavascriptInterface
        public void listen() {
            runOnUiThread(() -> {
                Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR");
                intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Fale com o " + getString(R.string.app_name));
                try {
                    startActivityForResult(intent, REQ_SPEECH);
                } catch (ActivityNotFoundException e) {
                    Toast.makeText(MainActivity.this,
                            "Reconhecimento de voz indisponível. Instale/ative o app Google.",
                            Toast.LENGTH_LONG).show();
                    deliverSpeech(null);
                }
            });
        }
    }

    private void js(String code) {
        if (web != null) web.evaluateJavascript(code, null);
    }

    private void ensureMicThenListen() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
            return;
        }
        startRecognizer();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_MIC) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            if (wantListening) startRecognizer();
        } else {
            wantListening = false;
            js("window.yaweOnSpeechError && window.yaweOnSpeechError('permission')");
        }
    }

    private void startRecognizer() {
        if (!wantListening || listening) return;
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            wantListening = false;
            js("window.yaweOnSpeechError && window.yaweOnSpeechError('unavailable')");
            return;
        }
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(this);
            recognizer.setRecognitionListener(new Listener());
        }
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        intent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, getPackageName());
        try {
            recognizer.startListening(intent);
            listening = true;
        } catch (Exception e) {
            restartLater(1000, true);
        }
    }

    private void stopRecognizer() {
        handler.removeCallbacksAndMessages(null);
        listening = false;
        if (recognizer != null) {
            try {
                recognizer.cancel();
            } catch (Exception ignored) {
            }
        }
    }

    private void restartLater(long delayMs, boolean recreate) {
        listening = false;
        if (recreate && recognizer != null) {
            recognizer.destroy();
            recognizer = null;
        }
        handler.postDelayed(this::startRecognizer, delayMs);
    }

    private static String firstResult(Bundle b) {
        if (b == null) return null;
        ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        return (r == null || r.isEmpty()) ? null : r.get(0);
    }

    private class Listener implements RecognitionListener {
        @Override public void onReadyForSpeech(Bundle params) { }
        @Override public void onBeginningOfSpeech() { }
        @Override public void onRmsChanged(float rmsdB) { }
        @Override public void onBufferReceived(byte[] buffer) { }
        @Override public void onEndOfSpeech() { }
        @Override public void onEvent(int eventType, Bundle params) { }

        @Override
        public void onPartialResults(Bundle partialResults) {
            String text = firstResult(partialResults);
            if (text != null && !text.isEmpty()) {
                js("window.yaweOnPartial && window.yaweOnPartial(" + JSONObject.quote(text) + ")");
            }
        }

        @Override
        public void onResults(Bundle results) {
            String text = firstResult(results);
            js("window.yaweOnFinal && window.yaweOnFinal(" + JSONObject.quote(text == null ? "" : text) + ")");
            listening = false;
            if (wantListening) restartLater(150, false);
        }

        @Override
        public void onError(int error) {
            listening = false;
            if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                wantListening = false;
                js("window.yaweOnSpeechError && window.yaweOnSpeechError('permission')");
                return;
            }
            if (!wantListening) return;
            boolean recreate = error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY
                    || error == SpeechRecognizer.ERROR_CLIENT
                    || error == SpeechRecognizer.ERROR_SERVER;
            long delay = error == SpeechRecognizer.ERROR_NETWORK ? 2000 : 300;
            restartLater(delay, recreate);
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String action = intent.getStringExtra(EXTRA_ACTION);
        if (action != null) {
            pendingAction = action;
            js("window.yaweAction && window.yaweAction()");
        }
    }

    /** Com o app aberto o YAWE aparece acordado no widget; ao sair, volta às atividades dele. */
    private void setAwake(boolean awake) {
        getSharedPreferences(YaweWidget.PREFS, MODE_PRIVATE).edit()
                .putBoolean("awake", awake)
                .putLong("awakeAt", System.currentTimeMillis())
                .apply();
        YaweLiveWidget.refresh(this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        setAwake(true);
        if (wantListening && checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startRecognizer();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_SPEECH) return;
        String text = null;
        if (resultCode == RESULT_OK && data != null) {
            ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) text = results.get(0);
        }
        deliverSpeech(text);
    }

    private void deliverSpeech(String text) {
        String arg = text == null ? "null" : JSONObject.quote(text);
        web.evaluateJavascript("window.yaweOnSpeech && window.yaweOnSpeech(" + arg + ")", null);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopRecognizer(); // não escuta com o app em segundo plano
        setAwake(false);
        CookieManager.getInstance().flush(); // mantém o login salvo
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        stopRecognizer();
        if (recognizer != null) recognizer.destroy();
        if (web != null) {
            web.setVisibility(View.GONE);
            web.destroy();
        }
        super.onDestroy();
    }
}
