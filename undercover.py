#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
谁是卧底 - N 人局，可选题组、人数、卧底数。
支援 Ollama（如 qwen3:4b）與 Groq（如 llama-3.3-70b-versatile）。
後端選擇由使用者手動指定。
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

# ─────────────────────────────────────────────
# Groq API Key 轮换池（最多支持 10 个）
# .env 格式：GROQ_API_KEY、GROQ_API_KEY2 ... GROQ_API_KEY10
# ─────────────────────────────────────────────

def _load_groq_key_pool() -> list:
    """从环境变量读取所有 Groq API Key，返回非空列表。"""
    keys = []
    # 第一个 key 名称为 GROQ_API_KEY（不带数字）
    for suffix in [""] + [str(i) for i in range(2, 11)]:
        k = os.environ.get(f"GROQ_API_KEY{suffix}", "").strip()
        if k:
            keys.append(k)
    return keys

# 全局 key 池状态
_GROQ_KEY_POOL: list = []
_GROQ_KEY_INDEX: int  = 0   # 当前使用的 key 索引

def _init_groq_key_pool():
    """初始化 key 池（启动时和 select_backend 时调用）。"""
    global _GROQ_KEY_POOL, _GROQ_KEY_INDEX
    _GROQ_KEY_POOL  = _load_groq_key_pool()
    _GROQ_KEY_INDEX = 0
    if _GROQ_KEY_POOL:
        print(f"[Key 池] 已加载 {len(_GROQ_KEY_POOL)} 个 Groq API Key，轮流使用。")
    return _GROQ_KEY_POOL

def _get_next_groq_key() -> str:
    """Round-robin 取下一个 Groq API Key。"""
    global _GROQ_KEY_INDEX
    if not _GROQ_KEY_POOL:
        return os.environ.get("GROQ_API_KEY", "")
    key = _GROQ_KEY_POOL[_GROQ_KEY_INDEX % len(_GROQ_KEY_POOL)]
    _GROQ_KEY_INDEX += 1
    return key

def _rotate_groq_key():
    """遇到限流时强制跳到下一个 key（已由 _get_next_groq_key 自动轮换，此函数留作日志用）。"""
    idx = _GROQ_KEY_INDEX % len(_GROQ_KEY_POOL) if _GROQ_KEY_POOL else 0
    print(f"[Key 池] 切换到 Key #{idx + 1}/{len(_GROQ_KEY_POOL)}")

# ─────────────────────────────────────────────
# 後端選擇（手動）
# ─────────────────────────────────────────────

BACKEND_OLLAMA = "ollama"
BACKEND_GROQ   = "groq"

# ─────────────────────────────────────────────
# 終端機顏色
# ─────────────────────────────────────────────
ANSI_BLUE  = "\033[94m"
ANSI_RESET = "\033[0m"

def _stream_print(content: str, in_think: list, show_thinking: bool = True):
    """
    逐 chunk 輸出，<think>...</think> 區塊：
    - show_thinking=True：以藍色顯示
    - show_thinking=False：完全略過不印
    in_think 是單元素 list，用來跨 chunk 共享狀態。
    """
    buf = content
    while buf:
        if in_think[0]:
            end = buf.find("</think>")
            if end == -1:
                # 还在 think 区块内
                if show_thinking:
                    print(f"{ANSI_BLUE}{buf}{ANSI_RESET}", end="", flush=True)
                buf = ""
            else:
                if show_thinking:
                    print(f"{ANSI_BLUE}{buf[:end]}</think>{ANSI_RESET}", end="", flush=True)
                in_think[0] = False
                buf = buf[end + len("</think>"):]
        else:
            start = buf.find("<think>")
            if start == -1:
                print(buf, end="", flush=True)
                buf = ""
            else:
                print(buf[:start], end="", flush=True)
                if show_thinking:
                    print(f"{ANSI_BLUE}<think>", end="", flush=True)
                in_think[0] = True
                buf = buf[start + len("<think>"):]


def select_backend():
    """互動式選擇後端（Ollama 或 Groq），回傳 (backend, model_name)。"""
    print("\n請選擇 LLM 后端：")
    print("  1. Ollama（本地模型，如 qwen3:4b、qwen2.5:1.5b）")
    print("  2. Groq（云端加速，如 qwen/qwen3-32b）[默认]")
    
    while True:
        choice = input("请输入 1 或 2（直接 Enter 使用默认 ollama）: ").strip()
        if choice == "2":
            backend = BACKEND_GROQ
            default_model = os.environ.get("GROQ_MODEL", "qwen/qwen3-32b")
            print(f"\nGroq 常用模型：qwen/qwen3-32b、llama-3.3-70b-versatile、llama-3.1-8b-instant")
            model = input(f"请输入 Groq 模型名称（直接 Enter 使用默认 {default_model}）: ").strip()
            if not model:
                model = default_model
            # 初始化 key 池（从 .env 读取所有 GROQ_API_KEY / GROQ_API_KEY2 ... GROQ_API_KEY10）
            pool = _init_groq_key_pool()
            if not pool:
                # 池里没有，交互式要求输入至少一个
                api_key = input("请输入 GROQ_API_KEY（或在 .env 中设置）: ").strip()
                if api_key:
                    os.environ["GROQ_API_KEY"] = api_key
                    _init_groq_key_pool()
                else:
                    print("[警告] 未提供 GROQ_API_KEY，调用可能失败。")
            return backend, model
        elif choice == "" or choice == "1":
            backend = BACKEND_OLLAMA
            default_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:32b")
            print(f"\nOllama 常用模型：qwen3:4b、qwen2.5:1.5b、llama3.2:3b、qwen2.5:32b （需要 Ollama 0.5.0+）")
            model = input(f"请输入 Ollama 模型名称（直接 Enter 使用默认 {default_model}）: ").strip()
            if not model:
                model = default_model
            return backend, model
        else:
            print("無效輸入，請輸入 1 或 2。")


