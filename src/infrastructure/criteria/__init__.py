from src.domain.entities.compliance import ComplianceCriterion
from src.infrastructure.criteria.agile import CRITERIA as AGILE_CRITERIA
from src.infrastructure.criteria.architecture import CRITERIA as ARCHITECTURE_CRITERIA
from src.infrastructure.criteria.backend import CRITERIA as BACKEND_CRITERIA
from src.infrastructure.criteria.frontend import CRITERIA as FRONTEND_CRITERIA
from src.infrastructure.criteria.infra import CRITERIA as INFRA_CRITERIA
from src.infrastructure.criteria.qa import CRITERIA as QA_CRITERIA
from src.infrastructure.criteria.security import CRITERIA as SECURITY_CRITERIA
from src.infrastructure.criteria.structure import CRITERIA as STRUCTURE_CRITERIA

ALL_CRITERIA: list[ComplianceCriterion] = [
    *BACKEND_CRITERIA,
    *FRONTEND_CRITERIA,
    *AGILE_CRITERIA,
    *SECURITY_CRITERIA,
    *STRUCTURE_CRITERIA,
    *QA_CRITERIA,
    *INFRA_CRITERIA,
    *ARCHITECTURE_CRITERIA,
]
