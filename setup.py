"""Setup script for AIOps Agent"""

from setuptools import setup, find_packages

setup(
    name="aiops-agent",
    version="0.1.0",
    author="SADA Systems",
    description="AI-powered Operations Agent for Google Cloud Platform",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "google-generativeai>=0.3.0",
        "google-cloud-aiplatform>=1.38.0",
        "google-cloud-monitoring>=2.15.0",
        "google-cloud-logging>=3.5.0",
        "pydantic>=2.5.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
    ],
)
