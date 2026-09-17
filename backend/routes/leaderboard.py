from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Portfolio, DailyValuation

router = APIRouter()


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    """
    Returns ranked performance stats for all models.
    Compatible with the existing frontend LeaderboardEntry interface.
    """
    models = [row[0] for row in db.query(Portfolio.model).distinct().all()]
    result = []

    for model_name in models:
        valuations = (
            db.query(DailyValuation)
            .join(Portfolio)
            .filter(Portfolio.model == model_name)
            .order_by(DailyValuation.date.asc())
            .all()
        )
        portfolio_count = (
            db.query(func.count(Portfolio.id))
            .filter(Portfolio.model == model_name)
            .scalar()
        )

        if not valuations:
            result.append({
                "model":                   model_name,
                "average_return_percent":  0.0,
                "best_return_percent":     0.0,
                "worst_return_percent":    0.0,
                "days_active":             portfolio_count,
                "win_rate":                0.0,
                "latest_return":           0.0,
                "total_portfolios":        portfolio_count,
            })
            continue

        returns      = [v.return_pct for v in valuations]
        avg_return   = sum(returns) / len(returns)
        best         = max(returns)
        worst        = min(returns)
        win_rate     = (sum(1 for r in returns if r > 0) / len(returns)) * 100
        latest_ret   = valuations[-1].return_pct

        result.append({
            "model":                   model_name,
            "average_return_percent":  round(avg_return,  4),
            "best_return_percent":     round(best,        4),
            "worst_return_percent":    round(worst,       4),
            "days_active":             len(valuations),
            "win_rate":                round(win_rate,    1),
            "latest_return":           round(latest_ret,  4),
            "total_portfolios":        portfolio_count,
        })

    result.sort(key=lambda x: x["average_return_percent"], reverse=True)
    return result