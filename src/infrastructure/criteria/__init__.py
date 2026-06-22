from src.domain.entities.compliance import ComplianceCriterion
from src.infrastructure.criteria.agile import CRITERIA as AGILE_CRITERIA
from src.infrastructure.criteria.backend import CRITERIA as BACKEND_CRITERIA
from src.infrastructure.criteria.frontend import CRITERIA as FRONTEND_CRITERIA

ALL_CRITERIA: list[ComplianceCriterion] = [
    *BACKEND_CRITERIA,
    *FRONTEND_CRITERIA,
    *AGILE_CRITERIA,
]
