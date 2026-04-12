#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
誰是臥底 - Flask 網頁版（已適配最新雙後端 + 白板 + 思考過程）
"""

import os
from flask import Flask, request, render_template, redirect, url_for, jsonify, flash

from dotenv import load_dotenv
load_dotenv()

# 從你剛剛最新版的 who_is_undercover 導入需要的函數和變數
# 注意：你的主程式檔名如果是 who_is_undercover.py，這裡就要 import who_is_undercover
from who_is_undercover import run_game, WORD_GROUPS, GROUP_OPTIONS, BACKEND_OLLAMA, BACKEND_GROQ

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "andrew-is-awesome-6th-grader")

# 存放對戰記錄（伺服器重開就會不見，純展示用）
GAME_RECORDS = []

@app.route("/")
def index():
    return render_template(
        "index.html",
        group_options=GROUP_OPTIONS,
        word_groups=WORD_GROUPS,
        records=reversed(GAME_RECORDS[-50:]),  # 顯示最近 50 筆吃瓜紀錄
    )

@app.route("/game/new", methods=["GET"])
def game_new_get():
    """避免有人在網址列亂敲 GET /game/new 導致 404"""
    return redirect(url_for("index"))

@app.route("/game/new", methods=["POST"])
def start_game():
    # 抓取前端表單送來的參數
    word_group = request.form.get("word_group", "隨機")
    backend = request.form.get("backend", BACKEND_OLLAMA)
    model_name = request.form.get("model_name", "qwen2.5:1.5b").strip() or "qwen2.5:1.5b"
    
    try:
        num_players = int(request.form.get("num_players", 6))
    except ValueError:
        num_players = 6
        
    try:
        num_undercover = int(request.form.get("num_undercover", 1))
    except ValueError:
        num_undercover = 1
        
    try:
        num_whites = int(request.form.get("num_whites", 1))
    except ValueError:
        num_whites = 1

    # 防呆機制：六年級的同學亂輸入數字也不怕
    num_players = max(3, min(12, num_players))
    # 臥底+白板不能大於或等於總人數，不然平民太可憐了
    if num_undercover + num_whites >= num_players:
        num_undercover = 1
        num_whites = 0

    try:
        # 呼叫你強大的新版 run_game
        record = run_game(
            word_group_choice=word_group,
            num_players=num_players,
            num_undercover=num_undercover,
            num_whites=num_whites,
            model_name=model_name,
            backend=backend,
            stream=False,         # 網頁版等它全部跑完再顯示，不串流印在終端機
            show_spoilers=True,   # 網頁版就是上帝視角觀戰
            show_thinking=True,   # 把 AI 內心戲也抓出來
            human_id=None         # 網頁版暫時做全 AI 大亂鬥
        )
        GAME_RECORDS.append(record)
        return redirect(url_for("game_detail", game_id=record["id"]))
    except Exception as e:
        # 限流或是任何出錯都抓起來，顯示在網頁上
        if "rate limit" in str(e).lower() or "429" in str(e):
            flash("API 額度被你榨乾啦（429 限流）！換個 Key、等一下，或是改用本地 Ollama 吧！", "error")
        else:
            flash(f"遊戲伺服器被 AI 搞崩潰啦：{str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/game/<game_id>")
def game_detail(game_id):
    # 尋找歷史紀錄
    record = next((r for r in GAME_RECORDS if r["id"] == game_id), None)
    if not record:
        return "找不到該局記錄，難道被臥底偷走了？", 404
    return render_template("game_detail.html", record=record, group_options=GROUP_OPTIONS)

@app.route("/api/game/new", methods=["POST"])
def api_start_game():
    """API：用 JSON 開新局，適合用來寫自動化腳本"""
    data = request.get_json() or {}
    word_group = data.get("word_group", "隨機")
    num_players = max(3, min(12, int(data.get("num_players", 6))))
    num_undercover = int(data.get("num_undercover", 1))
    num_whites = int(data.get("num_whites", 1))
    backend = data.get("backend", BACKEND_OLLAMA)
    model_name = data.get("model_name", "qwen2.5:1.5b") or "qwen2.5:1.5b"
    
    if num_undercover + num_whites >= num_players:
        num_undercover = 1
        num_whites = 0

    try:
        record = run_game(
            word_group_choice=word_group,
            num_players=num_players,
            num_undercover=num_undercover,
            num_whites=num_whites,
            model_name=model_name,
            backend=backend,
            stream=False,
            show_spoilers=True,
            show_thinking=True,
            human_id=None
        )
        GAME_RECORDS.append(record)
        return jsonify({"game_id": record["id"], "record": record})
    except Exception as e:
        return jsonify({"error": f"出事啦: {str(e)}"}), 500

if __name__ == "__main__":
    # 預設跑在 5050 port，打開瀏覽器看好戲囉
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)