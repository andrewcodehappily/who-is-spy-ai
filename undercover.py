#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
誰是臥底 AI 遊戲平台 (Who is Undercover AI)
支援模型：Ollama, Google Gemini, DeepSeek (OpenAI API 兼容)
特色：串流輸出、多樣性格、白板機制、臥底反殺、自動戰報、計分系統
"""

import os
import random
import re
import uuid
import time
import sys
import io
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 強制 stdout 使用 UTF-8 (修正 Windows 可能的編碼問題)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clear_screen():
    """清除終端機畫面。"""
    os.system('cls' if os.name == 'nt' else 'clear')

# --- 模型類型判定 ---

def _is_ollama_model(model_name):
    """模型名含 ':' 視為 Ollama（如 qwen3:4b）。"""
    return model_name and ":" in model_name

def _is_deepseek_model(model_name):
    """模型名含 'deepseek' 視為使用 DeepSeek API。"""
    return model_name and "deepseek" in model_name.lower()

# --- LLM 呼叫核心 ---

def _call_llm_with_timeout(prompt: str, model_name: str, stream: bool = False, show_thinking: bool = True, timeout: int = 300, temperature: float = 0.7) -> str:
    """具備超時機制的 LLM 呼叫包裝器。"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call_llm, prompt, model_name, stream, show_thinking, temperature)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            print(f"\n[系統錯誤] 模型回應超過 {timeout} 秒未完成，強制中斷。")
            return ""
        except Exception as e:
            print(f"\n[系統錯誤] 呼叫模型時發生意外錯誤：{e}")
            return ""

def _call_llm(prompt: str, model_name: str, stream: bool = False, show_thinking: bool = True, temperature: float = 0.7) -> str:
    """核心呼叫函式：依 model_name 分流至不同 Provider。"""
    
    # --- 1. DeepSeek 模式 (OpenAI 兼容) ---
    if _is_deepseek_model(model_name):
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=os.environ.get("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
            # R1 (reasoner) 不支援自定義 temperature
            is_reasoner = "reasoner" in model_name.lower()
            temp = None if is_reasoner else temperature

            if stream:
                full_content = ""
                printing_started = show_thinking
                buffer = ""
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    temperature=temp
                )
                for chunk in response:
                    # 抓取 DeepSeek R1 特有的思考過程
                    reasoning = getattr(chunk.choices[0].delta, 'reasoning_content', None)
                    content = chunk.choices[0].delta.content or ""
                    
                    if reasoning and show_thinking:
                        # 用灰色印出 R1 的內心思考
                        print(f"\033[90m{reasoning}\033[0m", end="", flush=True)
                    
                    if content:
                        full_content += content
                        if not printing_started:
                            buffer += content
                            if len(buffer) > 150:
                                print(buffer, end="", flush=True)
                                printing_started = True
                            else:
                                for marker in ["描述：", "描述:", "投票：", "投票:", "我的描述是：", "我的描述是:", "我選擇描述：", "我選擇描述:"]:
                                    if marker in buffer:
                                        _, tail = buffer.rsplit(marker, 1)
                                        print(f"{marker}{tail}", end="", flush=True)
                                        printing_started = True
                                        break
                        else:
                            print(content, end="", flush=True)
                print()
                return full_content
            else:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temp
                )
                return resp.choices[0].message.content
        except Exception as e:
            print(f"\n[系統提示] DeepSeek API 異常 ({e})")
            return ""

    # --- 2. Ollama 模式 ---
    elif _is_ollama_model(model_name):
        import ollama
        options = {"temperature": temperature, "top_p": 0.9}
        try:
            if stream:
                full_content = ""
                printing_started = show_thinking
                buffer = ""
                for chunk in ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}], stream=True, options=options):
                    content = (chunk.get("message") or {}).get("content") or ""
                    if content:
                        full_content += content
                        if not printing_started:
                            buffer += content
                            if len(buffer) > 150:
                                print(buffer, end="", flush=True)
                                printing_started = True
                            else:
                                for marker in ["描述：", "描述:", "投票：", "投票:", "我的描述是：", "我的描述是:", "我選擇描述：", "我選擇描述:"]:
                                    if marker in buffer:
                                        _, tail = buffer.rsplit(marker, 1)
                                        print(f"{marker}{tail}", end="", flush=True)
                                        printing_started = True
                                        break
                        else:
                            print(content, end="", flush=True)
                print()
                return full_content
            r = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}], options=options)
            return (r.get("message") or {}).get("content") or ""
        except Exception as e:
            print(f"\n[系統提示] Ollama 服務異常 ({e})")
            return ""

    # --- 3. Google Gemini 模式 ---
    else:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        model = genai.GenerativeModel(model_name)
        config = genai.types.GenerationConfig(temperature=temperature, top_p=0.9)
        try:
            if stream:
                full_content = ""
                printing_started = show_thinking
                buffer = ""
                response = model.generate_content(prompt, stream=True, generation_config=config)
                for chunk in response:
                    if chunk.text:
                        full_content += chunk.text
                        if not printing_started:
                            buffer += chunk.text
                            if len(buffer) > 150:
                                print(buffer, end="", flush=True)
                                printing_started = True
                            else:
                                for marker in ["描述：", "描述:", "投票：", "投票:", "我的描述是：", "我的描述是:", "我選擇描述：", "我選擇描述:"]:
                                    if marker in buffer:
                                        _, tail = buffer.rsplit(marker, 1)
                                        print(f"{marker}{tail}", end="", flush=True)
                                        printing_started = True
                                        break
                        else:
                            print(chunk.text, end="", flush=True)
                print()
                return full_content
            response = model.generate_content(prompt, generation_config=config)
            return (response.text or "").strip()
        except Exception as e:
            print(f"\n[系統提示] Gemini API 異常 ({e})")
            return ""

