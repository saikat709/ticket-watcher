from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import Ticket


class TicketSource(ABC):
    def __init__(self, source_id: str):
        self.source_id = source_id

    @abstractmethod
    def fetch_new_tickets(self, last_seen_id: int) -> List[Ticket]:
        """Fetch all new tickets with ID greater than last_seen_id.
        Must return tickets sorted by ticket ID in ascending order.
        """
        pass

    @abstractmethod
    def fetch_ticket(self, ticket_id: int) -> Optional[Ticket]:
        """Fetch full details for a single ticket by ticket_id."""
        pass

    @abstractmethod
    def detect_changes(self, old_ticket: Ticket, new_ticket: Ticket) -> List[str]:
        """Compare old and new ticket snapshots and return list of change descriptions."""
        pass

    @abstractmethod
    def is_completed(self, ticket: Ticket) -> bool:
        """Return True if ticket associated work is finished (e.g. PR merged or ticket resolved)."""
        pass
