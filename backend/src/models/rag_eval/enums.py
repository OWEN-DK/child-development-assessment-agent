import enum


class TestDomain(str, enum.Enum):
    GROSS_MOTOR = "gross_motor"
    FINE_MOTOR = "fine_motor"
    LANGUAGE = "language"
    COGNITIVE = "cognitive"
    SOCIAL_EMOTIONAL = "social_emotional"
    SENSORY_INTEGRATION = "sensory_integration"


class TestCaseStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    IMPORTED = "imported"


class TestRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestSourceType(str, enum.Enum):
    MANUAL = "manual"
    JSON_IMPORT = "json_import"
    BOOK_GENERATED = "book_generated"
    MIXED = "mixed"


class DifficultyLevel(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    ARCHIVED = "archived"