# ─────────────────────────────────────────────
# LLM 呼叫
# ─────────────────────────────────────────────

# 每次 API 调用前的基础延时（秒），避免触发免费额度限制
API_CALL_DELAY = 2.0
# 遇到错误时的重试等待时间（秒）和最大重试次数
RETRY_WAIT    = 300   # 5 分钟
MAX_RETRIES   = 20


def _call_llm_with_timeout(prompt: str, model_name: str, backend: str,
                            stream: bool = False, show_thinking: bool = True,
                            timeout: int = 300, temperature: float = 0.7) -> str:
    """带延时、超时与自动重试的 LLM 调用包装器。"""
    for attempt in range(1, MAX_RETRIES + 1):
        # 每次调用前等待，避免超过免费 API 限制
        if API_CALL_DELAY > 0:
            time.sleep(API_CALL_DELAY)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_llm, prompt, model_name, backend, stream, show_thinking, temperature)
            try:
                result = future.result(timeout=timeout)
                if result:          # 正常拿到回复，直接返回
                    return result
                # 空回复也视为失败，进入重试
                raise ValueError("模型返回空内容")
            except TimeoutError:
                msg = f"模型回应超过 {timeout} 秒未完成"
            except Exception as e:
                msg = str(e)

        # ── 判断是否是限流错误 ──
        is_rate_limit = any(kw in msg.lower() for kw in [
            "rate limit", "429", "too many requests",
            "quota", "exceeded", "rate_limit"
        ])

        if attempt >= MAX_RETRIES:
            print(f"\n[系统错误] 已重试 {MAX_RETRIES} 次，全部失败，放弃本次调用。")
            break

        pool_size = len(_GROQ_KEY_POOL)

        if is_rate_limit and pool_size > 1:
            # 有多个 key：直接切换，不等待（key 池会自动轮换到下一个）
            next_idx = _GROQ_KEY_INDEX % pool_size
            print(f"\n[Key 池] 限流，立即切换到 Key #{next_idx + 1}/{pool_size}，继续重试...")
        elif is_rate_limit and pool_size <= 1:
            # 只有一个 key，或 key 轮转一圈后都限流：等 5 分钟
            # 每转完一圈（attempt 是 pool_size 的倍数）才等待
            if pool_size == 0 or attempt % max(pool_size, 1) == 0:
                print(f"\n[系统警告] 第 {attempt}/{MAX_RETRIES} 次失败：{msg}")
                print(f"           所有 Key 均限流，等待 5 分钟后继续...")
                for remaining in range(300, 0, -10):
                    print(f"\r           剩余等待：{remaining} 秒...   ", end="", flush=True)
                    time.sleep(min(10, remaining))
                print(f"\r           重试中...                      ", flush=True)
            else:
                print(f"\n[Key 池] 限流，立即切换 Key 重试...")
        else:
            # 非限流错误（网络、超时等）：短暂等待后重试
            wait_sec = min(15 * attempt, 120)
            print(f"\n[系统警告] 第 {attempt}/{MAX_RETRIES} 次失败：{msg}")
            print(f"           等待 {wait_sec} 秒后重试...")
            time.sleep(wait_sec)

    return ""


def _call_llm_ollama(prompt: str, model_name: str, stream: bool, show_thinking: bool, temperature: float) -> str:
    """呼叫 Ollama。"""
    import ollama
    options = {"temperature": temperature, "top_p": 0.9}
    try:
        if stream:
            full_content = ""
            in_think = [False]   # 跨 chunk 追蹤是否在 <think> 區塊內
            for chunk in ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                options=options
            ):
                content = (chunk.get("message") or {}).get("content") or ""
                if content:
                    full_content += content
                    _stream_print(content, in_think, show_thinking)
                    if len(full_content) > 2000:
                        print("\n[系统强制截断过长回复...]")
                        break
            print()
            return full_content
        r = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options=options
        )
        return (r.get("message") or {}).get("content") or ""
    except Exception as e:
        print(f"\n[系统提示] Ollama 服务响应异常 ({e})，准备重试...")
        time.sleep(2)
        return ""


def _call_llm_groq(prompt: str, model_name: str, stream: bool, show_thinking: bool, temperature: float) -> str:
    """呼叫 Groq API，自动从 key 池轮换取用。"""
    try:
        from groq import Groq
    except ImportError:
        print("\n[系统错误] 未安装 groq 套件，请执行：pip install groq")
        return ""

    api_key = _get_next_groq_key()
    if not api_key:
        print("\n[系统错误] 未设置任何 GROQ_API_KEY 环境变量。")
        return ""

    client = Groq(api_key=api_key)
    key_label = f"Key #{_GROQ_KEY_INDEX % len(_GROQ_KEY_POOL) if _GROQ_KEY_POOL else 1}"

    try:
        if stream:
            full_content = ""
            in_think = [False]
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=4096,
                stream=True,
            )
            for chunk in completion:
                content = (chunk.choices[0].delta.content or "") if chunk.choices else ""
                if content:
                    full_content += content
                    _stream_print(content, in_think, show_thinking)
                    if len(full_content) > 8000:
                        print("\n[系统强制截断过长回复...]")
                        break
            print()
            return full_content
        else:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=4096,
            )
            return completion.choices[0].message.content or ""
    except Exception as e:
        err = str(e)
        # 限流时打印当前使用的 key 编号，便于排查
        if any(kw in err.lower() for kw in ["rate limit", "429", "quota", "exceeded"]):
            print(f"\n[Key 池] {key_label} 触发限流，下次调用将切换到下一个 Key。")
        raise   # 抛给上层 _call_llm_with_timeout 统一处理重试


def _call_llm(prompt: str, model_name: str, backend: str,
              stream: bool = False, show_thinking: bool = True,
              temperature: float = 0.7) -> str:
    """依 backend 呼叫對應的 LLM。"""
    if backend == BACKEND_GROQ:
        return _call_llm_groq(prompt, model_name, stream, show_thinking, temperature)
    elif backend == BACKEND_OLLAMA:
        return _call_llm_ollama(prompt, model_name, stream, show_thinking, temperature)
    else:
        print(f"\n[系统错误] 未知后端：{backend}")
        return ""


