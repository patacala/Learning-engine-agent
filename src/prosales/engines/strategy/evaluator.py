from prosales.core.enums import Sentiment


def evaluate_effectiveness(
    pre_sentiment: str,
    post_sentiment: str,
    goal_achieved: bool,
) -> float:
    """Evaluate strategy effectiveness (0-1)."""
    score = 0.5

    sentiment_order = ["very_negative", "negative", "neutral", "positive", "very_positive"]
    try:
        pre_idx = sentiment_order.index(pre_sentiment)
        post_idx = sentiment_order.index(post_sentiment)
        sentiment_delta = (post_idx - pre_idx) / len(sentiment_order)
        score += sentiment_delta * 0.3
    except ValueError:
        pass

    if goal_achieved:
        score += 0.3

    return max(0.0, min(1.0, score))
