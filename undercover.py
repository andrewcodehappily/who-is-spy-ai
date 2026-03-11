#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
誰是臥底 - N 人局，可選題組、人數、臥底數。支援 Ollama（如 qwen3:4b）或 Google Gemini。
"""

import os
import random
import re
import uuid
import time
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError

def clear_screen():
    """清除終端機畫面。"""
    os.system('cls' if os.name == 'nt' else 'clear')

from dotenv import load_dotenv
load_dotenv()


def _is_ollama_model(model_name):
    """模型名含 ':' 視為 Ollama（如 qwen3:4b）。"""
    return model_name and ":" in model_name


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
    """依 model_name 呼叫 Ollama 或 Gemini，回傳模型輸出的純文字。"""
    options = {
        "temperature": temperature,
        "top_p": 0.9,
    }
    if _is_ollama_model(model_name):
        import ollama
        try:
            if stream:
                full_content = ""
                printing_started = show_thinking
                buffer = ""
                for chunk in ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}], stream=True, options=options):
                    content = (chunk.get("message") or {}).get("content") or ""
                    if content:
                        full_content += content
                        # 如果開啟顯示思考，但模型開始輸出 Markdown 標題，過濾掉標題行
                        if show_thinking and content.startswith("#"):
                            continue
                        
                        if not printing_started:
                            buffer += content
                            # 如果 buffer 累積超過 150 字還沒看到 marker，強制切換
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
                            # 如果已經開始印，但字數爆炸（可能是胡言亂語），強制截斷顯示
                            if len(full_content) > 1000:
                                print("\n[系統強制截斷過長回覆...]")
                                break
                # 若結束時還沒開始印 (通常是 show_thinking=False 且沒抓到 marker)
                if not printing_started and buffer:
                    print(buffer, end="", flush=True)
                print()
                return full_content
            r = ollama.chat(model=model_name, messages=[{"role": "user", "content": prompt}], options=options)
            return (r.get("message") or {}).get("content") or ""
        except Exception as e:
            # 針對 Ollama 可能的連線錯誤進行重試前的提示
            print(f"\n[系統提示] Ollama 服務回應異常 ({e})，準備重試...")
            time.sleep(2)
            return ""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(model_name)
    generation_config = genai.types.GenerationConfig(**options)
    if stream:
        full_content = ""
        printing_started = show_thinking
        buffer = ""
        response = model.generate_content(prompt, stream=True, generation_config=generation_config)
        for chunk in response:
            if chunk.text:
                full_content += chunk.text
                if show_thinking and chunk.text.startswith("#"):
                    continue
                
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
                    if len(full_content) > 1000:
                        print("\n[系統強制截斷過長回覆...]")
                        break
        if not printing_started and buffer:
            print(buffer, end="", flush=True)
        print()
        return full_content
    response = model.generate_content(prompt, generation_config=generation_config)
    return (response.text or "").strip()

# 題庫：分類詞對 (平民詞, 臥底詞)
WORD_GROUPS = {
    "食物與飲品": [
        ("豆漿", "牛奶"), ("火鍋", "麻辣燙"), ("小籠包", "蒸餃"), ("拿鐵", "卡布奇諾"), ("可樂", "百事可樂"),
        ("炸雞", "烤雞"), ("壽司", "生魚片"), ("三明治", "漢堡"), ("拉麵", "泡麵"), ("巧克力", "糖果"),
        ("紅酒", "葡萄汁"), ("綠茶", "烏龍茶"), ("披薩", "派"), ("鬆餅", "蛋糕"), ("鳳梨酥", "太陽餅"),
        ("貢丸", "魚丸"), ("燒烤", "熱炒"), ("布丁", "果凍"), ("芒果", "木瓜"), ("檸檬", "葡萄柚")
    ],
    "生活用品": [
        ("牙刷", "電動牙刷"), ("毛巾", "浴巾"), ("梳子", "髮夾"), ("洗髮精", "沐浴乳"), ("洗衣粉", "柔軟精"),
        ("雨傘", "雨衣"), ("口罩", "眼罩"), ("鬧鐘", "手錶"), ("枕頭", "抱枕"), ("指甲剪", "銼刀"),
        ("熱水瓶", "保溫瓶"), ("垃圾桶", "資源回收桶"), ("拖鞋", "涼鞋"), ("眼鏡", "隱形眼鏡"), ("唇膏", "護唇膏"),
        ("打火機", "火柴"), ("膠水", "膠帶"), ("計算機", "電腦"), ("掃帚", "拖把"), ("抹布", "菜瓜布")
    ],
    "科技與電子": [
        ("筆電", "桌機"), ("平板", "手機"), ("耳機", "音響"), ("滑鼠", "觸控板"), ("隨身碟", "硬碟"),
        ("網路", "Wi-Fi"), ("相機", "攝影機"), ("印表機", "影印機"), ("充電線", "行動電源"), ("藍牙", "紅外線"),
        ("電視", "投影機"), ("簡訊", "Line"), ("FB", "IG"), ("Google", "Baidu"), ("抖音", "YouTube")
    ],
    "休閒娛樂": [
        ("電影", "電視劇"), ("漫畫", "小說"), ("唱歌", "跳舞"), ("逛街", "散步"), ("露營", "野餐"),
        ("狼人殺", "劇本殺"), ("撲克牌", "麻將"), ("健身", "瑜珈"), ("游泳", "潛水"), ("攀岩", "登山"),
        ("鋼琴", "小提琴"), ("籃球", "排球"), ("足球", "橄欖球"), ("慢跑", "快走"), ("遊樂園", "動物園")
    ],
    "職業與角色": [
        ("醫生", "護士"), ("老師", "教授"), ("警察", "保全"), ("律師", "法官"), ("記者", "編輯"),
        ("廚師", "服務生"), ("司機", "導遊"), ("明星", "網紅"), ("老闆", "經理"), ("學生", "學徒"),
        ("爸爸", "叔叔"), ("外公", "爺爺"), ("英雄", "超人"), ("偵探", "間諜"), ("海盜", "山賊")
    ],
    "地點與交通": [
        ("捷運", "公車"), ("高鐵", "火車"), ("飛機", "直升機"), ("腳踏車", "滑板車"), ("計程車", "Uber"),
        ("飯店", "民宿"), ("超商", "超市"), ("圖書館", "書店"), ("公園", "操場"), ("海邊", "泳池"),
        ("廚房", "浴室"), ("客廳", "臥室"), ("辦公室", "會議室"), ("電梯", "樓梯"), ("馬路", "巷子")
    ],
    "動物與自然": [
        ("老虎", "獅子"), ("貓", "豹"), ("狗", "狼"), ("企鵝", "鴕鳥"), ("蝴蝶", "飛蛾"),
        ("蜜蜂", "黃蜂"), ("海豚", "鯨魚"), ("玫瑰", "牡丹"), ("森林", "叢林"), ("沙漠", "荒野"),
        ("閃電", "雷聲"), ("颱風", "地震"), ("月亮", "星星"), ("太陽", "夕陽"), ("雲", "霧")
    ],
    "抽象名詞": [
        ("寂寞", "孤獨"), ("夢想", "理想"), ("幽默", "搞笑"), ("妒忌", "羨慕"), ("勇氣", "毅力"),
        ("暗戀", "單戀"), ("初戀", "舊愛"), ("財富", "成功"), ("智慧", "知識"), ("自由", "獨立"),
        ("藝術", "技術"), ("和平", "安靜"), ("憤怒", "悲傷"), ("溫暖", "炎熱"), ("尷尬", "害羞")
    ],
    "影視類": [
        ("甄嬛傳", "如懿傳"),
        ("復仇者聯盟", "正義聯盟"),
        ("鐵達尼號", "變形金剛"),
    ],
    "經典入門組": [
        ("水餃", "鍋貼"),
        ("牛奶", "豆漿"),
        ("泡麵", "麵條"),
        ("西瓜", "哈密瓜"),
        ("腳踏車", "摩托車"),
        ("醫生", "護士"),
        ("手機", "電話"),
    ],
    "進階混淆組": [
        ("燒肉", "火鍋"),
        ("鬧鐘", "生理時鐘"),
        ("麵包", "蛋糕"),
        ("唇膏", "護唇膏"),
        ("洗髮精", "沐浴乳"),
        ("蝴蝶", "飛蛾"),
        ("眼藥水", "隱形眼鏡液"),
    ],
    "高難度腦力組": [
        ("媽媽", "飼育員"),
        ("勇氣", "毅力"),
        ("暗戀", "單戀"),
        ("初戀", "舊愛"),
        ("保險箱", "存錢筒"),
        ("散步", "逛街"),
        ("英雄", "豪傑"),
    ],
    "趣味情境組": [
        ("元宵", "湯圓"),
        ("小籠包", "燒賣"),
        ("婚紗", "禮服"),
        ("導遊", "領隊"),
        ("教授", "老師"),
        ("雨傘", "雨衣"),
    ],
}

GROUP_OPTIONS = ["隨機"] + list(WORD_GROUPS.keys())
ALL_PAIRS = [
    (group_name, pair) for group_name, pairs in WORD_GROUPS.items() for pair in pairs
]

USED_PAIRS = []

PERSONALITIES = ["冷靜分析型", "熱情活潑型", "疑心病重型", "簡短省話型", "風向帶領者"]


def pick_word_pair(group_choice=None):
    """group_choice: None 或 '隨機' = 全部隨機；否則為指定組名。"""
    global USED_PAIRS
    # 建立目前可選的所有清單
    if group_choice and group_choice != "隨機" and group_choice in WORD_GROUPS:
        pool = [(group_choice, p) for p in WORD_GROUPS[group_choice]]
    else:
        pool = ALL_PAIRS

    # 找出還沒用過的
    available = [p for p in pool if p not in USED_PAIRS]
    
    # 如果用完了，自動清空記錄重新開始，並提示玩家
    if not available:
        print("\n[系統提示] 題庫已全部玩過一遍，重新洗牌中...")
        USED_PAIRS = []
        available = pool
        
    choice = random.choice(available)
    USED_PAIRS.append(choice)
    return choice


def assign_roles(num_players=6, num_undercover=1, num_whites=1, group_choice=None, human_id=None):
    """N 人：平民、臥底、白板分配。"""
    group_name, (word_civilian, word_undercover) = pick_word_pair(group_choice)
    roles = []
    
    # 確保人數邏輯正確
    num_whites = max(0, num_whites)
    num_undercover = max(0, num_undercover)
    num_civilians = max(1, num_players - num_undercover - num_whites)
    
    # 分配平民
    for _ in range(num_civilians):
        roles.append(("平民", word_civilian))
    # 分配臥底
    for _ in range(num_undercover):
        roles.append(("臥底", word_undercover))
    # 分配白板
    for _ in range(num_whites):
        roles.append(("白板", "???"))
        
    random.shuffle(roles)
    
    player_data = []
    for i, r in enumerate(roles):
        p_type = random.choice(PERSONALITIES)
        is_human = (i == human_id)
        player_data.append({
            "id": i,
            "role": r[0],
            "word": r[1],
            "personality": p_type,
            "is_human": is_human
        })
    return group_name, word_civilian, word_undercover, player_data


def _parse_thinking_description(text):
    """從模型回覆中解析 思考：... 描述：...，強化防呆處理。"""
    text = (text or "").strip()
    
    # 清除 AI 助手常見的開場白與 Markdown 標題
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE) # 刪除 # 標題
    text = re.sub(r"\*\*|__", "", text) # 刪除 ** 或 __
    text = re.sub(r"###+\s+思考過程", "", text, flags=re.IGNORECASE) 
    text = re.sub(r"作為一個.*助手.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"身為.*AI.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"以下是.*思考過程.*", "", text, flags=re.IGNORECASE)
    text = text.strip()
    
    thinking, description = "", text
    
    # 1. 嘗試標準解析 (思考：... 描述：...)
    m_think = re.search(r"思考[：:]\s*(.*?)(?=描述[：:]|$)", text, re.DOTALL)
    if m_think:
        thinking = m_think.group(1).strip()
    
    m_desc = re.search(r"描述[：:]\s*(.*)", text, re.DOTALL)
    if m_desc:
        description = m_desc.group(1).strip()
    else:
        # 2. 防呆：若沒找到「描述：」，但有冒號分隔
        if "：" in text or ":" in text:
            parts = re.split(r"[：:]", text)
            if len(parts) > 1:
                # 排除標題，取最後一個有意義的部分
                potential_desc = parts[-1].strip()
                if len(potential_desc) > 0:
                    description = potential_desc
                    thinking = " ".join(parts[:-1]).strip()
        
        # 3. 終極防呆：若還是太長，取最後一句話
        if len(description) > 50:
            lines = [line.strip() for line in description.split('\n') if line.strip() and not any(tag in line for tag in ["思考", "理由", "決定"])]
            if lines:
                description = lines[-1]
                thinking = "\n".join(lines[:-1])
    
    # 再次清理描述
    description = re.sub(r"(思考|理由|決定)[：:].*", "", description, flags=re.DOTALL).strip()
    # 清理所有加粗與 Markdown 語法
    description = re.sub(r"\*\*|__", "", description).strip()
    # 取最後一行並清理多餘標點
    description = description.split('\n')[-1].strip().strip('。').strip('"').strip('「').strip('」')
    
    return thinking[:100], description[:50] # 限制存入 record 的長度


def _parse_thinking_vote(text, alive):
    """從模型回覆中解析 思考：... 投票：N，強化防呆處理。"""
    text = (text or "").strip()
    # 清理干擾文字
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"作為一個.*助手.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"最終決定[：:]", "", text, flags=re.IGNORECASE)
    
    thinking, vote = "", None
    
    # 解析思考部分
    m_think = re.search(r"思考[：:]\s*(.*?)(?=(投票|最終決定)[：:]|$)", text, re.DOTALL)
    if m_think:
        thinking = m_think.group(1).strip()
    
    # 解析投票對象：支援「投票：N」或「投票給玩家N」或直接出現數字
    m_vote = re.search(r"投票[：:]\s*(\d+)", text)
    if m_vote:
        v = int(m_vote.group(1))
        if v in alive:
            vote = v
    
    if vote is None:
        # 尋找「投票給玩家N」或「投票給 N」
        m_vote_alt = re.search(r"投票給\s*(?:玩家)?\s*(\d+)", text)
        if m_vote_alt:
            v = int(m_vote_alt.group(1))
            if v in alive:
                vote = v

    if vote is None:
        # 搜尋全文中最後一個出現的數字且在存活名單內
        nums = re.findall(r"\d+", text)
        for num in reversed(nums):
            v = int(num)
            if v in alive:
                vote = v
                break
                
    if vote is None:
        # 真的沒抓到，隨機投一個存活者
        vote = random.choice(alive)
        
    return thinking[:100], vote


def build_system_prompt(player_id: int, role: str, word: str, num_players: int, personality: str):
    if role == "白板":
        role_instruction = (
            "你是【白板】。你完全不知道詞彙是什麼！\n"
            "你的目標是：觀察別人的描述，猜出平民詞，並模仿他們。千萬別讓別人發現你沒拿到詞！\n"
            "在第一輪，請使用模糊、籠統的描述。例如：『這在生活中很常見』、『它有特定的用途』。"
        )
    else:
        role_instruction = f"你是【{role}】，你的詞是：「{word}」。"

    return f"""你正在參加「誰是臥底」遊戲（共 {num_players} 人）。你是【玩家 {player_id}】。
