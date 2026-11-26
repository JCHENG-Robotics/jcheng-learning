"""jcheng-learning: offline datasets, validation and policy artifacts.

The package is ROS-free and hardware-free. It never opens a device, never
joins a DDS domain and never commands motion.
"""

from .version import __version__

__all__ = ["__version__"]
