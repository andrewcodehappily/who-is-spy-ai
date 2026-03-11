#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
誰是臥底 - Flask 網頁：可調整參數、查看對戰記錄與完整對話／思考過程。
"""

import os
from flask import Flask, request, render_template, redirect, url_for, jsonify, flash

from dotenv import load_dotenv
load_dotenv()

try:
    from google.api_core.exceptions import ResourceExhausted
except ImportError:
    ResourceExhausted = None

from undercover import run_game, WORD_GROUPS, GROUP_OPTIONS

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# 存放對戰記錄（可改為存資料庫或 JSON 檔案）
GAME_RECORDS = []


@app.route("/")
def index():
    return render_template(
        "index.html",
        group_options=GROUP_OPTIONS,
        word_groups=WORD_GROUPS,
        records=reversed(GAME_RECORDS[-50:]),  # 最近 50 筆
    )


@app.route("/game/new", methods=["GET"])
def game_new_get():
    """GET /game/new 導回首頁，避免 404。"""
    return redirect(url_for("index"))


@app.route("/game/new", methods=["POST"])
def start_game():
    word_group = request.form.get("word_group", "隨機")
    try:
        num_players = int(request.form.get("num_players", 6))
    except ValueError:
        num_players = 6
    try:
        num_undercover = int(request.form.get("num_undercover", 1))
    except ValueError:
        num_undercover = 1
    model_name = request.form.get("model_name", "qwen3:4b").strip() or "qwen3:4b"

    num_players = max(3, min(12, num_players))
    num_undercover = max(1, min(num_players - 1, num_undercover))

    try:
        record = run_game(
            word_group_choice=word_group,
            num_players=num_players,
            num_undercover=num_undercover,
            model_name=model_name,
        )
        GAME_RECORDS.append(record)
        return redirect(url_for("game_detail", game_id=record["id"]))
    except Exception as e:
        if ResourceExhausted and isinstance(e, ResourceExhausted):
            flash(
                "API 配額已用盡（429）。請稍後再試，或改用其他模型（例如 gemini-1.5-flash）。"
                " 詳見：https://ai.google.dev/gemini-api/docs/rate-limits",
                "error",
            )
            return redirect(url_for("index"))
        raise


@app.route("/game/<game_id>")
def game_detail(game_id):
    record = next((r for r in GAME_RECORDS if r["id"] == game_id), None)
    if not record:
        return "找不到該局記錄", 404
    return render_template("game_detail.html", record=record, group_options=GROUP_OPTIONS)


@app.route("/api/game/new", methods=["POST"])
def api_start_game():
    """API：用 JSON 開新局，回傳 game_id 或完整 record。"""
    data = request.get_json() or {}
    word_group = data.get("word_group", "隨機")
    num_players = max(3, min(12, int(data.get("num_players", 6))))
    num_undercover = max(1, min(num_players - 1, int(data.get("num_undercover", 1))))
    model_name = data.get("model_name", "qwen3:4b") or "qwen3:4b"
    try:
        record = run_game(
            word_group_choice=word_group,
            num_players=num_players,
            num_undercover=num_undercover,
            model_name=model_name,
        )
        GAME_RECORDS.append(record)
        return jsonify({"game_id": record["id"], "record": record})
    except Exception as e:
        if ResourceExhausted and isinstance(e, ResourceExhausted):
            return jsonify({"error": "API quota exceeded (429). Try again later or use another model."}), 429
        raise


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
