"""Custom exception hierarchy for Server Forge."""


class ForgeError(Exception):
    """Base exception for all forge errors."""


class PrerequisiteError(ForgeError):
    """A required prerequisite is missing or wrong version."""


class BuildError(ForgeError):
    """CMake configure or compile failure."""


class DatabaseError(ForgeError):
    """MySQL connection or import failure."""


class ConfigError(ForgeError):
    """Configuration file read/write failure."""


class ProfileError(ForgeError):
    """Server profile load/save failure."""


class ModuleError(ForgeError):
    """Module enable/disable failure."""


class PortError(ForgeError):
    """Port availability or firewall rule failure."""


class SourceError(ForgeError):
    """Git clone/update failure."""
