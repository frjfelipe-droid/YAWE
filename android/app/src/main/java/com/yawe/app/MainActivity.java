package com.yawe.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONObject;

import java.util.ArrayList;

/**
 * App Android do YAWE: abre o servidor do YAWE em tela cheia e oferece o microfone
 * nativo do Android (reconhecimento de voz do Google) para a página.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "yawe";
    private static final String KEY_URL = "server_url";
    private static final int REQ_SPEECH = 42;
    private static final String SETUP_PAGE = "file:///android_asset/setup.html";
    private static final String OFFLINE_PAGE = "file:///android_asset/offline.html";

    private WebView web;
    private SharedPreferences prefs;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#F5F2FB"));
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false); // a voz toca sozinha após a resposta
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setUserAgentString(s.getUserAgentString() + " YAWEApp/1");

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);

        web.addJavascriptInterface(new Bridge(), "YAWEAndroid");
        web.setWebViewClient(new Client());

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
        CookieManager.getInstance().flush(); // mantém o login salvo
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.setVisibility(View.GONE);
            web.destroy();
        }
        super.onDestroy();
    }
}
