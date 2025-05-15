import os
from setuptools import find_packages, setup

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name="django-auditlog-bridge",
    version="1.1.3",
    packages=find_packages(),
    python_requires=">=3.10",
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "Django>=3.2",
        "djangorestframework>=3.14.0",
        "django-auditlog>=3.0.0",
    ],
    extras_require={
        "dev": [
            "coverage",
            "black",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Utilities",
    ],
)
