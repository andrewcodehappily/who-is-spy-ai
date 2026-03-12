# 誰是臥底 AI 遊戲平台 (Who is Undercover AI)

[Read in English](#english-version) | [中文版](#中文版)

---

<a name="中文版"></a>

## 誰是臥底 AI 遊戲平台 (Who is Undercover AI)

這是一個由大型語言模型 (LLM) 驅動的「誰是臥底」遊戲平台。支援 **Ollama (本地模型)** 與 **Google Gemini (雲端模型)**，具備多樣化的 AI 性格、人類玩家參與模式、特殊角色「白板」、以及自動存檔與計分系統。

### 🌟 核心特色

- **雙模型支援**：可切換使用本地 Ollama (如 `qwen3:4b`) 或 Google Gemini。
- **即時串流輸出**：支援逐字顯示 AI 的思考與發言過程，遊戲感更真實。
- **多樣化 AI 性格**：包含「冷靜分析型」、「熱情活潑型」、「疑心病重型」等，讓對局充滿變數。
- **人類參與模式**：你可以親自加入遊戲，與 AI 同台競技，系統會自動為你隱藏劇透資訊。
- **特殊機制**：
  - **白板 (Blank)**：完全不知道詞彙的角色，必須透過觀察他人發言來隱藏身分。
  - **臥底反殺**：臥底被投出後，若能猜中平民詞，即可反敗為勝。
- **跨平台相容**：優化了 Windows/Mac/Linux 的執行環境與編碼處理。
- **自動記錄**：每場遊戲都會自動生成 Markdown 格式的詳細戰報於當前目錄下。

### 🎮 快速開始

#### 1. 安裝環境
建議使用 Python 3.10+。首先複製專案並安裝依賴：

# 建立虛擬環境 (推薦)
python -m venv .venv
source .venv/bin/activate  # Windows 使用: .venv\Scripts\activate

# 安裝必要套件
pip install -r requirements.txt

#### 2. 設定環境變數
建立一個 .env 檔案，並填入你的資訊：

GOOGLE_API_KEY=你的_GEMINI_API_KEY
MODEL_NAME=qwen3:4b  # 預設模型 (Ollama 名稱需包含冒號)
NUM_PLAYERS=6
NUM_UNDERCOVER=1
NUM_WHITES=1

#### 3. 執行遊戲
直接執行 undercover.py 即可開始：

python undercover.py

### 🛠️ 遊戲設定說明
啟動後，你可以進行以下互動設定：
1. **親自遊玩**：輸入 y 即可加入遊戲，系統會隨機分配一個位置給你。
2. **劇透設定**：如果不親自玩，可以開啟劇透模式查看所有人的身分與詞彙。
3. **思考過程**：開啟後可即時看到 AI 的推理邏輯（推薦開啟）。

### 📝 題庫分類
遊戲內建豐富題庫，涵蓋多種維度：
- **生活類**：牙膏 vs 洗面乳、行動電源 vs 充電頭
- **飲食類**：拿鐵 vs 卡布奇諾、雞排 vs 鹹酥雞
- **影視類**：甄嬛傳 vs 如懿傳、復仇者聯盟 vs 正義聯盟
- **高難度類**：勇氣 vs 毅力、暗戀 vs 單戀
- ... 以及更多趣味組合。

### 📂 檔案結構
- undercover.py: 遊戲核心邏輯與執行檔。
- app.py: Flask 網頁版應用程式。
- requirements.txt: 專案依賴清單。
- game_*.md: 遊戲結束後自動存放於當前目錄的 Markdown 遊戲記錄。
- .env.example: 環境設定範例檔。

### ⚠️ 注意事項
- 使用 Ollama 時，請確保後端服務已啟動 (ollama serve)。
- 若在 Windows 終端機遇到亂碼，程式已內建 UTF-8 強制修正，建議使用 PowerShell 或 Windows Terminal 執行。
- 程式設有 300 秒超時保護，避免模型陷入死循環。
## 🐳 使用 Docker 啟動 (推薦專業玩家)

如果你不想在本地安裝 Python 環境，可以使用 Docker 一鍵啟動網頁版：

1. 確保已安裝 Docker 與 Docker Compose。
2. 建立並設定 `.env` 檔案。
3. 執行指令：
   ```bash
   docker-compose up -d
---

<a name="english-version"></a>

## Who is the Spy AI Game Platform (Who is Undercover AI)

This is an LLM-driven "Who is the Spy" (Undercover) game platform. It supports **Ollama (local models)** and **Google Gemini (cloud models)**, featuring diverse AI personalities, a human player mode, a special "Blank" (Whiteboard) role, and an automated saving and scoring system.

### 🌟 Core Features

- **Dual Model Support**: Switch seamlessly between local Ollama (e.g., qwen3:4b) or Google Gemini.
- **Real-time Streaming Output**: See the AI's thought process and statements typed out word-by-word for a more immersive game experience.
- **Diverse AI Personalities**: Includes personalities like "Calm & Analytical", "Enthusiastic & Lively", and "Suspicious", making every match unpredictable.
- **Human Player Mode**: Join the game yourself and compete against the AI. The system will automatically hide spoilers for your session.
- **Special Mechanics**:
  - **Blank (Whiteboard)**: A role that receives no word at all. They must observe others' descriptions to blend in and hide their identity.
  - **Undercover Counter-kill**: If the Undercover is voted out, they have one last chance to guess the Civilian word and snatch a victory.
- **Cross-Platform Compatibility**: Optimized execution environments and encoding handling for Windows, Mac, and Linux.
- **Auto-Logging**: Every game automatically generates a detailed battle report in Markdown format directly in the current directory.

### 🎮 Quick Start

#### 1. Environment Setup
Python 3.10+ is recommended. Clone the project and install the dependencies:

# Create a virtual environment (Recommended)
python -m venv .venv
source .venv/bin/activate  # For Windows: .venv\Scripts\activate

# Install required packages
pip install -r requirements.txt

#### 2. Configure Environment Variables
Create a .env file and fill in your information:

GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
MODEL_NAME=qwen3:4b  # Default model (Ollama names must include a colon)
NUM_PLAYERS=6
NUM_UNDERCOVER=1
NUM_WHITES=1

#### 3. Run the Game
Execute undercover.py to start:

python undercover.py

### 🛠️ Game Settings
Upon launch, you can configure the following interactions:
1. **Play Yourself**: Enter y to join the game. The system will randomly assign you a seat.
2. **Spoiler Settings**: If you choose to spectate (all-AI game), you can enable spoiler mode to see everyone's identity and word.
3. **Thinking Process**: Enabling this allows you to see the AI's reasoning logic in real-time (Highly Recommended).

### 📝 Word Pools
The game includes a rich built-in word pool covering various categories:
- **Daily Life**: Toothpaste vs. Facial Cleanser, Power Bank vs. Charging Block
- **Food & Drinks**: Latte vs. Cappuccino, Fried Chicken vs. Popcorn Chicken
- **Movies & TV**: Empresses in the Palace vs. Ruyi's Royal Love in the Palace, Avengers vs. Justice League
- **High Difficulty**: Courage vs. Perseverance, Secret Crush vs. Unrequited Love
- ... and many more fun combinations.

### 📂 File Structure
- undercover.py: Core game logic and executable.
- app.py: Flask web application.
- requirements.txt: Project dependencies list.
- game_*.md: Auto-saved Markdown game records generated in the current directory.
- .env.example: Environment configuration example file.

### ⚠️ Notes
- When using Ollama, ensure the backend service is running (ollama serve).
- If you encounter garbled text in the Windows terminal, the program includes a UTF-8 forced fix, but using PowerShell or Windows Terminal is recommended.
- The program has a 300-second timeout protection to prevent the model from entering infinite loops.

---
*祝你在這場 AI 心理戰中獲得勝利！ / Good luck winning this AI psychological warfare!*
