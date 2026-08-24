from setuptools import setup, find_packages

setup(
    name="horizon_client",
    version="0.1.0",
    description="Horizon SaaS client app: enforces plan limits and feature gates inside tenant sites",
    author="Horizon Smart Systems",
    author_email="support@horizonerp.cloud",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[],
)
