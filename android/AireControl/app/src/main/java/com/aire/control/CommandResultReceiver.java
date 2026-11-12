package com.aire.control;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

public class CommandResultReceiver extends BroadcastReceiver {
    public static final String ACTION_UI_RESULT = "com.aire.control.UI_RESULT";
    public static final String EXTRA_LABEL = "label";

    @Override
    public void onReceive(Context context, Intent intent) {
        Bundle result = intent.getBundleExtra("result");
        String label = intent.getStringExtra(EXTRA_LABEL);
        String stdout = "";
        String stderr = "";
        int exitCode = -999;
        String errmsg = "";

        if (result != null) {
            stdout = result.getString("stdout", "");
            stderr = result.getString("stderr", "");
            exitCode = result.getInt("exitCode", -999);
            errmsg = result.getString("errmsg", "");
        }

        Intent ui = new Intent(ACTION_UI_RESULT);
        ui.setPackage(context.getPackageName());
        ui.putExtra("label", label == null ? "command" : label);
        ui.putExtra("stdout", stdout);
        ui.putExtra("stderr", stderr);
        ui.putExtra("exitCode", exitCode);
        ui.putExtra("errmsg", errmsg);
        context.sendBroadcast(ui);
    }
}