# --- 遊戲題庫與設定 ---

WORD_GROUPS = {
    "食物與飲品": [("豆漿", "牛奶"), ("火鍋", "麻辣燙"), ("小籠包", "蒸餃"), ("拿鐵", "卡布奇諾"), ("可樂", "百事可樂")],
    "生活用品": [("牙刷", "電動牙刷"), ("毛巾", "浴巾"), ("雨傘", "雨衣"), ("眼鏡", "隱形眼鏡")],
    "科技與電子": [("筆電", "桌機"), ("平板", "手機"), ("耳機", "音響"), ("充電線", "行動電源")],
    "休閒娛樂": [("電影", "電視劇"), ("漫畫", "小說"), ("唱歌", "跳舞"), ("露營", "野餐")],
    "影視類": [("甄嬛傳", "如懿傳"), ("復仇者聯盟", "正義聯盟")],
    "高難度類": [("勇氣", "毅力"), ("暗戀", "單戀"), ("初戀", "舊愛")],
}

GROUP_OPTIONS = ["隨機"] + list(WORD_GROUPS.keys())
ALL_PAIRS = [(group, pair) for group, pairs in WORD_GROUPS.items() for pair in pairs]
USED_PAIRS = []
PERSONALITIES = ["冷靜分析型", "熱情活潑型", "疑心病重型", "簡短省話型", "風向帶領者"]
SCOREBOARD = {}

# --- 遊戲核心邏輯函式 ---

def pick_word_pair(group_choice=None):
    global USED_PAIRS
    pool = ALL_PAIRS if not group_choice or group_choice == "隨機" else [(group_choice, p) for p in WORD_GROUPS.get(group_choice, [])]
    available = [p for p in pool if p not in USED_PAIRS]
    if not available:
        USED_PAIRS = []
        available = pool
    choice = random.choice(available)
    USED_PAIRS.append(choice)
    return choice

def assign_roles(num_players=6, num_undercover=1, num_whites=1, group_choice=None, human_id=None):
    group_name, (word_civ, word_und) = pick_word_pair(group_choice)
    roles = [("平民", word_civ)] * (num_players - num_undercover - num_whites)
    roles += [("臥底", word_und)] * num_undercover
    roles += [("白板", "???")] * num_whites
    random.shuffle(roles)
    
    player_data = []
    for i, r in enumerate(roles):
        player_data.append({
            "id": i, "role": r[0], "word": r[1],
            "personality": random.choice(PERSONALITIES),
            "is_human": (i == human_id)
        })
    return group_name, word_civ, word_und, player_data

