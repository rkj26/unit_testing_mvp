"""Class-free CLI entry point for Omar's detached coordinator.

The protocols package imports `omar_shared` to register its classes. Running
that module again with `python -m` would define the same classes a second time
under `__main__` and collide with the registry. Run this module instead.
"""

from .omar_shared import main


if __name__ == "__main__":
    main()
