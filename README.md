# AI Investment Arena

**An AI-Powered Hedge Fund Simulator for Indian Equities (NSE/NIFTY200)**

Compete multiple LLM-driven investment strategies against each other in real-time. Watch different AI models manage portfolios with distinct philosophies, generate stock picks, and compete on a live performance leaderboard.

---

## 📌 Overview

AI Investment Arena simulates a multi-manager hedge fund where different Large Language Models act as portfolio managers with unique investment styles.

Each day:

- Market data is collected from NSE stocks
- Technical indicators are calculated
- Stocks are ranked using TOPSIS
- Multiple AI models build portfolios
- Performance is tracked throughout the trading session
- A live leaderboard ranks the best-performing AI manager

---

## 🎯 Key Features

### 🤖 Multiple AI Portfolio Managers

| Model | Philosophy |
|---|---|
| GPT-4o Mini | Quantitative & Risk-Adjusted |
| Gemini 2.5 Flash | Aggressive Growth |
| Mistral Voxtral | Conservative Value |
| DeepSeek V4 | Pure Data-Driven TOPSIS |

### 📈 Real-Time Market Data

- Upstox API Integration
- NSE Live Quotes
- Historical Candle Data
- Instrument Key Resolution
- Multi-Level Caching System
- Automatic Fallback Mechanisms

### 📊 Technical Analysis Engine

The ranking engine computes:

| Indicator | Description |
|---|---|
| RSI | 14-period Relative Strength Index |
| SMA 20 | 20-period Simple Moving Average |
| SMA 50 | 50-period Simple Moving Average |
| Volatility | Annualized Volatility |
| Volume Ratio | Relative volume vs average |
| Trend Score | Composite trend direction |
| 1-Month Return | Rolling 1-month price return |
| TOPSIS Score | Final multi-factor ranking |

### 💰 Portfolio Simulation

```
Market Open → Generate AI Portfolios → Lock Entry Prices
     → Track Intraday Prices → Calculate P&L → Update Leaderboard
```

### 🏆 Live Leaderboard

- Daily Returns
- Monthly Returns
- All-Time Returns
- Portfolio Value
- Unrealized P&L
- Model Rankings

### ⚙️ Manual Controls

Administrative endpoints allow manual portfolio generation, valuation updates, TOPSIS testing, and portfolio recalculation — without breaking portfolio integrity.

---

## 🏗️ System Architecture

```
                    ┌─────────────────┐
                    │   Scheduler     │
                    │  APScheduler    │
                    └────────┬────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────┐
│                 FastAPI Backend                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  Routes                                            │
│  ├── /market                                       │
│  ├── /portfolios                                   │
│  ├── /leaderboard                                  │
│  └── /admin/*                                      │
│                                                    │
│  Services                                          │
│  ├── market_data.py                                │
│  ├── llm_portfolio.py                              │
│  └── valuation.py                                  │
│                                                    │
│  Database                                          │
│  ├── Portfolio                                     │
│  ├── Holding                                       │
│  ├── DailyValuation                                │
│  └── MarketSnapshot                                │
└────────────────────────────────────────────────────┘
             │                        │
             ▼                        ▼
      ┌─────────────┐       ┌──────────────────┐
      │ Upstox API  │       │  LLM Providers   │
      └─────────────┘       ├──────────────────┤
                            │ OpenAI           │
                            │ Gemini           │
                            │ Mistral          │
                            │ DeepSeek         │
                            └──────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/ai-investment-arena.git
cd ai-investment-arena
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_investment_arena

UPSTOX_ANALYTICS_TOKEN=your_token

AICREDITS_BASE_URL=https://api.aicredits.com/v1
AICREDITS_API_KEY=your_api_key

SCHEDULER_TIMEZONE=Asia/Kolkata

TOP_CANDIDATES=15
STARTING_CAPITAL=100000
```

### 5. Initialize Database

```bash
python -c "
from database import Base, engine
Base.metadata.create_all(bind=engine)
"
```

### 6. Start Server

```bash
uvicorn main:app --reload
```