def _parse_thinking_description(text):
    text = (text or "").strip()
    thinking, description = "", text
    m_think = re.search(r"思考[：:]\s*(.*?)(?=描述[：:]|$)", text, re.DOTALL)
    if m_think: thinking = m_think.group(1).strip()
    m_desc = re.search(r"描述[：:]\s*(.*)", text, re.DOTALL)
    if m_desc:
        description = m_desc.group(1).strip()
    else:
        # 防呆：若沒標籤則取最後一行
        description = text.split('\n')[-1].strip()
    return thinking[:100], description[:50]

def _parse_thinking_vote(text, alive):
    text = (text or "").strip()
    thinking, vote = "", None
    m_think = re.search(r"思考[：:]\s*(.*?)(?=(投票|最終決定)[：:]|$)", text, re.DOTALL)
    if m_think: thinking = m_think.group(1).strip()
    m_vote = re.search(r"投票[：:]\s*(\d+)", text)
    if m_vote:
        v = int(m_vote.group(1))
        if v in alive: vote = v
    if vote is None:
        vote = random.choice(alive)
    return thinking[:100], vote

def build_system_prompt(player_id, role, word, num_players, personality):
    role_info = f"你是【白板】，完全不知道詞彙！" if role == "白板" else f"你是【{role}】，詞彙是：「{word}」。"
    return f"""你正在參加「誰是臥底」遊戲（共 {num_players} 人）。你是【玩家 {player_id}】。
性格：【{personality}】。請全程以此性格分析與發言。
{role_info}
目標：平民要投出臥底；臥底/白板要生存並模仿平民。
格式規範：
描述階段：
思考：(30字內)
描述：(15字內的一句話)
投票階段：
思考：(30字內)
投票：(僅數字)"""

def get_description(model_name, player_id, role, word, history, round_no, num_players, personality, stream=False, show_thinking=True):
    system = build_system_prompt(player_id, role, word, num_players, personality)
    history_str = "\n".join(history[-10:])
    prompt = f"【第 {round_no} 輪描述】\n歷史：\n{history_str}\n請給出本輪描述："
    raw = _call_llm_with_timeout(f"{system}\n\n{prompt}", model_name, stream, show_thinking, temperature=0.5)
    t, d = _parse_thinking_description(raw)
    return {"raw": raw, "thinking": t, "description": d}

def get_vote(model_name, player_id, role, word, history, round_no, alive, num_players, personality, stream=False, show_thinking=True):
    system = build_system_prompt(player_id, role, word, num_players, personality)
    candidates = [a for a in alive if a != player_id]
    history_str = "\n".join(history[-15:])
    prompt = f"【第 {round_no} 輪投票】\n歷史：\n{history_str}\n存活玩家：{candidates}\n請投票："
    raw = _call_llm_with_timeout(f"{system}\n\n{prompt}", model_name, stream, show_thinking, temperature=0.3)
    t, v = _parse_thinking_vote(raw, candidates)
    return {"raw": raw, "thinking": t, "vote": v}

def spy_counter_kill(model_name, player_id, word, history, civilian_word, stream=False):
    prompt = f"你是臥底，被投出局了！猜測平民詞：\n遊戲記錄：\n{chr(10).join(history)}\n請直接輸出你猜的一個詞："
    guess = _call_llm_with_timeout(prompt, model_name, stream, show_thinking=False).strip().strip('。')
    return guess, guess == civilian_word

# --- 資料紀錄與顯示 ---

def save_game_record(record):
    os.makedirs("game_logs", exist_ok=True)
    fn = f"game_logs/game_{record['id'][:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(f"# 誰是臥底 戰報\n\n- 題組: {record['group_name']}\n- 贏家: {record['winner']}\n")
    return fn

def update_scoreboard(record):
    for p in record['roles']:
        pid = p['id']
        if pid not in SCOREBOARD: SCOREBOARD[pid] = {"win": 0, "loss": 0, "is_human": p['is_human']}
        if p['role'] == record['winner'] or (p['role'] in ["臥底", "白板"] and record['winner'] == "非平民陣營"):
            SCOREBOARD[pid]["win"] += 1
        else:
            SCOREBOARD[pid]["loss"] += 1

def print_scoreboard():
    print("\n" + "="*20 + " 累計計分板 " + "="*20)
    for pid, s in sorted(SCOREBOARD.items()):
        identity = "你" if s['is_human'] else "AI"
        win_rate = f"{(s['win']/(s['win']+s['loss']))*100:.1f}%" if (s['win']+s['loss']) > 0 else "0%"
        print(f"玩家{pid} ({identity}): 勝 {s['win']} / 負 {s['loss']} (勝率 {win_rate})")

