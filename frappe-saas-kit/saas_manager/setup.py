from setuptools import setup, find_packages

setup(
    name="saas_manager",
    version="0.1.0",
    description="Frappe Bench SaaS Control Plane - automated signup to activation",
    author="Horizon Smart Systems",
    author_email="contact@almoaser.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[],
)