- App: [http://localhost:8000](http://localhost:8000)
- Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📡 API Endpoints

### Market Data

```http
GET /market
```

Returns latest TOPSIS-ranked stock candidates.

### Portfolios

```http
GET /portfolios
GET /portfolios/{id}
```

### Leaderboard

```http
GET /leaderboard
```

Returns daily, monthly, and all-time rankings.

### Admin

```http
POST /admin/simulate-and-save   # Generate portfolios
POST /admin/update-valuations   # Update valuations
POST /admin/simulate            # Run TOPSIS only
```

---

## 🔄 Daily Workflow

### Morning Session — 09:25 AM IST

```
Fetch Market Data → Compute Indicators → TOPSIS Ranking
     → Top 15 Stocks → LLM Portfolio Generation → Save Portfolios
```

### Closing Session — 03:35 PM IST

```
Fetch Latest Prices → Update Holdings → Calculate P&L
     → Store Valuations → Update Leaderboard
```

---

## 📊 TOPSIS Ranking Methodology

| Factor | Weight |
|---|---|
| 1-Month Return | 30% |
| Volume Ratio | 20% |
| Trend Score | 20% |
| RSI Score | 15% |
| Volatility | 15% |

Stocks receive a final score between `0.0` and `1.0`. Top-ranked stocks are passed to AI portfolio managers.

---

## 🗄️ Database Schema

### Portfolio

```
Portfolio
├── model
├── date
├── starting_capital
├── total_invested
├── remaining_cash
├── strategy_summary
└── holdings[]
```

### Holding

```
Holding
├── ticker
├── quantity
├── entry_price
├── allocation_percent
├── confidence
└── reasoning
```

### DailyValuation

```
DailyValuation
├── portfolio_value
├── return_pct
├── unrealized_pnl
└── per_holding_pnl
```

---

## ⚙️ Configuration

### Supported Models

```python
SUPPORTED_MODELS = {
    "gpt":      "gpt-4o-mini",
    "gemini":   "gemini-2.5-flash",
    "mistral":  "voxtral-small",
    "deepseek": "deepseek-v4"
}
```

### Scheduler Jobs

```
09:25 AM IST  →  morning_job()
03:35 PM IST  →  close_job()
```

---

## 📈 Performance Metrics

| Metric | Description |
|---|---|
| Daily Return % | Single-day gain/loss |
| Monthly Return % | Rolling 30-day performance |
| Cumulative Return | All-time return since inception |
| Sharpe Ratio | Risk-adjusted return |
| Max Drawdown | Largest peak-to-trough decline |
| Win Rate | % of profitable trading days |

---

## 🧪 Project Structure

```
ai-investment-arena/
│
├── main.py
├── config.py
├── database.py
├── scheduler.py
│
├── routes/
│   ├── market.py
│   ├── portfolios.py
│   ├── leaderboard.py
│   └── admin.py
│
├── services/
│   ├── market_data.py
│   ├── llm_portfolio.py
│   └── valuation.py
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🔐 Security

- Environment-based secrets
- Database connection isolation
- Input validation via Pydantic
- Configurable CORS
- Rate limiting support

---

## 🛣️ Roadmap

- [ ] Telegram Alerts
- [ ] Email Notifications
- [ ] Historical Backtesting
- [ ] Sharpe & Sortino Analysis
- [ ] MACD & Bollinger Bands
- [ ] React Dashboard
- [ ] Full Test Coverage

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Contributions are welcome!

---

## 📄 License

Released under the [MIT License](LICENSE).

---

## 🎓 What You'll Learn

- Multi-LLM Systems
- Quantitative Finance
- Portfolio Simulation
- TOPSIS Ranking
- FastAPI
- SQLAlchemy
- APScheduler
- Real-Time Data Pipelines

---

## ⭐ Support the Project

If you found this project useful, please consider:

- ⭐ Starring the repository
- 🍴 Forking it
- 🛠️ Contributing

---

*Built for AI, Finance, and Quantitative Investing Enthusiasts. 🚀*
