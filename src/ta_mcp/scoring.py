from decimal import Decimal

from ta_mcp.domain import (
    CriterionRole,
    CriterionStatus,
    ReviewBundle,
    ReviewSummary,
    ScoringMode,
)


class ScoreCalculator:
    """Pure exact-decimal recommendation calculator."""

    @staticmethod
    def calculate(bundle: ReviewBundle) -> ReviewSummary:
        """Calculate earned points, explicit deductions, and unresolved bounds.

        Args:
            bundle: Validated review entities and source-derived allocation.

        Returns:
            Exact score components and a null recommendation until resolved.
        """
        criteria = {criterion.id: criterion for criterion in bundle.criteria}
        if bundle.rubric.scoring_mode == ScoringMode.UNSCORED:
            if any(item.awarded_points is not None for item in bundle.assessments):
                raise ValueError("UNSCORED assessments must have null points")
            if bundle.penalty_applications:
                raise ValueError("UNSCORED reviews cannot apply numeric penalties")
            return ReviewSummary()
        base_points = Decimal(0)
        bonus_points = Decimal(0)
        unresolved = []
        unresolved_maximum = Decimal(0)
        for assessment in bundle.assessments:
            criterion = criteria[assessment.criterion_id]
            maximum = criterion.max_points
            awarded = assessment.awarded_points
            if criterion.role == CriterionRole.ADVISORY:
                if awarded is not None:
                    raise ValueError("ADVISORY assessments must have null points")
                continue
            if maximum is None or maximum <= 0:
                raise ValueError("Point-bearing criteria need positive source points")
            if assessment.status == CriterionStatus.NOT_VERIFIABLE:
                if awarded is not None:
                    raise ValueError("Unverified points must be null")
                unresolved.append(criterion.id)
                unresolved_maximum += maximum
                continue
            if awarded is None or awarded > maximum:
                raise ValueError("Award is missing or exceeds criterion maximum")
            if assessment.status == CriterionStatus.PASS and awarded != maximum:
                raise ValueError("PASS must award the exact maximum")
            if assessment.status == CriterionStatus.FAIL and awarded != 0:
                raise ValueError("FAIL must award zero")
            if (
                assessment.status == CriterionStatus.PARTIAL
                and not 0 < awarded < maximum
            ):
                raise ValueError("PARTIAL must be strictly between zero and maximum")
            if criterion.role == CriterionRole.BONUS:
                bonus_points += awarded
            else:
                base_points += awarded
        penalty_points = sum(
            (item.applied_amount for item in bundle.penalty_applications), Decimal(0)
        )
        known_points = base_points + bonus_points
        minimum = max(Decimal(0), known_points - penalty_points)
        maximum = max(Decimal(0), known_points + unresolved_maximum - penalty_points)
        if bundle.rubric.grade_cap is not None:
            minimum = min(minimum, bundle.rubric.grade_cap)
            maximum = min(maximum, bundle.rubric.grade_cap)
        return ReviewSummary(
            known_points=known_points,
            base_points=base_points,
            bonus_points=bonus_points,
            penalty_points=penalty_points,
            unresolved_criterion_ids=unresolved,
            minimum_possible_score=minimum,
            maximum_possible_score=maximum,
            recommended_score=None if unresolved else minimum,
        )