# ─────────────────────────────────────────────
# 題庫
# ─────────────────────────────────────────────

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
        ("水餃", "鍋貼"), ("牛奶", "豆漿"), ("泡麵", "麵條"),
        ("西瓜", "哈密瓜"), ("腳踏車", "摩托車"), ("醫生", "護士"), ("手機", "電話"),
    ],
    "進階混淆組": [
        ("燒肉", "火鍋"), ("鬧鐘", "生理時鐘"), ("麵包", "蛋糕"),
        ("唇膏", "護唇膏"), ("洗髮精", "沐浴乳"), ("蝴蝶", "飛蛾"), ("眼藥水", "隱形眼鏡液"),
    ],
    "高難度腦力組": [
        ("媽媽", "飼育員"), ("勇氣", "毅力"), ("暗戀", "單戀"),
        ("初戀", "舊愛"), ("保險箱", "存錢筒"), ("散步", "逛街"), ("英雄", "豪傑"),
    ],
    "趣味情境組": [
        ("元宵", "湯圓"), ("小籠包", "燒賣"), ("婚紗", "禮服"),
        ("導遊", "領隊"), ("教授", "老師"), ("雨傘", "雨衣"),
    ],
}

GROUP_OPTIONS = ["隨機"] + list(WORD_GROUPS.keys())
ALL_PAIRS = [
    (group_name, pair) for group_name, pairs in WORD_GROUPS.items() for pair in pairs
]

USED_PAIRS = []

PERSONALITIES = ["冷靜分析型", "熱情活潑型", "疑心病重型", "簡短省話型", "風向帶領者"]


def pick_word_pair(group_choice=None):
    global USED_PAIRS
    if group_choice and group_choice != "隨機" and group_choice in WORD_GROUPS:
        pool = [(group_choice, p) for p in WORD_GROUPS[group_choice]]
    else:
        pool = ALL_PAIRS
    available = [p for p in pool if p not in USED_PAIRS]
    if not available:
        print("\n[系统提示] 题库已全部玩过一遍，重新洗牌中...")
        USED_PAIRS = []
        available = pool
    choice = random.choice(available)
    USED_PAIRS.append(choice)
    return choice


def assign_roles(num_players=6, num_undercover=1, num_whites=1, group_choice=None, human_id=None):
    group_name, (word_civilian, word_undercover) = pick_word_pair(group_choice)
    num_whites = max(0, num_whites)
    num_undercover = max(0, num_undercover)
    num_civilians = max(1, num_players - num_undercover - num_whites)

    # 先建立角色池（不含白板），隨機排列
    roles = []
    for _ in range(num_civilians):
        roles.append(("平民", word_civilian))
    for _ in range(num_undercover):
        roles.append(("卧底", word_undercover))
    random.shuffle(roles)

    # 白板一定插在後 1/3 的位置（玩家編號靠後）
    white_roles = [("白板", "???") for _ in range(num_whites)]
    # 後 1/3 的起始 index（至少從一半之後開始）
    late_start = max(num_players // 2, num_players - num_whites * 2)
    # 從 late_start 到末尾隨機挑位置插入白板
    insert_positions = sorted(random.sample(range(late_start, num_players), min(num_whites, num_players - late_start)))
    # 把非白板角色先放好，再把白板插入指定位置
    final_roles = list(roles)  # 長度為 num_civilians + num_undercover
    for pos, wr in zip(insert_positions, white_roles):
        final_roles.insert(pos, wr)
    # 若超出 num_players 就截尾（保險用）
    final_roles = final_roles[:num_players]

    player_data = []
    for i, r in enumerate(final_roles):
        p_type = random.choice(PERSONALITIES)
        is_human = (i == human_id)
        player_data.append({
            "id": i, "role": r[0], "word": r[1],
            "personality": p_type, "is_human": is_human
        })
    return group_name, word_civilian, word_undercover, player_data


# ─────────────────────────────────────────────
# Prompt 與解析
# ─────────────────────────────────────────────

def _parse_thinking_description(text):
    text = (text or "").strip()
    # 先去除 <think> 區塊（保留內容給 thinking 解析）
    think_content = ""
    m_think_block = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    if m_think_block:
        think_content = m_think_block.group(1).strip()
    # 去除整個 <think> 區塊，只留模型的正式輸出
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"作為一個.*助手.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"身為.*AI.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"以下是.*思考過程.*", "", text, flags=re.IGNORECASE)
    # 截斷：描述階段不應出現「投票：」，若有則截掉後面的部分
    text = re.sub(r"投票[：:].*", "", text, flags=re.DOTALL).strip()
    text = text.strip()
    thinking, description = think_content, text
    m_think = re.search(r"思考[：:]\s*(.*?)(?=描述[：:]|$)", text, re.DOTALL)
    if m_think:
        thinking = m_think.group(1).strip() or think_content
    m_desc = re.search(r"描述[：:]\s*(.*)", text, re.DOTALL)
    if m_desc:
        description = m_desc.group(1).strip()
    else:
        if "：" in text or ":" in text:
            parts = re.split(r"[：:]", text)
            if len(parts) > 1:
                potential_desc = parts[-1].strip()
                if len(potential_desc) > 0:
                    description = potential_desc
                    thinking = thinking or " ".join(parts[:-1]).strip()
        if len(description) > 50:
            lines = [line.strip() for line in description.split('\n') if line.strip() and not any(tag in line for tag in ["思考", "理由", "決定"])]
            if lines:
                description = lines[-1]
                thinking = thinking or "\n".join(lines[:-1])
    description = re.sub(r"(思考|理由|決定|投票)[：:].*", "", description, flags=re.DOTALL).strip()
    description = re.sub(r"\*\*|__", "", description).strip()
    description = description.split('\n')[-1].strip().strip('。').strip('"').strip('「').strip('」')
    return thinking[:100], description[:50]


