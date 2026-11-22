"""Small domain objects corresponding to the Phase 5 class model."""
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

ROLES = ('requester', 'representative', 'custodian', 'maintenance', 'workflow_admin',
         'procurement', 'finance', 'sustainability', 'system_admin')
CATEGORIES = ('Furniture', 'IT', 'Books', 'Laboratory', 'Office')
CONDITIONS = ('New', 'Good', 'Fair', 'Poor', 'Unsafe')


class RuleError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(ZoneInfo('Asia/Dubai'))


def stamp():
    return now().isoformat(timespec='seconds')


@dataclass(frozen=True)
class AssetUnit:
    id: int
    publication: str
    serviceability: str
    lifecycle: str

    def reserve(self):
        if (self.publication, self.serviceability, self.lifecycle) != ('Published', 'Serviceable', 'Active'):
            raise RuleError('This unit is not eligible for allocation.', 409)


@dataclass(frozen=True)
class ResourceRequest:
    id: int
    status: str

    def require(self, *states):
        if self.status not in states:
            raise RuleError('The request has changed or this transition is not allowed.', 409)


@dataclass(frozen=True)
class RequestSpecification:
    purpose: str
    quantity: int
    needed_date: str

    def validate(self):
        if not self.purpose.strip() or len(self.purpose) > 1000:
            raise RuleError('Enter a purpose of 1 to 1000 characters.')
        if not 1 <= self.quantity <= 100:
            raise RuleError('Quantity must be between 1 and 100.')
        try:
            date = datetime.strptime(self.needed_date, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            raise RuleError('Enter a valid needed date.') from None
        if date < now().date():
            raise RuleError('The needed date cannot be in the past.')


@dataclass(frozen=True)
class Transfer:
    status: str

    def collect(self):
        if self.status != 'Approved':
            raise RuleError('Only an approved transfer may be collected.', 409)

    def acknowledge(self):
        if self.status != 'Awaiting receipt':
            raise RuleError('Collection must be recorded before receipt.', 409)


@dataclass(frozen=True)
class MaintenanceJob:
    status: str

    def next_state(self, target):
        moves = {'Reported': ['Inspection requested'], 'Inspection requested': ['Inspected'],
                 'Inspected': ['Repair approved'], 'Repair approved': ['In progress'],
                 'In progress': ['Completed', 'Inspected'], 'Completed': ['Closed']}
        if target not in moves.get(self.status, []):
            raise RuleError('Invalid maintenance transition.', 409)


@dataclass(frozen=True)
class MatchRecommendation:
    unit_id: int
    score: float
    reason: str

    def explain(self):
        return f'Unit {self.unit_id}: {self.score:.0f}/100. {self.reason}'
