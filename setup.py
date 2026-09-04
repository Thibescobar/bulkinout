"""Build hooks for distribution assets that remain editable at the repository root."""

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as setuptools_build_py


class build_py(setuptools_build_py):
    """Copy the canonical reference into the installed Bulkinout package."""

    def run(self) -> None:
        super().run()
        repository_root = Path(__file__).parent
        source_root = repository_root / "reference"
        target_root = Path(self.build_lib) / "bulkinout" / "reference_data"
        target_scenarios = target_root / "scenarios"
        self.mkpath(str(target_scenarios))
        self.copy_file(str(source_root / "catalog.json"), str(target_root / "catalog.json"))
        for source in sorted((source_root / "scenarios").glob("*.yaml")):
            self.copy_file(str(source), str(target_scenarios / source.name))


setup(cmdclass={"build_py": build_py})