def _parse_thinking_vote(text, alive):
    text = (text or "").strip()
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"作為一個.*助手.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"最終決定[：:]", "", text, flags=re.IGNORECASE)
    thinking, vote = "", None
    m_think = re.search(r"思考[：:]\s*(.*?)(?=(投票|最終決定)[：:]|$)", text, re.DOTALL)
    if m_think:
        thinking = m_think.group(1).strip()
    m_vote = re.search(r"投票[：:]\s*(\d+)", text)
    if m_vote:
        v = int(m_vote.group(1))
        if v in alive:
            vote = v
    if vote is None:
        m_vote_alt = re.search(r"投票給\s*(?:玩家)?\s*(\d+)", text)
        if m_vote_alt:
            v = int(m_vote_alt.group(1))
            if v in alive:
                vote = v
    if vote is None:
        nums = re.findall(r"\d+", text)
        for num in reversed(nums):
            v = int(num)
            if v in alive:
                vote = v
                break
    if vote is None:
        vote = random.choice(alive)
    return thinking[:100], vote


def build_system_prompt(player_id, role, word, num_players, personality, round_no=1, show_thinking=True, phase="describe"):
    if role == "白板":
        if round_no == 1:
            observe_tip = (
                "第一轮你还没有足够信息。策略：给出极度情绪化、模糊的描述，"
                "例如「让人心跳加速的感觉」、「充满力量的存在」。"
                "绝对不要说「这在生活中很常见」、「很普通」这种废话！"
            )
        else:
            observe_tip = (
                f"你已观察了 {round_no - 1} 轮。策略：分析大多数平民的描述方向，"
                "完全模仿他们的语气和关键词，让自己听起来和平民一模一样。"
            )
        role_instruction = (
            "你是【白板】。你完全不知道词汇是什么！\n"
            "【生存第一原则】你的唯一目标是活到最后，绝对不能被发现！\n"
            "- 描述时：模仿大多数人，不要「与众不同」，要「融入」。\n"
            "- 讨论时：附和多数人的判断，把怀疑引向其他人。\n"
            "- 投票时：跟着多数人投，不要独行。\n"
            f"{observe_tip}"
        )
    elif role == "卧底":
        role_instruction = (
            f"你是【卧底】，你的词是：「{word}」。\n"
            "【生存第一原则】你的目标是活到最后，绝对不能暴露自己是卧底！\n"
            "- 你的词与平民词相似但不同，描述时要找两者的共同点，让自己听起来像平民。\n"
            "- 不要描述你的词独有的特征，要描述平民词「也适用」的特征。\n"
            "- 讨论时：主动怀疑别人，把注意力从自己身上引开。\n"
            "- 如果有人怀疑你，立刻反怀疑那个人，说他的描述才奇怪。"
        )
    else:
        role_instruction = f"你是【平民】，你的词是：「{word}」。"

    if show_thinking:
        format_spec = f"""【输出格式规范】：
- 描述阶段：
思考：(策略分析，30字以内)
描述：(一句话，不超过 20 字)

- 讨论阶段：
思考：(分析谁可疑，30字以内)
发言：(一句话表态，不超过 30 字)

- 投票阶段：
思考：(最终判断，30字以内)
投票：(仅填写一个数字)"""
    else:
        format_spec = f"""【输出格式规范】：
- 描述阶段：只输出「描述：XXX」一行
- 讨论阶段：只输出「发言：XXX」一行
- 投票阶段：只输出「投票：N」一行
绝对不要输出「思考：」这一行。"""

    return f"""你正在参加「谁是卧底」游戏（共 {num_players} 人）。你是【玩家 {player_id}】。
你的性格是：【{personality}】。请全程以这种性格说话与分析。
{role_instruction}

【游戏阶段】
1. 描述阶段：每人用一句话描述自己的词（禁止直接说出词汇或谐音拆字）。
2. 讨论阶段：所有人轮流发言两轮，讨论谁最可疑，允许互相质疑和反驳。
3. 投票阶段：每人投票一次，得票最多者出局。
4. 胜利条件：所有卧底/白板出局则平民胜；平民剩 2 人而场上仍有卧底/白板则非平民胜。

【绝对禁令】
- 禁止提到自己的词汇「{word if role != "白板" else "（你没有词）"}」或谐音拆字。
- 禁止表现得像 AI 助手，禁止废话开场白，禁止 Markdown 格式。
- 禁止只输出分析而不给出实际描述/发言/投票。

{format_spec}

**请全程使用简体中文。完全沉浸在【玩家 {player_id}】与【{personality}】的角色中。**"""


def get_description(model_name, backend, player_id, role, word, history, round_no, num_players, personality, stream=False, show_thinking=True):
    system = build_system_prompt(player_id, role, word, num_players, personality, round_no=round_no, show_thinking=show_thinking)
    recent_history = history[-10:] if len(history) > 10 else history
    history_str = chr(10).join(recent_history) if recent_history else "目前还没有人发言。"
    if show_thinking:
        fmt_reminder = "必须严格遵守「思考：」与「描述：」的格式。"
    else:
        fmt_reminder = "只输出「描述：XXX」一行，不要有思考或其他文字。"
    prompt = f"""【第 {round_no} 轮 - 描述阶段】
当前发言历史（仅显示最近部分）：
{history_str}

请针对你的词「{word}」给出本轮描述。
要求：
- {fmt_reminder}
- 描述仅限「一句话」，简短有力，不超过 20 个字。
- 绝对不要在描述中包含词汇「{word}」。

现在请开始你的回复："""
    for _ in range(3):
        # show_thinking=False 時不用 streaming，避免重複印出
        actual_stream = stream and show_thinking
        raw = _call_llm_with_timeout(
            f"{system}\n\n{prompt}", model_name, backend,
            stream=actual_stream, show_thinking=show_thinking, temperature=0.4
        ).strip()
        if not raw:
            continue
        thinking, description = _parse_thinking_description(raw)
        # 只檢查 <think> 區塊外的文字是否包含關鍵詞
        raw_no_think = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        if word in raw_no_think:
            if stream:
                print(f"\n[系统警告] 玩家{player_id} 的描述中包含关键词「{word}」，正在要求重新发言...")
            continue
        # show_thinking=False 時，非 streaming，印出最终描述
        if stream and not show_thinking:
            print(f"描述：{description}")
        return {"raw": raw, "thinking": thinking, "description": description}
    return {"raw": "...", "thinking": "无法给出不含关键词的描述", "description": "这很常见。"}


