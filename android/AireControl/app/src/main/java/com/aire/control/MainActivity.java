package com.aire.control;

import android.Manifest;
import android.app.Activity;
import android.app.PendingIntent;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.atomic.AtomicInteger;

public class MainActivity extends Activity {
    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String RUN_PERMISSION = "com.termux.permission.RUN_COMMAND";
    private static final int REQ_TERMUX = 41;
    private static final String UPDATE_MANIFEST = "https://raw.githubusercontent.com/krodon998/aire-onebot-mcp/main/android/AireControl/latest.json";
    private static final AtomicInteger EXEC_ID = new AtomicInteger(1000);

    private TextView output;
    private EditText conversationInput;
    private EditText idleInput;
    private EditText repeatInput;
    private EditText startInput;
    private EditText endInput;
    private EditText groupInput;

    private final BroadcastReceiver uiReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String label = intent.getStringExtra("label");
            String stdout = intent.getStringExtra("stdout");
            String stderr = intent.getStringExtra("stderr");
            String errmsg = intent.getStringExtra("errmsg");
            int exit = intent.getIntExtra("exitCode", -999);

            StringBuilder text = new StringBuilder();
            text.append("[").append(label == null ? "command" : label).append("] exit=").append(exit).append("\n");
            if (stdout != null && !stdout.isBlank()) text.append(stdout.trim()).append("\n");
            if (stderr != null && !stderr.isBlank()) text.append("stderr:\n").append(stderr.trim()).append("\n");
            if (errmsg != null && !errmsg.isBlank()) text.append("termux: ").append(errmsg.trim()).append("\n");
            output.setText(text.toString().trim());
        }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        registerUiReceiver();
        setContentView(buildUi());
        ensureTermuxPermission();
    }

    private void registerUiReceiver() {
        IntentFilter filter = new IntentFilter(CommandResultReceiver.ACTION_UI_RESULT);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(uiReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(uiReceiver, filter);
        }
    }

    @Override
    protected void onDestroy() {
        try { unregisterReceiver(uiReceiver); } catch (Exception ignored) {}
        super.onDestroy();
    }

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(20), dp(18), dp(32));
        root.setBackgroundColor(Color.rgb(246, 250, 255));
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView title = text("Aire Control", 28, true);
        root.addView(title);
        TextView subtitle = text("RikkaHub · Heartbeat · QQ/NapCat · AireOneBot", 13, false);
        subtitle.setTextColor(Color.DKGRAY);
        root.addView(subtitle, lp(0, 0, 0, 6));

        TextView version = text("v" + BuildConfig.VERSION_NAME, 12, false);
        version.setTextColor(Color.GRAY);
        root.addView(version, lp(0, 0, 0, 8));

        LinearLayout updateRow = row();
        updateRow.addView(button("检查更新", v -> checkForUpdates()), weight());
        updateRow.addView(button("同步控制脚本", v -> syncScripts()), weight());
        root.addView(updateRow, lp(0, 0, 0, 14));

        TextView notice = text(
                "第一次使用：Termux 需要 allow-external-apps=true，并给本 App 授予「Run commands in Termux environment」。之后大部分操作都可以只在这里点。",
                13, false);
        root.addView(notice, lp(0, 0, 0, 10));

        LinearLayout setupRow = row();
        setupRow.addView(button("复制一次性 Termux 设置", v -> copyTermuxSetup()), weight());
        setupRow.addView(button("权限设置", v -> openOwnSettings()), weight());
        root.addView(setupRow, lp(0, 0, 0, 16));

        section(root, "整套状态 / 恢复");
        LinearLayout statusRow = row();
        statusRow.addView(button("刷新状态", v -> runAireCtl("status", "status")), weight());
        statusRow.addView(button("一键恢复", v -> runAireCtl("recover", "recover")), weight());
        root.addView(statusRow);
        root.addView(button("打开 QQ 登录 / noVNC", v -> openUrl("http://127.0.0.1:6080/vnc.html")), lp(0, 8, 0, 14));

        section(root, "RikkaHub 绑定窗口");
        conversationInput = edit("↑Aire02");
        root.addView(conversationInput);
        LinearLayout convoRow = row();
        convoRow.addView(button("查会话 / UUID", v -> runAireCtl("uuid " + sh(conversationInput.getText().toString()), "uuid")), weight());
        convoRow.addView(button("绑定这个窗口", v -> runAireCtl("target " + sh(conversationInput.getText().toString()), "target")), weight());
        root.addView(convoRow, lp(0, 8, 0, 14));

        section(root, "Heartbeat");
        LinearLayout h1 = row();
        idleInput = smallNumber("60");
        repeatInput = smallNumber("180");
        h1.addView(labeled("安静分钟", idleInput), weight());
        h1.addView(labeled("最短间隔", repeatInput), weight());
        root.addView(h1);

        LinearLayout h2 = row();
        startInput = edit("00:00");
        endInput = edit("23:59");
        h2.addView(labeled("开始", startInput), weight());
        h2.addView(labeled("结束", endInput), weight());
        root.addView(h2, lp(0, 8, 0, 0));

        LinearLayout hButtons = row();
        hButtons.addView(button("应用并启用", v -> applyHeartbeat()), weight());
        hButtons.addView(button("停用", v -> runAireCtl("heartbeat set --disable", "heartbeat off")), weight());
        root.addView(hButtons, lp(0, 8, 0, 0));

        LinearLayout hMore = row();
        hMore.addView(button("查看当前设置", v -> runAireCtl("heartbeat show", "heartbeat show")), weight());
        hMore.addView(button("高级 Heartbeat 页面", v -> openHeartbeatPanel()), weight());
        root.addView(hMore, lp(0, 8, 0, 14));

        section(root, "QQ 群接收白名单");
        groupInput = edit("群名或群号");
        root.addView(groupInput);
        LinearLayout g1 = row();
        g1.addView(button("列出已加入群", v -> runAireCtl("groups list", "groups")), weight());
        g1.addView(button("只监听这个群", v -> {
            String value = groupInput.getText().toString().trim();
            if (value.isEmpty()) {
                toast("先填群名或群号");
                return;
            }
            runAireCtl("groups watch " + sh(value), "watch group");
        }), weight());
        root.addView(g1, lp(0, 8, 0, 0));
        root.addView(button("关闭群监听并清空白名单", v -> runAireCtl("groups clear", "clear groups")), lp(0, 8, 0, 14));

        section(root, "输出");
        output = text("等你点一下。", 13, false);
        output.setTextIsSelectable(true);
        output.setTypeface(android.graphics.Typeface.MONOSPACE);
        output.setPadding(dp(12), dp(12), dp(12), dp(12));
        output.setBackgroundColor(Color.WHITE);
        root.addView(output, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(220)));

        root.addView(button("复制输出", v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("Aire Control", output.getText()));
            toast("已复制");
        }), lp(0, 8, 0, 0));

        return scroll;
    }

    private void syncScripts() {
        String cmd =
                "cd /opt/aire-onebot-mcp && python3 - <<'PY'\n" +
                "from pathlib import Path\n" +
                "from urllib.request import Request, urlopen\n" +
                "import os, time\n" +
                "base='https://raw.githubusercontent.com/krodon998/aire-onebot-mcp/main/'\n" +
                "files=['airectl.py','qq_watch.py','MOBILE_TOOLKIT_zh.md']\n" +
                "for name in files:\n" +
                "    last=None\n" +
                "    for attempt in range(3):\n" +
                "        try:\n" +
                "            req=Request(base+name, headers={'User-Agent':'AireControl/0.3'})\n" +
                "            data=urlopen(req, timeout=12).read()\n" +
                "            if not data:\n" +
                "                raise RuntimeError('empty download')\n" +
                "            tmp=Path(name+'.tmp')\n" +
                "            tmp.write_bytes(data)\n" +
                "            os.replace(tmp, Path(name))\n" +
                "            print(name+': updated')\n" +
                "            break\n" +
                "        except Exception as e:\n" +
                "            last=e\n" +
                "            if attempt == 2:\n" +
                "                raise\n" +
                "            time.sleep(1.2*(attempt+1))\n" +
                "PY";
        runUbuntu(cmd, "sync scripts");
    }

    private void checkForUpdates() {
        output.setText("[update] 检查中…");
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(UPDATE_MANIFEST + "?t=" + System.currentTimeMillis());
                conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(5000);
                conn.setRequestProperty("Cache-Control", "no-cache");
                try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream()))) {
                    StringBuilder body = new StringBuilder();
                    String line;
                    while ((line = br.readLine()) != null) body.append(line);
                    JSONObject j = new JSONObject(body.toString());
                    int latestCode = j.getInt("version_code");
                    String latestName = j.optString("version_name", "?");
                    String downloadUrl = j.optString("download_url", "");
                    String notes = j.optString("notes", "");

                    runOnUiThread(() -> {
                        output.setText("[update]\n当前 v" + BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + ")" +
                                "\n最新 v" + latestName + " (" + latestCode + ")");
                        if (latestCode > BuildConfig.VERSION_CODE) {
                            new AlertDialog.Builder(this)
                                    .setTitle("发现 Aire Control v" + latestName)
                                    .setMessage(notes.isBlank() ? "有新版本可用。" : notes)
                                    .setNegativeButton("稍后", null)
                                    .setPositiveButton("下载更新", (d, w) -> {
                                        if (!downloadUrl.isBlank()) openUrl(downloadUrl);
                                    })
                                    .show();
                        } else {
                            new AlertDialog.Builder(this)
                                    .setTitle("已经是最新版")
                                    .setMessage("当前版本：v" + BuildConfig.VERSION_NAME)
                                    .setPositiveButton("好", null)
                                    .show();
                        }
                    });
                }
            } catch (Exception e) {
                runOnUiThread(() -> output.setText("[update] 检查失败\n" + e.getClass().getSimpleName() + ": " + e.getMessage()));
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    private void applyHeartbeat() {
        String idle = idleInput.getText().toString().trim();
        String repeat = repeatInput.getText().toString().trim();
        String start = startInput.getText().toString().trim();
        String end = endInput.getText().toString().trim();
        if (!idle.matches("\\d+") || !repeat.matches("\\d+")) {
            toast("分钟数要填整数");
            return;
        }
        if (!start.matches("([01]\\d|2[0-3]):[0-5]\\d") || !end.matches("([01]\\d|2[0-3]):[0-5]\\d")) {
            toast("时间格式用 HH:MM");
            return;
        }
        String args = "heartbeat set --idle " + idle + " --repeat " + repeat +
                " --start " + sh(start) + " --end " + sh(end) + " --enable";
        runAireCtl(args, "heartbeat apply");
    }

    private void openHeartbeatPanel() {
        String cmd = "cd /opt/aire-onebot-mcp/rikkahub-heartbeat && " +
                "(pgrep -f 'python3 webui.py' >/dev/null || nohup python3 webui.py >/tmp/rikkahub-heartbeat-webui.log 2>&1 &)";
        runUbuntu(cmd, "heartbeat webui");
        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            Intent i = new Intent(this, WebViewActivity.class);
            i.putExtra("url", "http://127.0.0.1:8767/");
            startActivity(i);
        }, 900);
    }

    private void copyTermuxSetup() {
        String cmd = "mkdir -p ~/.termux && touch ~/.termux/termux.properties && " +
                "(grep -q '^allow-external-apps=true$' ~/.termux/termux.properties || " +
                "echo 'allow-external-apps=true' >> ~/.termux/termux.properties) && termux-reload-settings";
        ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        cm.setPrimaryClip(ClipData.newPlainText("Termux setup", cmd));
        toast("已复制。只需在 Termux 里运行一次。");
    }

    private void openOwnSettings() {
        Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.parse("package:" + getPackageName()));
        startActivity(i);
    }

    private void ensureTermuxPermission() {
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(RUN_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{RUN_PERMISSION}, REQ_TERMUX);
        }
    }

    private void runAireCtl(String args, String label) {
        runUbuntu("cd /opt/aire-onebot-mcp && python3 airectl.py " + args, label);
    }

    private void runUbuntu(String command, String label) {
        String path = "/data/data/com.termux/files/usr/bin/proot-distro";
        String[] args = new String[]{"login", "ubuntu", "--", "bash", "-lc", command};
        runTermux(path, args, label);
    }

    private void runTermux(String path, String[] args, String label) {
        if (!isTermuxInstalled()) {
            output.setText("Termux 未安装或当前不是 com.termux 包。");
            return;
        }
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(RUN_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            ensureTermuxPermission();
            output.setText("先授予「Run commands in Termux environment」权限。");
            return;
        }

        int requestCode = EXEC_ID.incrementAndGet();
        Intent resultIntent = new Intent(this, CommandResultReceiver.class);
        resultIntent.putExtra(CommandResultReceiver.EXTRA_LABEL, label);
        int flags = PendingIntent.FLAG_ONE_SHOT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) flags |= PendingIntent.FLAG_MUTABLE;
        PendingIntent pending = PendingIntent.getBroadcast(this, requestCode, resultIntent, flags);

        Intent intent = new Intent();
        intent.setClassName(TERMUX_PACKAGE, "com.termux.app.RunCommandService");
        intent.setAction("com.termux.RUN_COMMAND");
        intent.putExtra("com.termux.RUN_COMMAND_PATH", path);
        intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", args);
        intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
        intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
        intent.putExtra("com.termux.RUN_COMMAND_PENDING_INTENT", pending);

        try {
            output.setText("[" + label + "] 运行中…");
            startService(intent);
        } catch (Exception e) {
            output.setText("启动 Termux 命令失败：\n" + e.getClass().getSimpleName() + ": " + e.getMessage() +
                    "\n\n确认 allow-external-apps=true，并检查 App 权限。");
        }
    }

    private boolean isTermuxInstalled() {
        try {
            getPackageManager().getPackageInfo(TERMUX_PACKAGE, 0);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private String sh(String value) {
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }

    private void openUrl(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            output.setText("打不开：" + url);
        }
    }

    private LinearLayout row() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.HORIZONTAL);
        return l;
    }

    private LinearLayout.LayoutParams weight() {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        p.setMargins(dp(3), dp(3), dp(3), dp(3));
        return p;
    }

    private LinearLayout.LayoutParams lp(int l, int t, int r, int b) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.setMargins(dp(l), dp(t), dp(r), dp(b));
        return p;
    }

    private TextView text(String value, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(sp);
        t.setTextColor(Color.rgb(25, 35, 50));
        if (bold) t.setTypeface(null, android.graphics.Typeface.BOLD);
        return t;
    }

    private void section(LinearLayout root, String value) {
        TextView t = text(value, 18, true);
        t.setTextColor(Color.rgb(35, 95, 155));
        root.addView(t, lp(0, 8, 0, 6));
    }

    private Button button(String value, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(value);
        b.setAllCaps(false);
        b.setOnClickListener(listener);
        return b;
    }

    private EditText edit(String hint) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setSingleLine(true);
        e.setPadding(dp(10), dp(6), dp(10), dp(6));
        return e;
    }

    private EditText smallNumber(String value) {
        EditText e = edit(value);
        e.setText(value);
        e.setInputType(InputType.TYPE_CLASS_NUMBER);
        return e;
    }

    private LinearLayout labeled(String label, EditText field) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.addView(text(label, 12, false));
        box.addView(field, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return box;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }
}
