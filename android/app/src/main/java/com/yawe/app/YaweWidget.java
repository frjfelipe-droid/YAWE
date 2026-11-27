package com.yawe.app;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.widget.RemoteViews;

import java.util.Calendar;

/** Widget da tela inicial: a esfera do YAWE no humor atual, saudação e atalhos. */
public class YaweWidget extends AppWidgetProvider {

    static final String PREFS = "yawe_widget";

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        for (int id : ids) manager.updateAppWidget(id, build(context));
    }

    /** Redesenha todos os widgets com os dados mais recentes enviados pelo app. */
    static void refresh(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        int[] ids = manager.getAppWidgetIds(new ComponentName(context, YaweWidget.class));
        for (int id : ids) manager.updateAppWidget(id, build(context));
    }

    static RemoteViews build(Context c) {
        SharedPreferences p = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String name = p.getString("name", "");
        String mood = p.getString("mood", "");
        String line = p.getString("line", "");
        int streak = p.getInt("streak", 0);
        int xp = p.getInt("todayXp", 0);
        int goal = p.getInt("goal", 30);

        int hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY);
        String greet = hour < 5 ? "Boa madrugada" : hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
        if (mood.isEmpty()) mood = (hour >= 23 || hour < 6) ? "sonolento" : "calmo";

        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.widget_yawe);
        v.setImageViewResource(R.id.widget_orb, orbFor(mood));
        v.setTextViewText(R.id.widget_greet, greet + (name.isEmpty() ? "." : ","));
        v.setTextViewText(R.id.widget_name, name.isEmpty() ? "Estou aqui." : name + ".");
        v.setTextViewText(R.id.widget_line, line.isEmpty() ? "Toque para conversar comigo." : line);
        v.setTextViewText(R.id.widget_spanish, "🔥 " + streak + "  ·  " + xp + "/" + goal + " XP");

        v.setOnClickPendingIntent(R.id.widget_root, open(c, "open", 11));
        v.setOnClickPendingIntent(R.id.widget_orb, open(c, "open", 12));
        v.setOnClickPendingIntent(R.id.widget_talk, open(c, "listen", 13));
        v.setOnClickPendingIntent(R.id.widget_spanish, open(c, "course", 14));
        return v;
    }

    static PendingIntent open(Context c, String action, int requestCode) {
        Intent i = new Intent(c, MainActivity.class);
        i.putExtra(MainActivity.EXTRA_ACTION, action);
        i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(c, requestCode, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static int orbFor(String mood) {
        switch (mood) {
            case "feliz": return R.drawable.orb_feliz;
            case "curioso": return R.drawable.orb_curioso;
            case "animado": return R.drawable.orb_animado;
            case "pensativo": return R.drawable.orb_pensativo;
            case "sonolento": return R.drawable.orb_sonolento;
            case "preocupado": return R.drawable.orb_preocupado;
            default: return R.drawable.orb_calmo;
        }
    }
}
