# 誰是臥底 AI 遊戲平台 (Who is Undercover AI)

這是一個由大型語言模型 (LLM) 驅動的「誰是臥底」遊戲平台。支援 **Ollama (本地模型)** 與 **Google Gemini (雲端模型)**，具備多樣化的 AI 性格、人類玩家參與模式、特殊角色「白板」、以及自動存檔與計分系統。

## 🌟 核心特色

- **雙模型支援**：可切換使用本地 Ollama (如 `qwen3:4b`) 或 Google Gemini。
- **即時串流輸出**：支援逐字顯示 AI 的思考與發言過程，遊戲感更真實。
- **多樣化 AI 性格**：包含「冷靜分析型」、「熱情活潑型」、「疑心病重型」等，讓對局充滿變數。
- **人類參與模式**：你可以親自加入遊戲，與 AI 同台競技，系統會自動為你隱藏劇透資訊。
- **特殊機制**：
  - **白板 (Blank)**：完全不知道詞彙的角色，必須透過觀察他人發言來隱藏身分。
  - **臥底反殺**：臥底被投出後，若能猜中平民詞，即可反敗為勝。
- **跨平台相容**：優化了 Windows/Mac/Linux 的執行環境與編碼處理。
- **自動記錄**：每場遊戲都會自動生成 Markdown 格式的詳細戰報於 `game_logs/` 資料夾。

## 🎮 快速開始

### 1. 安裝環境
建議使用 Python 3.10+。首先複製專案並安裝依賴：

```bash
# 建立虛擬環境 (推薦)
python -m venv .venv
source .venv/bin/activate  # Windows 使用: .venv\Scripts\activate

# 安裝必要套件
pip install -r requirements.txt
```

### 2. 設定環境變數
建立一個 `.env` 檔案，並填入你的 API Key (若使用 Gemini)：

```env
GOOGLE_API_KEY=你的_GEMINI_API_KEY
MODEL_NAME=qwen3:4b  # 預設模型 (Ollama 名稱需包含冒號)
NUM_PLAYERS=6
NUM_UNDERCOVER=1
NUM_WHITES=1
```

### 3. 執行遊戲
直接執行 `undercover.py` 即可開始：

```bash
python undercover.py
```

## 🛠️ 遊戲設定說明

啟動後，你可以進行以下互動設定：
1. **親自遊玩**：輸入 `y` 即可加入遊戲，系統會隨機分配一個位置給你。
2. **劇透設定**：如果不親自玩，可以開啟劇透模式查看所有人的身分與詞彙。
3. **思考過程**：開啟後可即時看到 AI 的推理邏輯（推薦開啟）。

## 📝 題庫分類
遊戲內建豐富題庫，涵蓋多種維度：
- **生活類**：牙膏 vs 洗面乳、行動電源 vs 充電頭
- **飲食類**：拿鐵 vs 卡布奇諾、雞排 vs 鹹酥雞
- **影視類**：甄嬛傳 vs 如懿傳、復仇者聯盟 vs 正義聯盟
- **高難度類**：勇氣 vs 毅力、暗戀 vs 單戀
- ... 以及更多趣味組合。

## 📂 檔案結構
- `undercover.py`: 遊戲核心邏輯與執行檔。
- `requirements.txt`: 專案依賴清單。
- `game_logs/`: 自動存放的 Markdown 遊戲記錄。
- `.env`: 環境設定檔。

## ⚠️ 注意事項
- 使用 Ollama 時，請確保後端服務已啟動 (`ollama serve`)。
- 若在 Windows 終端機遇到亂碼，程式已內建 UTF-8 強制修正，建議使用 PowerShell 或 Windows Terminal 執行。
- 程式設有 300 秒超時保護，避免模型陷入死循環。

---
*祝你在這場 AI 心理戰中獲得勝利！*
