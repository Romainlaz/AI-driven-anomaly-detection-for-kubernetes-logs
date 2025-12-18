from setuptools import setup, find_packages

setup(
    name="anomaly-detector",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.5.0",
        "prometheus-client>=0.19.0",
        "pandas>=2.1.0",
        "numpy>=1.26.0",
        "scikit-learn>=1.4.0",
        "scipy>=1.12.0",
        "drain3>=0.9.11",
        "click>=8.1.7",
    ],
    entry_points={
        'console_scripts': [
            'anomaly-detector=src.cli:cli',
            'prepare-data=scripts.prepare_data:cli',
        ],
    },
)