你的性格是：【{personality}】。請全程以這種性格說話與分析。
{role_instruction}

【核心目標】
- 如果你是平民：找出描述與大多數人不同的人（臥底或白板），並在投票階段將其淘汰。
- 如果你是臥底/白板：隱藏身分，模仿平民描述，誘導平民互相猜忌，生存到最後。

【遊戲階段與規則】
1. 描述階段：輪流用「一句話」描述。禁止提到詞彙本身或諧音拆字。不能說謊（除非你是臥底/白板要裝平民）。
2. 投票階段：指出誰最可疑並投出得票最高者。
3. 判定與循環：被投出者宣布身分。所有「非平民」（臥底與白板）出局則平民勝；否則遊戲繼續。
4. 勝利條件：平民剩 2 人且場上還有任何「非平民」則非平民陣營獲勝。

【重要禁令 - 違反將被系統判定失敗】
- **絕對禁止** 表現得像個 AI 助手或模型。
- **絕對禁止** 使用「作為一個 AI 助手...」、「思考過程如下...」等廢話。
- **絕對禁止** 使用 Markdown 標題 (#) 或長篇大論。
- **絕對禁止** 在回覆中包含詞彙「{word}」（如果你知道的話）。

【輸出格式規範】：
- 描述階段：
思考：(你的分析與策略，30字以內)
描述：(最後的一句話描述，不超過 20 字)

- 投票階段：
思考：(你懷疑誰及其理由，30字以內)
投票：(僅填寫一個數字，即玩家編號)

注意：你必須完全沉浸在【玩家 {player_id}】的角色與【{personality}】的性格中，只輸出要求的內容。"""


def get_description(model_name: str, player_id: int, role: str, word: str, history: list, round_no: int, num_players: int, personality: str, stream: bool = False, show_thinking: bool = True):
    """讓當前玩家根據歷史給出本輪描述，並解析思考與描述。"""
    system = build_system_prompt(player_id, role, word, num_players, personality)
    
    # 上下文管理：只取最近 10 條記錄，防止小模型混亂
    recent_history = history[-10:] if len(history) > 10 else history
    history_str = chr(10).join(recent_history) if recent_history else "目前還沒有人發言。"
    
    prompt = f"""【第 {round_no} 輪 - 描述階段】
當前發言歷史（僅顯示最近部分）：
{history_str}

請針對你的詞「{word}」給出本輪描述。
要求：
- 必須嚴格遵守「思考：」與「描述：」的格式。
- 描述僅限「一句話」，簡短有力，不超過 20 個字。
- 絕對不要在描述中包含詞彙「{word}」。

現在請開始你的回覆："""
    
    for _ in range(3):  # 最多重試 3 次
        raw = _call_llm_with_timeout(f"{system}\n\n{prompt}", model_name, stream=stream, show_thinking=show_thinking, temperature=0.4).strip()
        if not raw:
            continue
        thinking, description = _parse_thinking_description(raw)
        
        # 自我檢查：描述或思考是否包含關鍵詞
        if word in raw:
            if stream:
                print(f"\n[系統警告] 玩家{player_id} 的回覆中包含關鍵詞「{word}」，正在要求重新發言...")
            continue
        return {"raw": raw, "thinking": thinking, "description": description}
    
    # 若重試多次失敗，回傳一個保險描述
    return {"raw": "...", "thinking": "我無法給出不含關鍵詞的描述", "description": "這個東西很常見。"}


def get_vote(model_name: str, player_id: int, role: str, word: str, history: list, round_no: int, alive: list, num_players: int, personality: str, stream: bool = False, show_thinking: bool = True):
    """讓當前玩家根據描述投票，並解析思考與投票對象。"""
    system = build_system_prompt(player_id, role, word, num_players, personality)
    
    # 投票候選人排除自己
    candidates = [a for a in alive if a != player_id]
    names = "、".join([f"玩家{i}" for i in candidates])
    
    # 投票階段需要較完整歷史，但仍限制在 15 條以內
    recent_history = history[-15:] if len(history) > 15 else history
    history_str = chr(10).join(recent_history)
    
    prompt = f"""【第 {round_no} 輪 - 投票階段】
請分析本輪發言（僅顯示最近部分）：
{history_str}

目前存活的其他玩家：{names}。
請決定你要投票給誰（必須是上述編號之一）。
要求：
- 必須嚴格遵守「思考：」與「投票：」的格式。
- 「投票：」後面只能跟一個數字，例如：投票：3

現在請開始你的回覆："""
    raw = _call_llm_with_timeout(f"{system}\n\n{prompt}", model_name, stream=stream, show_thinking=show_thinking, temperature=0.7).strip()
    if not raw:
        return {"raw": "...", "thinking": "...", "vote": random.choice(candidates)}
    thinking, vote = _parse_thinking_vote(raw, candidates)
    return {"raw": raw, "thinking": thinking, "vote": vote}


def save_game_record(record: dict):
    """將遊戲記錄存為 Markdown 檔案。"""
    os.makedirs("game_logs", exist_ok=True)
    filename = f"game_logs/game_{record['id'][:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# 誰是臥底 遊戲記錄\n\n")
        f.write(f"- **時間**: {record['created_at']}\n")
        f.write(f"- **題組**: {record['group_name']}\n")
        f.write(f"- **勝利者**: {record['winner']}\n\n")
        
        f.write(f"## 玩家配置\n")
        for p in record['roles']:
            human_tag = " (人類)" if p['is_human'] else ""
            f.write(f"- 玩家{p['id']}: {p['role']} ({p['word']}){human_tag} - 性格: {p['personality']}\n")
        
        f.write(f"\n## 遊戲過程\n")
        for r in record['rounds']:
            f.write(f"### 第 {r['round']} 輪\n")
            f.write(f"#### 描述階段\n")
            for d in r['descriptions']:
                f.write(f"- **玩家{d['player_id']}**: {d['description']}\n")
                f.write(f"  - *思考*: {d['thinking']}\n")
            
            f.write(f"\n#### 投票階段\n")
            for v in r['votes']:
                f.write(f"- **玩家{v['player_id']}** 投給了 **玩家{v['vote_to']}**\n")
                f.write(f"  - *思考*: {v['thinking']}\n")
            
            f.write(f"\n**淘汰者**: 玩家{r['eliminated']}\n\n")
    
    return filename


# 全域計分板
SCOREBOARD = {}

def update_scoreboard(record: dict):
    """更新計分板。"""
    global SCOREBOARD
    winner_role = record['winner']
    for p in record['roles']:
        p_id = p['id']
        if p_id not in SCOREBOARD:
            SCOREBOARD[p_id] = {"win": 0, "loss": 0, "is_human": p['is_human']}
        
        if p['role'] == winner_role:
            SCOREBOARD[p_id]["win"] += 1
        else:
            SCOREBOARD[p_id]["loss"] += 1

def print_scoreboard():
    """顯示計分板。"""
    print("\n" + "="*20 + " 累計計分板 " + "="*20)
    print(f"{'玩家':<10} {'身分':<10} {'勝':<5} {'敗':<5} {'勝率':<10}")
    for p_id, stats in sorted(SCOREBOARD.items()):
        identity = "你" if stats['is_human'] else "AI"
        total = stats['win'] + stats['loss']
        win_rate = f"{(stats['win']/total)*100:.1f}%" if total > 0 else "0%"
        print(f"玩家{p_id:<8} {identity:<10} {stats['win']:<5} {stats['loss']:<5} {win_rate:<10}")
    print("="*52)


def spy_counter_kill(model_name: str, player_id: int, word: str, history: list, civilian_word: str, stream: bool = False):
    """臥底被投出後的反殺機會：猜測平民詞。"""
    prompt = f"""你是【玩家 {player_id}】，你的身分是【臥底】，你的詞是：「{word}」。
你現在被投出局了，但你還有最後一次「反殺」的機會！

根據以下遊戲記錄，請猜測平民手中的詞是什麼：
{chr(10).join(history)}

請直接輸出你猜測的一個詞（例如：水餃），不要有任何廢話或解釋。
如果你猜對了，臥底將反敗為勝！"""
    
    # 這裡不顯示思考，直接讓臥底猜詞
    guess = _call_llm_with_timeout(prompt, model_name, stream=stream, show_thinking=False).strip()
    # 清理標點與加粗
    guess = re.sub(r"\*\*|__|[。！？?]", "", guess).strip()
    
    is_correct = guess == civilian_word
    return guess, is_correct


def run_game(
    word_group_choice="隨機",
    num_players=6,
    num_undercover=1,
    num_whites=1,
    model_name="qwen3:4b",
    stream=False,
    show_spoilers=True,
    show_thinking=True,
    human_id=None,
):
    """
    跑一局誰是臥底，返回完整記錄（含每輪描述與投票的思考、對話）供網頁顯示。
    model_name: Ollama 用「名稱:tag」如 qwen3:4b；否則為 Gemini 模型名。
    """
    if num_undercover + num_whites >= num_players or (num_undercover + num_whites) < 1:
        # 確保至少有一個非平民，且平民人數足夠
        num_undercover = 1
        num_whites = 0
        
    group_name, word_civilian, word_undercover, player_data = assign_roles(
        num_players=num_players, num_undercover=num_undercover, num_whites=num_whites, group_choice=word_group_choice, human_id=human_id
    )

    if stream:
        print(f"【遊戲開始】題組：{group_name}")
        print(f"玩家總數：{num_players} | 臥底人數：{num_undercover} | 白板人數：{num_whites}")
        if show_spoilers:
            print(f"平民詞：{word_civilian} | 臥底詞：{word_undercover}")
            print("玩家身分：")
            for p in player_data:
                human_tag = " (你)" if p['is_human'] else ""
                print(f"  玩家{p['id']}: {p['role']} ({p['word']}){human_tag} - 性格：{p['personality']}")
        elif human_id is not None:
            # 如果不劇透但有玩家，只顯示玩家自己的詞
            for p in player_data:
                if p['is_human']:
                    if p['role'] == "白板":
                        print(f"\n>>> [你是玩家 {p['id']}] 你是白板！你沒有詞，請觀察別人發言。")
                    else:
                        print(f"\n>>> [你是玩家 {p['id']}] 你的詞是: {p['word']}")
                    break
        print("-" * 30)

    # 建立方便查詢的字典
    player_info = {p['id']: p for p in player_data}
    alive = [p['id'] for p in player_data]
    history_lines = []
    record = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(),
        "config": {
            "word_group": word_group_choice,
            "num_players": num_players,
            "num_undercover": num_undercover,
            "num_whites": num_whites,
            "model_name": model_name,
        },
        "group_name": group_name,
        "word_civilian": word_civilian,
        "word_undercover": word_undercover,
        "roles": player_data,
        "rounds": [],
        "winner": None,
    }

    round_no = 0
    start_player_idx = 0 # 每輪更換首位發言者
    
    while True:
        round_no += 1
        round_data = {"round": round_no, "descriptions": [], "votes": [], "eliminated": None, "alive_after": []}

        if stream:
            print(f"\n=== 第 {round_no} 輪 - 描述階段 ===")

        # 根據 start_player_idx 調整發言順序
        # 找出當前存活玩家中，最接近 start_player_idx 的人開始
        current_order = []
        for i in range(num_players):
            p = (start_player_idx + i) % num_players
            if p in alive:
                current_order.append(p)

        for pid in current_order:
            p = player_info[pid]
            if p['is_human']:
                if p['role'] == "白板":
                    print(f"\n[玩家{pid}] (你) 你是白板！請觀察別人描述。")
                else:
                    print(f"\n[玩家{pid}] (你) 的詞是: {p['word']}")
                desc = input("請輸入你的描述: ").strip()
                out = {"description": desc, "thinking": "人類玩家", "raw": desc}
            else:
                if stream:
                    display_role = f" ({p['role']})" if show_spoilers else ""
                    print(f"\n[玩家{pid}]{display_role} ({p['personality']}) 思考與描述：")
                    import time
                    time.sleep(0.5)
                out = get_description(model_name, pid, p['role'], p['word'], history_lines, round_no, num_players, p['personality'], stream=stream, show_thinking=show_thinking)
            
            line = f"玩家{pid}：{out['description']}"
            history_lines.append(line)
            round_data["descriptions"].append({
                "player_id": pid,
                "description": out["description"],
                "thinking": out["thinking"],
                "raw": out["raw"],
            })

        if stream:
            print(f"\n=== 第 {round_no} 輪 - 投票階段 ===")

        for pid in alive:
            p = player_info[pid]
            if p['is_human']:
                others = [a for a in alive if a != pid]
                print(f"\n[玩家{pid}] (你) 請投票。除自己外的存活玩家: {others}")
                while True:
                    try:
                        v_input = input("請輸入你要投的玩家編號: ").strip()
                        v_id = int(v_input)
                        if v_id in others:
                            out = {"vote": v_id, "thinking": "人類投票", "raw": v_input}
                            break
                        elif v_id == pid:
                            print(f"你不能投給自己！請從其他玩家 {others} 中選擇。")
                        else:
                            print(f"玩家 {v_id} 不在存活名單中，請重新輸入。")
                    except ValueError:
                        print("請輸入有效的數字編號。")
            else:
                if stream:
                    display_role = f" ({p['role']})" if show_spoilers else ""
                    print(f"\n[玩家{pid}]{display_role} ({p['personality']}) 思考與投票：")
                    import time
                    time.sleep(0.5)
                out = get_vote(model_name, pid, p['role'], p['word'], history_lines, round_no, alive, num_players, p['personality'], stream=stream, show_thinking=show_thinking)
            
            round_data["votes"].append({
                "player_id": pid,
                "vote_to": out["vote"],
                "thinking": out["thinking"],
                "raw": out["raw"],
            })

        votes_count = {}
        for v in round_data["votes"]:
            p = v["vote_to"]
            votes_count[p] = votes_count.get(p, 0) + 1
        
        if stream:
            print("\n【投票統計】")
            for p, c in votes_count.items():
                print(f"玩家{p}: {c} 票")

        max_votes = max(votes_count.values())
        tied = [target for target, count in votes_count.items() if count == max_votes]
        eliminated = tied[0] if len(tied) == 1 else random.choice(tied)
        round_data["eliminated"] = eliminated
        alive = [target for target in alive if target != eliminated]
        round_data["alive_after"] = list(alive)
        
        start_player_idx = (eliminated + 1) % num_players
        
        role_info = f"（身分是：{player_info[eliminated]['role']}）" if show_spoilers or player_info[eliminated]['is_human'] else ""
        result_msg = f"【投票結果】玩家{eliminated} 被淘汰{role_info}。"
        history_lines.append(result_msg)
        if stream:
            print(f"\n{result_msg}")
            print("-" * 30)

        record["rounds"].append(round_data)

        # 判定是否還有非平民在場
        non_civilians_alive = [p_id for p_id in alive if player_info[p_id]['role'] in ["臥底", "白板"]]
        
        if player_info[eliminated]['role'] == "臥底":
            if stream:
                print(f"\n🎭 玩家{eliminated} 是臥底！觸發「反殺」機制...")
            
            if player_info[eliminated]['is_human']:
                print(f"\n>>> [你是臥底] 你還有最後一次機會！")
                guess = input(f"請猜測平民詞是什麼: ").strip()
                is_correct = (guess == word_civilian)
            else:
                guess, is_correct = spy_counter_kill(model_name, eliminated, player_info[eliminated]['word'], history_lines, word_civilian, stream=stream)
            
            if stream:
                print(f"臥底猜測平民詞為：{guess}")
            
            if is_correct:
                record["winner"] = "臥底"
                if stream:
                    print(f"🎯 猜對了！平民詞正是「{word_civilian}」。臥底反殺成功，臥底獲勝！")
                break
            else:
                if stream:
                    print(f"❌ 猜錯了！平民詞是「{word_civilian}」。")
                # 若還有其他非平民，遊戲繼續；否則平民勝
                if not non_civilians_alive:
                    record["winner"] = "平民"
                    if stream: print("🎉 所有臥底與白板均已出局，平民獲勝！")
                    break
        
        elif player_info[eliminated]['role'] == "白板":
            if not non_civilians_alive:
                record["winner"] = "平民"
                if stream: print("🎉 所有臥底與白板均已出局，平民獲勝！")
                break
        
        # 檢查平民人數是否低於門檻
        civilians_alive = [p_id for p_id in alive if player_info[p_id]['role'] == "平民"]
        if len(civilians_alive) <= 2 and non_civilians_alive:
            record["winner"] = "非平民陣營" # 包含臥底與白板
            if stream:
                print("\n😈 平民人數不足，非平民陣營（臥底與白板）獲勝！")
            break

    return record


if __name__ == "__main__":
    # 強制 stdout 使用 UTF-8 (修正 Windows 可能的編碼問題)
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    group_choice = os.environ.get("WORD_GROUP", "隨機")
    num_players = int(os.environ.get("NUM_PLAYERS", "6"))
    num_undercover = int(os.environ.get("NUM_UNDERCOVER", "1"))
    num_whites = int(os.environ.get("NUM_WHITES", "1"))
    model_name = os.environ.get("MODEL_NAME", "qwen3:4b")
    if len(sys.argv) > 1:
        group_choice = sys.argv[1]
    
    clear_screen()
    print("=== 誰是臥底 遊戲設定 ===")
    
    # 是否親自玩
    user_play = input("你想親自下去玩嗎？(y/N): ").lower() == 'y'
    human_id = random.randint(0, num_players - 1) if user_play else None
    
    # 劇透設定
    if user_play:
        show_spoilers = False # 親自玩預設不劇透
        print(f"因為你要親自參與，劇透功能已自動關閉。你的玩家編號將是隨機分配的。")
    else:
        spoil_input = input("是否要顯示劇透（顯示所有玩家身分與詞彙）？[Y/n]: ").strip().lower()
        show_spoilers = spoil_input != 'n'
    
    # 提示（思考）設定
    print("\n提示：開啟「顯示思考過程」可以即時看到模型運作，體驗較流暢。")
    print("若關閉，則需等待模型思考完畢後才會一次顯示描述，可能會感覺卡頓。")
    think_input = input("是否要顯示玩家思考過程？[Y/n]: ").strip().lower()
    show_thinking = think_input != 'n'
    
    print(f"\n遊戲設定完成！(角色: {'人類+AI' if user_play else '全AI'}, 提示: {'開啟' if show_thinking else '關閉'})")
    print("按下 Ctrl+C 可隨時結束遊戲。\n")

    try:
        game_count = 0
        while True:
            game_count += 1
            clear_screen()
            print(f"\n{'='*20} 第 {game_count} 場遊戲 開始 {'='*20}\n")
            
            record = run_game(
                word_group_choice=group_choice, 
                num_players=num_players, 
                num_undercover=num_undercover,
                num_whites=num_whites,
                model_name=model_name,
                stream=True,
                show_spoilers=show_spoilers,
                show_thinking=show_thinking,
                human_id=human_id
            )
            
            # 更新與顯示計分板
            update_scoreboard(record)
            print_scoreboard()
            
            # 存檔遊戲記錄
            filename = save_game_record(record)
            print(f"\n[系統提示] 遊戲記錄已存檔至: {filename}")
            
            print("\n" + "="*30)
            print(f"第 {game_count} 場遊戲結束")
            print("Game ID:", record["id"])
            print("Winner:", record["winner"])
            print("="*30)
            
            print("\n即將開始下一場遊戲...")
            import time
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n偵測到 Ctrl+C，遊戲已停止。感謝遊玩！")
        sys.exit(0)
