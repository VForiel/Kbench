from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

for line in requirements:
    if line.startswith("#"):
        requirements.remove(line)
    if line == "":
        requirements.remove(line)

setup(
    name="Kbench",
    version="0.0.1", # Breaking.Feature.Fix
    packages=find_packages(),
    install_requires=requirements,
    author="Photonics",
    description="High level control interface for all the kernel bench instruments.",
    url="https://github.com/VForiel/Kbench",
)