def get_vote(model_name, backend, player_id, role, word, history, round_no, alive, num_players, personality, stream=False, show_thinking=True):
    system = build_system_prompt(player_id, role, word, num_players, personality, round_no=round_no, show_thinking=show_thinking)
    candidates = [a for a in alive if a != player_id]
    names = "、".join([f"玩家{i}" for i in candidates])
    recent_history = history[-15:] if len(history) > 15 else history
    history_str = chr(10).join(recent_history)
    if show_thinking:
        fmt_reminder = "必須嚴格遵守「思考：」與「投票：」的格式。\n- 「投票：」後面只能跟一個數字，例如：投票：3"
    else:
        fmt_reminder = "只输出「投票：N」一行（N 为玩家编号数字），不要有思考或其他文字。"
    prompt = f"""【第 {round_no} 轮 - 投票阶段】
请分析本轮发言（仅显示最近部分）：
{history_str}

目前存活的其他玩家：{names}。
请决定你要投票给谁（必须是上述编号之一）。
要求：
- {fmt_reminder}

现在请开始你的回复："""
    actual_stream = stream and show_thinking
    raw = _call_llm_with_timeout(
        f"{system}\n\n{prompt}", model_name, backend,
        stream=actual_stream, show_thinking=show_thinking, temperature=0.7
    ).strip()
    if not raw:
        return {"raw": "...", "thinking": "...", "vote": random.choice(candidates)}
    thinking, vote = _parse_thinking_vote(raw, candidates)
    if stream and not show_thinking:
        print(f"投票：{vote}")
    return {"raw": raw, "thinking": thinking, "vote": vote}


def _parse_discussion(text):
    """从模型回复中解析「发言：XXX」。"""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"\*\*|__", "", text).strip()
    # 优先抓「发言：」
    m = re.search(r"发言[：:]\s*(.*)", text)
    if m:
        speech = m.group(1).strip().split('\n')[0].strip()
    else:
        # fallback：取最后一行非空内容
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        speech = lines[-1] if lines else text
    # 清理
    speech = re.sub(r"(思考|投票)[：:].*", "", speech, flags=re.DOTALL).strip()
    speech = speech[:60]
    return speech


def get_discussion(model_name, backend, player_id, role, word, history, round_no,
                   alive, num_players, personality, disc_round,
                   stream=False, show_thinking=True):
    """讨论阶段：让玩家发表一句意见（指出可疑者或为自己辩护）。"""
    system = build_system_prompt(player_id, role, word, num_players, personality,
                                  round_no=round_no, show_thinking=show_thinking, phase="discuss")
    recent_history = history[-15:] if len(history) > 15 else history
    history_str = chr(10).join(recent_history)
    alive_names = "、".join([f"玩家{i}" for i in alive])
    if show_thinking:
        fmt_reminder = "必须遵守「思考：」与「发言：」格式，发言不超过 30 字。"
    else:
        fmt_reminder = "只输出「发言：XXX」一行，不超过 30 字，不要有其他文字。"
    prompt = f"""【第 {round_no} 轮 - 讨论阶段（第 {disc_round} 轮发言）】
当前发言记录：
{history_str}

存活玩家：{alive_names}
现在轮到你【玩家 {player_id}】发言。你可以：
- 点名怀疑某位玩家并说明理由
- 为自己辩解（如果有人怀疑你）
- 附和或反驳他人的判断

要求：
- {fmt_reminder}
- 发言要有立场，不能说废话，不能回避。

现在请开始你的回复："""
    actual_stream = stream and show_thinking
    raw = _call_llm_with_timeout(
        f"{system}\n\n{prompt}", model_name, backend,
        stream=actual_stream, show_thinking=show_thinking, temperature=0.8
    ).strip()
    if not raw:
        return {"raw": "...", "thinking": "...", "speech": "我觉得大家都很可疑。"}
    speech = _parse_discussion(raw)
    # 解析思考部分
    thinking = ""
    m_think = re.search(r"思考[：:]\s*(.*?)(?=发言[：:]|$)", raw, re.DOTALL)
    if m_think:
        thinking = m_think.group(1).strip()[:100]
    if stream and not show_thinking:
        print(f"发言：{speech}")
    return {"raw": raw, "thinking": thinking, "speech": speech}




def save_game_record(record):
    os.makedirs("game_logs", exist_ok=True)
    filename = f"game_logs/game_{record['id'][:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# 谁是卧底 游戏记录\n\n")
        f.write(f"- **时间**: {record['created_at']}\n")
        f.write(f"- **题组**: {record['group_name']}\n")
        f.write(f"- **后端**: {record['config']['backend']} / {record['config']['model_name']}\n")
        f.write(f"- **胜利者**: {record['winner']}\n\n")
        f.write(f"## 玩家配置\n")
        for p in record['roles']:
            human_tag = " (人类)" if p['is_human'] else ""
            f.write(f"- 玩家{p['id']}: {p['role']} ({p['word']}){human_tag} - 性格: {p['personality']}\n")
        f.write(f"\n## 游戏过程\n")
        for r in record['rounds']:
            f.write(f"### 第 {r['round']} 轮\n#### 描述阶段\n")
            for d in r['descriptions']:
                f.write(f"- **玩家{d['player_id']}**: {d['description']}\n")
                f.write(f"  - *思考*: {d['thinking']}\n")
            if r.get('discussions'):
                f.write(f"\n#### 讨论阶段\n")
                cur_round = 0
                for disc in r['discussions']:
                    if disc['disc_round'] != cur_round:
                        cur_round = disc['disc_round']
                        f.write(f"\n**第 {cur_round} 轮讨论**\n")
                    f.write(f"- **玩家{disc['player_id']}**: {disc['speech']}\n")
                    f.write(f"  - *思考*: {disc['thinking']}\n")
            f.write(f"\n#### 投票阶段\n")
            for v in r['votes']:
                f.write(f"- **玩家{v['player_id']}** 投给了 **玩家{v['vote_to']}**\n")
                f.write(f"  - *思考*: {v['thinking']}\n")
            f.write(f"\n**淘汰者**: 玩家{r['eliminated']}\n\n")
    return filename


