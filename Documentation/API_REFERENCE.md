# AI Investment Arena — API Reference

## Overview

**Base URL:** `http://localhost:8000`  
**API Version:** 2.0.0  
**Framework:** FastAPI  
**Documentation:** http://localhost:8000/docs (Swagger UI)

All endpoints return JSON. Most endpoints support filtering via query parameters.

---

## 📋 Health & Status Endpoints

### GET /health
Check backend health and status.

**Request:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "portfolios_today": 5
}
```

**Status Codes:**
- `200 OK` — Backend is healthy

---

## 🎯 Simulation Endpoints

### GET /simulation/today
Get today's simulation data including market candidates and all model results.

**Request:**
```bash
curl http://localhost:8000/simulation/today
```

**Response:**
```json
{
  "date": "2024-05-23",
  "market_candidates": [
    {
      "ticker": "HDFCBANK.NS",
      "current_price": 1750.50,
      "rsi": 65.2,
      "volatility": 12.5,
      "volume_ratio": 1.1,
      "one_month_return": 5.3,
      "sector": "Financials",
      "trend_score": 75.5,
      "topsis_score": 0.85
    }
    // ... more candidates
  ],
  "model_results": [
    {
      "model": "gpt",
      "starting_capital": 100000.0,
      "remaining_cash": 25000.0,
      "strategy_summary": "Value investing with growth bias",
      "risk_level": "moderate",
      "current_return": 8.5,
      "portfolio_value": 108500.0,
      "portfolio": [
        {
          "ticker": "HDFCBANK.NS",
          "quantity": 50,
          "entry_price": 1700.0,
          "invested_amount": 85000.0,
          "allocation_percent": 75.0,
          "confidence": 0.92,
          "reasoning": "Strong financials, consistent dividend payer",
          "sector": "Financials"
        }
        // ... more holdings
      ]
    }
    // ... results for other models
  ]
}
```

**Query Parameters:**
- `date` (optional): Specific date in YYYY-MM-DD format

**Status Codes:**
- `200 OK` — Success
- `404 Not Found` — No simulation data for that date

---

## 📊 Leaderboard Endpoints

### GET /leaderboard
Get AI model performance leaderboard.

**Request:**
```bash
curl http://localhost:8000/leaderboard
```

**Response:**
```json
[
  {
    "model": "gpt",
    "average_return_percent": 6.75,
    "best_return_percent": 12.5,
    "worst_return_percent": -3.2,
    "days_active": 45,
    "win_rate": 0.78,
    "latest_return": 8.5,
    "total_portfolios": 45
  },
  {
    "model": "gemini",
    "average_return_percent": 5.25,
    "best_return_percent": 10.2,
    "worst_return_percent": -5.1,
    "days_active": 45,
    "win_rate": 0.71,
    "latest_return": 6.3,
    "total_portfolios": 45
  }
  // ... more models
]
```

**Query Parameters:**
- `limit` (optional): Max number of results (default: 100)
- `sort_by` (optional): `average_return`, `win_rate`, `days_active` (default: `average_return`)
- `order` (optional): `asc` or `desc` (default: `desc`)

**Status Codes:**
- `200 OK` — Success
- `400 Bad Request` — Invalid parameters

---

## 🏢 Portfolio Endpoints

### GET /portfolios
Get all portfolios, optionally filtered by date or model.

**Request:**
```bash
curl http://localhost:8000/portfolios
curl http://localhost:8000/portfolios?date=2024-05-23
curl http://localhost:8000/portfolios?model=gpt
```

**Response:**
```json
[
  {
    "id": 1,
    "date": "2024-05-23",
    "model": "gpt",
    "starting_capital": 100000.0,
    "remaining_cash": 25000.0,
    "strategy_summary": "Value investing with growth bias",
    "risk_level": "moderate",
    "current_return": 8.5,
    "portfolio_value": 108500.0,
    "holdings": [
      {
        "ticker": "HDFCBANK.NS",
        "quantity": 50,
        "entry_price": 1700.0,
        "invested_amount": 85000.0,
        "allocation_percent": 75.0,
        "confidence": 0.92,
        "reasoning": "Strong balance sheet and consistent dividends",
        "sector": "Financials"
      }
      // ... more holdings
    ]
  }
  // ... more portfolios
]
```

**Query Parameters:**
- `date` (optional): Filter by date (YYYY-MM-DD)
- `model` (optional): Filter by model name (`gpt`, `gemini`, `mistral`, `deepseek`)
- `limit` (optional): Max results (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Status Codes:**
- `200 OK` — Success
- `400 Bad Request` — Invalid date format

---

## 📈 Market Data Endpoints

### GET /market/candidates
Get candidate stocks for portfolio selection.

**Request:**
```bash
curl http://localhost:8000/market/candidates
curl http://localhost:8000/market/candidates?date=2024-05-23
```

**Response:**
```json
[
  {
    "ticker": "HDFCBANK.NS",
    "current_price": 1750.50,
    "rsi": 65.2,
    "volatility": 12.5,
    "volume_ratio": 1.1,
    "one_month_return": 5.3,
    "sector": "Financials",
    "trend_score": 75.5,
    "topsis_score": 0.85
  },
  {
    "ticker": "INFY.NS",
    "current_price": 1620.75,
    "rsi": 52.1,
    "volatility": 14.2,
    "volume_ratio": 0.95,
    "one_month_return": -2.1,
    "sector": "Technology",
    "trend_score": 45.3,
    "topsis_score": 0.62
  }
  // ... more candidates
]
```

**Query Parameters:**
- `date` (optional): Specific date (default: today)
- `sector` (optional): Filter by sector (e.g., `Financials`, `Technology`)
- `limit` (optional): Max results (default: 50)
- `min_topsis` (optional): Minimum TOPSIS score (0.0-1.0)

**Status Codes:**
- `200 OK` — Success
- `404 Not Found` — No candidates for that date

---

## 📊 Analytics Endpoints

### GET /analytics/history
Get historical performance data for all models.

**Request:**
```bash
curl http://localhost:8000/analytics/history
curl http://localhost:8000/analytics/history?model=gpt
```

**Response:**
```json
{
  "gpt": [
    {
      "date": "2024-05-15",
      "return_pct": 3.2,
      "portfolio_value": 103200.0
    },
    {
      "date": "2024-05-16",
      "return_pct": 5.1,
      "portfolio_value": 105100.0
    }
    // ... more historical data
  ],
  "gemini": [
    {
      "date": "2024-05-15",
      "return_pct": 2.1,
      "portfolio_value": 102100.0
    }
    // ... more data
  ]
  // ... other models
}
```

**Query Parameters:**
- `model` (optional): Single model name
- `start_date` (optional): Filter from date (YYYY-MM-DD)
- `end_date` (optional): Filter to date (YYYY-MM-DD)

**Status Codes:**
- `200 OK` — Success
- `400 Bad Request` — Invalid date format

---

## ⚙️ Admin Endpoints

### POST /simulate-and-save
Trigger a new simulation run and save results to database.

**Request:**
```bash
curl -X POST http://localhost:8000/simulate-and-save
```

**Response:**
```json
{
  "message": "Simulation completed and saved to database",
  "timestamp": "2024-05-23T14:30:45",
  "models_simulated": ["gpt", "gemini", "mistral", "deepseek"],
  "portfolios_created": 4,
  "total_candidates": 200
}
```

**Status Codes:**
- `200 OK` — Simulation completed successfully
- `500 Internal Server Error` — Simulation failed

**Notes:**
- This endpoint may take 10-30 seconds to complete
- Requires AI Credits API key to be configured
- Calls the configured AI models for portfolio recommendations

### POST /update-valuations
Update current valuations for all stocks.

**Request:**
```bash
curl -X POST http://localhost:8000/update-valuations
```

**Response:**
```json
{
  "message": "Valuations updated successfully",
  "timestamp": "2024-05-23T14:31:20",
  "stocks_updated": 200,
  "market_open": true
}
```

**Status Codes:**
- `200 OK` — Valuations updated
- `500 Internal Server Error` — Update failed

**Notes:**
- Checks if market is open before updating
- Uses configured market data APIs
- Updates prices, RSI, volatility, etc.

---

## 🔐 Request/Response Format

### Headers
```
Content-Type: application/json
Accept: application/json
```

### Error Responses

**400 Bad Request:**
```json
{
  "detail": "Invalid date format. Use YYYY-MM-DD"
}
```

**404 Not Found:**
```json
{
  "detail": "Portfolio not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Database connection failed"
}
```

---

## 📐 Data Models

### Candidate
```typescript
{
  ticker: string              // Stock ticker (e.g., "HDFCBANK.NS")
  current_price: float        // Current market price
  rsi: float                  // RSI indicator (0-100)
  volatility: float           // Stock volatility (%)
  volume_ratio: float         // Volume ratio vs average
  one_month_return: float     // 1-month return (%)
  sector: string              // Stock sector
  trend_score: float          // Custom trend score (0-100)
  topsis_score: float         // TOPSIS ranking score (0-1)
}
```

### Holding
```typescript
{
  ticker: string              // Stock ticker
  quantity: int               // Number of shares
  entry_price: float          // Purchase price
  invested_amount: float      // Total invested (quantity × price)
  allocation_percent: float   // % of portfolio
  confidence: float           // Model confidence (0-1)
  reasoning: string           // Why this was selected
  sector: string              // Stock sector
}
```

### Portfolio
```typescript
{
  id: int
  date: string                // YYYY-MM-DD
  model: string               // "gpt", "gemini", "mistral", "deepseek"
  starting_capital: float
  remaining_cash: float
  strategy_summary: string
  risk_level: string          // "conservative", "moderate", "aggressive"
  current_return: float       // Return percentage
  portfolio_value: float      // Total value
  holdings: Holding[]
}
```

### LeaderboardEntry
```typescript
{
  model: string
  average_return_percent: float
  best_return_percent: float
  worst_return_percent: float
  days_active: int
  win_rate: float             // 0-1
  latest_return: float
  total_portfolios: int
}
```

---

## 🧪 Testing with curl

### Test health
```bash
curl -v http://localhost:8000/health
```

### Get leaderboard with pretty printing
```bash
curl http://localhost:8000/leaderboard | jq
```

### Filter portfolios by date
```bash
curl "http://localhost:8000/portfolios?date=2024-05-23" | jq '.[] | .model'
```

### Get only TOPSIS scores above 0.8
```bash
curl http://localhost:8000/market/candidates | jq '.[] | select(.topsis_score > 0.8) | .ticker'
```

### Run simulation and capture response
```bash
curl -X POST http://localhost:8000/simulate-and-save | jq
```

### Get performance history for one model
```bash
curl http://localhost:8000/analytics/history | jq '.gpt'
```

---

## 🔄 Common Workflows

### Workflow 1: Get Today's Simulation Data
```bash
# Get all data for today
curl http://localhost:8000/simulation/today | jq

