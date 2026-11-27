package com.yawe.app;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.view.View;
import android.widget.RemoteViews;

import java.util.Calendar;

/**
 * Widget "YAWE vivo": o personagem mora num retângulo e faz atividades conforme a hora
 * (dormir, café, celular, TV). Enquanto o app está aberto, ele aparece acordado e atento.
 */
public class YaweLiveWidget extends AppWidgetProvider {

    private static final long AWAKE_MS = 10 * 60 * 1000; // segurança: volta à rotina depois de 10 min

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        for (int id : ids) manager.updateAppWidget(id, build(context));
    }

    static void refresh(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        int[] ids = manager.getAppWidgetIds(new ComponentName(context, YaweLiveWidget.class));
        for (int id : ids) manager.updateAppWidget(id, build(context));
    }

    static RemoteViews build(Context c) {
        SharedPreferences p = c.getSharedPreferences(YaweWidget.PREFS, Context.MODE_PRIVATE);
        boolean awake = p.getBoolean("awake", false)
                && System.currentTimeMillis() - p.getLong("awakeAt", 0) < AWAKE_MS;
        String scene = awake ? "awake" : sceneNow(p.getString("mood", ""));

        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_live);
        v.removeAllViews(R.id.live_flipper);
        for (int res : frames(scene)) {
            RemoteViews frame = new RemoteViews(c.getPackageName(), R.layout.widget_live_frame);
            frame.setImageViewResource(R.id.live_frame, res);
            v.addView(R.id.live_flipper, frame);
        }
        v.setTextViewText(R.id.live_label, label(scene));
        v.setViewVisibility(R.id.live_bubble, awake ? View.VISIBLE : View.GONE);
        v.setViewVisibility(R.id.live_label, awake ? View.GONE : View.VISIBLE);
        // Tocar nele: abre o app, ele acorda e pergunta "Como posso ajudar?"
        v.setOnClickPendingIntent(R.id.live_root, YaweWidget.open(c, "wake", 21));
        v.setOnClickPendingIntent(R.id.live_talk, YaweWidget.open(c, "wake", 22));
        return v;
    }

    /** Atividade do momento: depende da hora; muda a cada meia hora, sem ficar trocando à toa. */
    static String sceneNow(String mood) {
        Calendar now = Calendar.getInstance();
        int h = now.get(Calendar.HOUR_OF_DAY);
        int slot = now.get(Calendar.DAY_OF_YEAR) * 48 + h * 2 + now.get(Calendar.MINUTE) / 30;
        if (h >= 23 || h < 6 || "sonolento".equals(mood)) return "sleep";
        String[] options;
        if (h < 9) options = new String[]{"coffee", "coffee", "phone"};
        else if (h < 12) options = new String[]{"phone", "coffee", "phone"};
        else if (h < 14) options = new String[]{"coffee", "phone", "tv"};
        else if (h < 18) options = new String[]{"phone", "tv", "coffee"};
        else options = new String[]{"tv", "tv", "phone"};
        int pick = (int) Math.floorMod(slot * 2654435761L, 1000003L); // "sorteio" fixo por meia hora
        return options[pick % options.length];
    }

    private static int[] frames(String scene) {
        switch (scene) {
            case "sleep": // respiração lenta: quadros repetidos deixam o ritmo mais calmo
                return new int[]{R.drawable.live_sleep0, R.drawable.live_sleep0, R.drawable.live_sleep1,
                        R.drawable.live_sleep2, R.drawable.live_sleep2, R.drawable.live_sleep1};
            case "coffee":
                return new int[]{R.drawable.live_coffee0, R.drawable.live_coffee1, R.drawable.live_coffee0,
                        R.drawable.live_coffee1, R.drawable.live_coffee2, R.drawable.live_coffee2};
            case "phone":
                return new int[]{R.drawable.live_phone0, R.drawable.live_phone1, R.drawable.live_phone0,
                        R.drawable.live_phone1, R.drawable.live_phone2};
            case "tv":
                return new int[]{R.drawable.live_tv0, R.drawable.live_tv1, R.drawable.live_tv2, R.drawable.live_tv3};
            default: // acordado e atento
                return new int[]{R.drawable.live_awake0, R.drawable.live_awake1, R.drawable.live_awake0,
                        R.drawable.live_awake2};
        }
    }

    private static String label(String scene) {
        switch (scene) {
            case "sleep": return "😴  dormindo";
            case "coffee": return "☕  tomando um café";
            case "phone": return "📱  no celular";
            case "tv": return "📺  assistindo";
            default: return "acordado";
        }
    }
}
