from typing import Dict, Any, List
import statistics
from collections import Counter
from src.model.schemas import AgentState, CondensedContext, HistoryRecord
from src.config.rules import rules
from src.core.nodes.base import BaseNode
from src.utils.logger import logger


class PreprocessingNode(BaseNode):
    """预处理与上下文压缩"""

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        logger.info("Executing Preprocessing Node...")

        history = state.history_context or []

        if not history:
            logger.info(
                "No history context provided, returning default condensed context."
            )
            return {
                "condensed_context": CondensedContext(
                    weekly_avg_duration=0.0,
                    frequency_consistency=0.0,
                    intensity_trend="stable",
                    diversity_score=0.0,
                    recent_feedbacks=[],
                )
            }

        # 1. Calculate Weekly Average Duration
        total_duration = 0
        dates = set()
        for record in history:
            dates.add(record.date)
            for activity in record.activities:
                total_duration += activity.duration_minutes

        # Estimate weeks based on date range or unique dates (simplified here)
        # Assuming history covers the relevant period. If dates span 14 days, that's 2 weeks.
        # For simplicity, let's just average per record if dates are sparse,
        # or treat the whole history as a "recent window" if it's short.
        # Let's use a simple heuristic: Total Duration / (Unique Dates / 7)
        num_days = len(dates)
        num_weeks = max(1, num_days / 7.0)
        weekly_avg_duration = round(total_duration / num_weeks, 1)

        # 2. Calculate Frequency Consistency (1.0 = very consistent, 0.0 = inconsistent)
        # We can look at the variance of duration per day
        daily_durations = []
        for record in history:
            day_total = sum(a.duration_minutes for a in record.activities)
            daily_durations.append(day_total)

        if len(daily_durations) > 1:
            mean_duration = statistics.mean(daily_durations)
            stdev_duration = statistics.stdev(daily_durations)
            # Coefficient of variation (CV) = stdev / mean
            # Consistency = 1 / (1 + CV) to map it to [0, 1] range approximately
            cv = stdev_duration / mean_duration if mean_duration > 0 else 0
            frequency_consistency = round(1.0 / (1.0 + cv), 2)
        else:
            frequency_consistency = 1.0  # Only one data point is "consistent"

        # 3. Determine Intensity Trend
        # Map intensity to numeric values
        intensity_map = {"low": 1, "medium": 2, "high": 3}
        intensity_scores = []
        for record in history:
            # Average intensity for the day
            day_intensities = [
                intensity_map.get(a.intensity, 1)
                for a in record.activities
                if a.intensity
            ]
            if day_intensities:
                intensity_scores.append(statistics.mean(day_intensities))
            else:
                intensity_scores.append(1)  # Default to low

        intensity_trend = "stable"
        if len(intensity_scores) >= rules.preprocessing.min_records_for_trend:
            # Simple comparison of first half vs second half
            mid = len(intensity_scores) // 2
            first_half = statistics.mean(intensity_scores[:mid])
            second_half = statistics.mean(intensity_scores[mid:])
            if second_half > first_half + rules.preprocessing.trend_threshold:
                intensity_trend = "rising"
            elif second_half < first_half - rules.preprocessing.trend_threshold:
                intensity_trend = "falling"

        # 4. Diversity Score
        activity_names = []
        for record in history:
            for activity in record.activities:
                activity_names.append(activity.name)

        unique_activities = set(activity_names)
        total_activities = len(activity_names)
        diversity_score = (
            round(len(unique_activities) / total_activities, 2)
            if total_activities > 0
            else 0.0
        )

        # 5. Extract Recent Feedbacks
        recent_feedbacks = []
        # Get feedbacks from the last records
        sorted_history = sorted(history, key=lambda x: x.date, reverse=True)
        for record in sorted_history[:rules.preprocessing.recent_feedback_limit]:
            for activity in record.activities:
                if activity.feedback:
                    recent_feedbacks.append(
                        f"[{record.date}] {activity.name}: {activity.feedback}"
                    )
            if record.notes:
                recent_feedbacks.append(f"[{record.date}] Note: {record.notes}")

        condensed = CondensedContext(
            weekly_avg_duration=weekly_avg_duration,
            frequency_consistency=frequency_consistency,
            intensity_trend=intensity_trend,
            diversity_score=diversity_score,
            recent_feedbacks=recent_feedbacks[:5],  # Limit to top 5
        )

        logger.info(f"Context condensed: {condensed.model_dump()}")

        return {"condensed_context": condensed}