# Extract just the models' performance
curl http://localhost:8000/simulation/today | jq '.model_results[] | {model, risk_level, current_return}'

# Get portfolio breakdown for GPT
curl http://localhost:8000/simulation/today | jq '.model_results[] | select(.model=="gpt") | .portfolio[] | {ticker, allocation_percent}'
```

### Workflow 2: Monitor Leaderboard
```bash
# Get sorted by average return
curl 'http://localhost:8000/leaderboard?sort_by=average_return&order=desc' | jq '.[] | {model, average_return_percent, win_rate}'

# Get sorted by win rate
curl 'http://localhost:8000/leaderboard?sort_by=win_rate&order=desc' | jq '.[] | {model, win_rate}'
```

### Workflow 3: Historical Analysis
```bash
# Get performance over time
curl http://localhost:8000/analytics/history | jq

# Calculate average return for each model
curl http://localhost:8000/analytics/history | jq 'to_entries[] | {model: .key, avg_return: (.value | map(.return_pct) | add / length)}'
```

### Workflow 4: Market Analysis
```bash
# Get top candidates by TOPSIS score
curl http://localhost:8000/market/candidates | jq 'sort_by(.topsis_score) | reverse | .[0:5] | .[] | {ticker, topsis_score, sector}'

# Get candidates by sector
curl http://localhost:8000/market/candidates | jq 'group_by(.sector) | map({sector: .[0].sector, count: length})'
```

---

## 🚨 Rate Limiting

Currently, there is **no rate limiting** configured. For production deployment, consider:

1. Implementing rate limiting per IP
2. Adding authentication tokens
3. Setting request quotas per user

---

## 📞 Debugging

### Enable verbose logging
Check backend logs for detailed request/response information.

### API Documentation
Visit: `http://localhost:8000/docs` for interactive Swagger UI

### Alternative Documentation
Visit: `http://localhost:8000/redoc` for ReDoc documentation

---

**Last Updated:** May 23, 2026  
**API Version:** 2.0.0