# --- 主程式迴圈 ---

def run_game(word_group_choice="隨機", num_players=6, num_undercover=1, num_whites=1, model_name="qwen3:4b", stream=True, show_spoilers=False, show_thinking=True, human_id=None):
    group_name, word_civ, word_und, player_data = assign_roles(num_players, num_undercover, num_whites, word_group_choice, human_id)
    player_info = {p['id']: p for p in player_data}
    alive = [p['id'] for p in player_data]
    history_lines = []
    record = {"id": str(uuid.uuid4()), "group_name": group_name, "roles": player_data, "rounds": [], "winner": None}

    print(f"\n【遊戲開始】題組：{group_name} | 模式：{model_name}")
    if human_id is not None:
        p = player_info[human_id]
        print(f">>> [你是玩家 {human_id}] 你的詞是: {p['word'] if p['role'] != '白板' else '???'}")

    while True:
        round_no = len(record["rounds"]) + 1
        round_data = {"round": round_no, "descriptions": [], "votes": []}
        print(f"\n--- 第 {round_no} 輪 描述 ---")
        
        for pid in alive:
            p = player_info[pid]
            if p['is_human']:
                desc = input(f"玩家{pid} (你)，請輸入描述: ").strip()
                out = {"description": desc, "thinking": "人類玩家", "raw": desc}
            else:
                print(f"\n玩家{pid} ({p['personality']}) 思考中...")
                out = get_description(model_name, pid, p['role'], p['word'], history_lines, round_no, num_players, p['personality'], stream, show_thinking)
            
            history_lines.append(f"玩家{pid}：{out['description']}")
            round_data["descriptions"].append({"player_id": pid, "description": out["description"], "thinking": out["thinking"]})

        print(f"\n--- 第 {round_no} 輪 投票 ---")
        for pid in alive:
            p = player_info[pid]
            if p['is_human']:
                v_id = int(input(f"玩家{pid} (你)，投票給誰 { [a for a in alive if a != pid] }: "))
                out = {"vote": v_id, "thinking": "人類投票"}
            else:
                out = get_vote(model_name, pid, p['role'], p['word'], history_lines, round_no, alive, num_players, p['personality'], stream, show_thinking)
            round_data["votes"].append({"player_id": pid, "vote_to": out["vote"], "thinking": out["thinking"]})

        # 結算投票
        v_counts = {}
        for v in round_data["votes"]: v_counts[v["vote_to"]] = v_counts.get(v["vote_to"], 0) + 1
        eliminated = max(v_counts, key=v_counts.get)
        alive.remove(eliminated)
        print(f"\n【投票結果】玩家{eliminated} 被淘汰！(身分: {player_info[eliminated]['role']})")
        history_lines.append(f"玩家{eliminated} 被淘汰。")
        record["rounds"].append(round_data)

        # 檢查勝負
        non_civs = [pid for pid in alive if player_info[pid]['role'] in ["臥底", "白板"]]
        if player_info[eliminated]['role'] == "臥底":
            guess, correct = spy_counter_kill(model_name, eliminated, player_info[eliminated]['word'], history_lines, word_civ, stream)
            print(f"臥底反殺猜測：{guess}")
            if correct:
                print("🎯 猜對了！臥底獲勝！"); record["winner"] = "臥底"; break
        
        if not non_civs:
            print("🎉 平民獲勝！"); record["winner"] = "平民"; break
        if len([pid for pid in alive if player_info[pid]['role'] == "平民"]) <= 2:
            print("😈 非平民陣營獲勝！"); record["winner"] = "非平民陣營"; break
            
    return record

if __name__ == "__main__":
    clear_screen()
    print("=== 誰是臥底 AI 平台 (支援 DeepSeek/Ollama/Gemini) ===")
    user_play = input("親自遊玩？(y/N): ").lower() == 'y'
    model = os.environ.get("MODEL_NAME", "deepseek-chat")
    
    try:
        while True:
            rec = run_game(model_name=model, human_id=(random.randint(0, 5) if user_play else None))
            update_scoreboard(rec)
            print_scoreboard()
            if input("\n下一局？(Y/n): ").lower() == 'n': break
    except KeyboardInterrupt:
        print("\n遊戲結束。")