SCOREBOARD = {}

def update_scoreboard(record):
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
    print("\n" + "="*20 + " 累计计分板 " + "="*20)
    print(f"{'玩家':<10} {'身分':<10} {'勝':<5} {'敗':<5} {'胜率':<10}")
    for p_id, stats in sorted(SCOREBOARD.items()):
        identity = "你" if stats['is_human'] else "AI"
        total = stats['win'] + stats['loss']
        win_rate = f"{(stats['win']/total)*100:.1f}%" if total > 0 else "0%"
        print(f"玩家{p_id:<8} {identity:<10} {stats['win']:<5} {stats['loss']:<5} {win_rate:<10}")
    print("="*52)


# ─────────────────────────────────────────────
def _judge_semantic_match(word_a: str, word_b: str, model_name: str, backend: str) -> bool:
    """用 LLM 判断两个词语义是否几乎相同（如「客厅」和「客廳」、「开心」和「高兴」）。"""
    # 先做字面清理再比较，处理简繁体等
    if word_a.strip() == word_b.strip():
        return True
    prompt = f"""请判断以下两个词语是否表达了几乎相同的意思（含简繁体、同义词、近义词等情况均算相同）。

词A：{word_a}
词B：{word_b}

只需回答「相同」或「不同」，不要有任何解释。"""
    result = _call_llm_with_timeout(prompt, model_name, backend, stream=False, show_thinking=False, temperature=0.0).strip()
    result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
    return "相同" in result


# ─────────────────────────────────────────────
# 卧底反杀
# ─────────────────────────────────────────────

def spy_counter_kill(model_name, backend, player_id, word, history, civilian_word, stream=False):
    prompt = f"""你是【玩家 {player_id}】，你的身份是【卧底】，你的词是：「{word}」。
你现在被投出局了，但你还有最后一次「反杀」的机会！

根据以下游戏记录，请猜测平民手中的词是什么：
{chr(10).join(history)}

直接输出你猜测的一个词（例如：水饺），不要有任何废话或解释。
如果你猜对了，卧底将反败为胜！"""
    guess = _call_llm_with_timeout(
        prompt, model_name, backend, stream=False, show_thinking=False
    ).strip()
    guess = re.sub(r"<think>.*?</think>", "", guess, flags=re.DOTALL).strip()
    guess = re.sub(r"\*\*|__|[。！？?\n]", "", guess).strip()
    # 取第一行，防止模型多说废话
    guess = guess.split()[0] if guess.split() else guess
    is_correct = _judge_semantic_match(guess, civilian_word, model_name, backend)
    return guess, is_correct


# ─────────────────────────────────────────────
# 主游戏流程
# ─────────────────────────────────────────────

