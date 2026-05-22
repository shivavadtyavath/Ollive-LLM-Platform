from setuptools import setup, find_packages

setup(
    name="ollive-sdk",
    version="1.0.0",
    description="Lightweight LLM inference logging SDK",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "openai>=1.0.0",
        "httpx>=0.25.0",
    ],
)