def run_game(
    word_group_choice="隨機",
    num_players=6,
    num_undercover=1,
    num_whites=1,
    model_name="qwen2.5:1.5b",
    backend=BACKEND_OLLAMA,
    stream=False,
    show_spoilers=True,
    show_thinking=True,
    human_id=None,
):
    if num_undercover + num_whites >= num_players or (num_undercover + num_whites) < 1:
        num_undercover = 1
        num_whites = 0

    group_name, word_civilian, word_undercover, player_data = assign_roles(
        num_players=num_players, num_undercover=num_undercover,
        num_whites=num_whites, group_choice=word_group_choice, human_id=human_id
    )

    if stream:
        backend_label = f"[后端：{backend} / {model_name}]"
        print(f"【游戏开始】题组：{group_name}  {backend_label}")
        print(f"玩家总数：{num_players} | 卧底人数：{num_undercover} | 白板人数：{num_whites}")
        if show_spoilers:
            print(f"平民词：{word_civilian} | 卧底词：{word_undercover}")
            print("玩家身份：")
            for p in player_data:
                human_tag = " (你)" if p['is_human'] else ""
                print(f"  玩家{p['id']}: {p['role']} ({p['word']}){human_tag} - 性格：{p['personality']}")
        elif human_id is not None:
            for p in player_data:
                if p['is_human']:
                    if p['role'] == "白板":
                        print(f"\n>>> [你是玩家 {p['id']}] 你是白板！你没有词，请观察别人发言。")
                    else:
                        print(f"\n>>> [你是玩家 {p['id']}] 你的词是: {p['word']}")
                    break
        print("-" * 30)

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
            "backend": backend,
        },
        "group_name": group_name,
        "word_civilian": word_civilian,
        "word_undercover": word_undercover,
        "roles": player_data,
        "rounds": [],
        "winner": None,
    }

    round_no = 0
    start_player_idx = 0

    while True:
        round_no += 1
        round_data = {"round": round_no, "descriptions": [], "discussions": [], "votes": [], "eliminated": None, "alive_after": []}

        if stream:
            clear_screen()
            # 重新打印本局基本信息
            print(f"【游戏开始】题组：{group_name}  [后端：{backend} / {model_name}]")
            print(f"玩家总数：{num_players} | 卧底人数：{num_undercover} | 白板人数：{num_whites}")
            alive_str = "、".join([f"玩家{i}" for i in alive])
            print(f"存活玩家：{alive_str}")
            # 打印历史发言记录（若有）
            if history_lines:
                print("\n── 历史记录 ──")
                for line in history_lines:
                    print(f"  {line}")
                print("──────────────")
            print(f"\n=== 第 {round_no} 轮 - 描述阶段 ===")

        current_order = []
        for i in range(num_players):
            p = (start_player_idx + i) % num_players
            if p in alive:
                current_order.append(p)

        for pid in current_order:
            p = player_info[pid]
            if p['is_human']:
                if p['role'] == "白板":
                    print(f"\n[玩家{pid}] (你) 你是白板！请观察别人描述。")
                else:
                    print(f"\n[玩家{pid}] (你) 的词是: {p['word']}")
                desc = input("请输入你的描述: ").strip()
                out = {"description": desc, "thinking": "人类玩家", "raw": desc}
            else:
                if stream:
                    display_role = f" ({p['role']})" if show_spoilers else ""
                    label = "思考與描述" if show_thinking else "描述"
                    print(f"\n[玩家{pid}]{display_role} ({p['personality']}) {label}：")
                    time.sleep(0.5)
                out = get_description(
                    model_name, backend, pid, p['role'], p['word'],
                    history_lines, round_no, num_players, p['personality'],
                    stream=stream, show_thinking=show_thinking
                )
            line = f"玩家{pid}：{out['description']}"
            history_lines.append(line)
            round_data["descriptions"].append({
                "player_id": pid, "description": out["description"],
                "thinking": out["thinking"], "raw": out["raw"],
            })

        # ── 讨论阶段：两轮，每轮所有存活玩家各发言一次 ──
        if stream:
            print(f"\n=== 第 {round_no} 轮 - 讨论阶段 ===")

        for disc_round in range(1, 3):   # 两轮讨论
            if stream:
                print(f"\n-- 讨论第 {disc_round} 轮 --")
            for pid in current_order:
                p = player_info[pid]
                if p['is_human']:
                    print(f"\n[玩家{pid}] (你) 请发言（可质疑他人或为自己辩护）:")
                    speech_input = input("你的发言: ").strip()
                    disc_out = {"speech": speech_input, "thinking": "人类发言", "raw": speech_input}
                else:
                    if stream:
                        display_role = f" ({p['role']})" if show_spoilers else ""
                        label = "思考與发言" if show_thinking else "发言"
                        print(f"\n[玩家{pid}]{display_role} ({p['personality']}) {label}：")
                        time.sleep(0.5)
                    disc_out = get_discussion(
                        model_name, backend, pid, p['role'], p['word'],
                        history_lines, round_no, alive, num_players, p['personality'],
                        disc_round=disc_round, stream=stream, show_thinking=show_thinking
                    )
                disc_line = f"[讨论] 玩家{pid}：{disc_out['speech']}"
                history_lines.append(disc_line)
                round_data["discussions"].append({
                    "player_id": pid,
                    "disc_round": disc_round,
                    "speech": disc_out["speech"],
                    "thinking": disc_out["thinking"],
                })

        if stream:
            print(f"\n=== 第 {round_no} 轮 - 投票阶段 ===")

        for pid in alive:
            p = player_info[pid]
            if p['is_human']:
                others = [a for a in alive if a != pid]
                print(f"\n[玩家{pid}] (你) 请投票。除自己外的存活玩家: {others}")
                while True:
                    try:
                        v_input = input("请输入你要投的玩家编号: ").strip()
                        v_id = int(v_input)
                        if v_id in others:
                            out = {"vote": v_id, "thinking": "人类投票", "raw": v_input}
                            break
                        elif v_id == pid:
                            print(f"你不能投给自己！请从其他玩家 {others} 中选择。")
                        else:
                            print(f"玩家 {v_id} 不在存活名单中，请重新输入。")
                    except ValueError:
                        print("请输入有效的数字编号。")
            else:
                if stream:
                    display_role = f" ({p['role']})" if show_spoilers else ""
                    label = "思考與投票" if show_thinking else "投票"
                    print(f"\n[玩家{pid}]{display_role} ({p['personality']}) {label}：")
                    time.sleep(0.5)
                out = get_vote(
                    model_name, backend, pid, p['role'], p['word'],
                    history_lines, round_no, alive, num_players, p['personality'],
                    stream=stream, show_thinking=show_thinking
                )
            round_data["votes"].append({
                "player_id": pid, "vote_to": out["vote"],
                "thinking": out["thinking"], "raw": out["raw"],
            })

        votes_count = {}
        for v in round_data["votes"]:
            p = v["vote_to"]
            votes_count[p] = votes_count.get(p, 0) + 1

        if stream:
            print("\n【投票统计】")
            for p, c in votes_count.items():
                print(f"玩家{p}: {c} 票")

        max_votes = max(votes_count.values())
        tied = [target for target, count in votes_count.items() if count == max_votes]

        # 平票：重新投票，候选人限缩为平票玩家
        if len(tied) > 1:
            if stream:
                tied_names = "、".join([f"玩家{t}" for t in tied])
                print(f"\n⚠️  平票！{tied_names} 票数相同，进行重新投票（仅限以上候选人）...")
            revote_count = {}
            for pid in alive:
                p = player_info[pid]
                if p['is_human']:
                    print(f"\n[玩家{pid}] (你) 重新投票，候选人: {tied}")
                    while True:
                        try:
                            v_input = input("请输入你要投的玩家编号: ").strip()
                            v_id = int(v_input)
                            if v_id in tied:
                                revote_count[v_id] = revote_count.get(v_id, 0) + 1
                                break
                            else:
                                print(f"只能投 {tied} 中的玩家。")
                        except ValueError:
                            print("请输入有效的数字编号。")
                else:
                    # AI 重新投票，候选人限缩为 tied
                    out2 = get_vote(
                        model_name, backend, pid, p['role'], p['word'],
                        history_lines, round_no, tied, num_players, p['personality'],
                        stream=False, show_thinking=False
                    )
                    v = out2["vote"] if out2["vote"] in tied else random.choice(tied)
                    revote_count[v] = revote_count.get(v, 0) + 1

            if stream:
                print("\n【重新投票统计】")
                for p, c in revote_count.items():
                    print(f"玩家{p}: {c} 票")

            max_revote = max(revote_count.values())
            still_tied = [t for t, c in revote_count.items() if c == max_revote]
            eliminated = still_tied[0] if len(still_tied) == 1 else random.choice(still_tied)
            if len(still_tied) > 1 and stream:
                print(f"仍然平票，随机淘汰玩家{eliminated}。")
        else:
            eliminated = tied[0]
        round_data["eliminated"] = eliminated
        alive = [target for target in alive if target != eliminated]
        round_data["alive_after"] = list(alive)
        start_player_idx = (eliminated + 1) % num_players

        role_info = f"（身份是：{player_info[eliminated]['role']}）" if show_spoilers or player_info[eliminated]['is_human'] else ""
        result_msg = f"【投票结果】玩家{eliminated} 被淘汰{role_info}。"
        history_lines.append(result_msg)
        if stream:
            print(f"\n{result_msg}")
            print("-" * 30)

        record["rounds"].append(round_data)

        non_civilians_alive = [p_id for p_id in alive if player_info[p_id]['role'] in ["卧底", "白板"]]

        if player_info[eliminated]['role'] == "卧底":
            if stream:
                print(f"\n🎭 玩家{eliminated} 是卧底！触发「反杀」机制...")
            if player_info[eliminated]['is_human']:
                print(f"\n>>> [你是卧底] 你还有最后一次机会！")
                guess = input(f"请猜测平民词是什么: ").strip()
                is_correct = _judge_semantic_match(guess, word_civilian, model_name, backend)
            else:
                guess, is_correct = spy_counter_kill(
                    model_name, backend, eliminated, player_info[eliminated]['word'],
                    history_lines, word_civilian, stream=stream
                )
            if stream:
                print(f"卧底猜测平民词为：{guess}")
            if is_correct:
                record["winner"] = "卧底"
                if stream:
                    print(f"🎯 猜对了！平民词正是「{word_civilian}」。卧底反杀成功，卧底获胜！")
                break
            else:
                if stream:
                    print(f"❌ 猜错了！平民词是「{word_civilian}」。")
                if not non_civilians_alive:
                    record["winner"] = "平民"
                    if stream:
                        print("🎉 所有卧底与白板均已出局，平民获胜！")
                    break

        elif player_info[eliminated]['role'] == "白板":
            if not non_civilians_alive:
                record["winner"] = "平民"
                if stream:
                    print("🎉 所有卧底与白板均已出局，平民获胜！")
                break

        civilians_alive = [p_id for p_id in alive if player_info[p_id]['role'] == "平民"]
        if len(civilians_alive) <= 2 and non_civilians_alive:
            record["winner"] = "非平民陣營"
            if stream:
                print("\n😈 平民人数不足，非平民阵营（卧底与白板）获胜！")
            break

    return record


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    group_choice  = os.environ.get("WORD_GROUP", "隨機")
    num_players   = int(os.environ.get("NUM_PLAYERS", "6"))
    num_undercover = int(os.environ.get("NUM_UNDERCOVER", "1"))
    num_whites    = int(os.environ.get("NUM_WHITES", "1"))

    if len(sys.argv) > 1:
        group_choice = sys.argv[1]

    clear_screen()
    print("=== 谁是卧底 游戏设置 ===\n")

    # ── 選擇後端 ──
    backend, model_name = select_backend()
    print(f"\n✅ 已選擇后端：{backend}，模型：{model_name}\n")

    # ── 是否親自玩 ──
    user_play = input("你想亲自参与游戏吗？(y/N): ").lower() == 'y'
    human_id = random.randint(0, num_players - 1) if user_play else None

    # ── 劇透設定 ──
    if user_play:
        show_spoilers = False
        print("因为你要亲自参与，剧透功能已自动关闭。")
    else:
        spoil_input = input("是否要显示剧透（显示所有玩家身份与词汇）？[Y/n]: ").strip().lower()
        show_spoilers = spoil_input != 'n'

    # ── 思考過程 ──
    print("\n提示：开启「显示思考过程」可实时看到模型运作，体验更流畅。")
    think_input = input("是否要显示玩家思考过程？[Y/n]: ").strip().lower()
    show_thinking = think_input != 'n'

    print(f"\n游戏设置完成！(角色: {'人类+AI' if user_play else '全AI'}, 提示: {'开启' if show_thinking else '关闭'})")
    print("按下 Ctrl+C 可随时结束游戏。\n")

    try:
        game_count = 0
        while True:
            game_count += 1
            clear_screen()
            print(f"\n{'='*20} 第 {game_count} 场游戏 开始 {'='*20}\n")

            try:
                record = run_game(
                    word_group_choice=group_choice,
                    num_players=num_players,
                    num_undercover=num_undercover,
                    num_whites=num_whites,
                    model_name=model_name,
                    backend=backend,
                    stream=True,
                    show_spoilers=show_spoilers,
                    show_thinking=show_thinking,
                    human_id=human_id,
                )

                update_scoreboard(record)
                print_scoreboard()

                filename = save_game_record(record)
                print(f"\n[系统提示] 游戏记录已存档至: {filename}")

                print("\n" + "="*30)
                print(f"第 {game_count} 场游戏结束")
                print("Game ID:", record["id"])
                print("Winner:", record["winner"])
                print("="*30)

            except KeyboardInterrupt:
                raise   # 让外层捕获
            except Exception as e:
                print(f"\n[系统警告] 第 {game_count} 场游戏发生意外错误：{e}")
                print("           将在 10 秒后自动开始下一场...")
                time.sleep(10)
                continue

            print(f"\n即将开始下一场游戏...")
            time.sleep(3)

    except KeyboardInterrupt:
        print("\n\n检测到 Ctrl+C，游戏已停止。感谢游玩！")
        sys.exit(0)