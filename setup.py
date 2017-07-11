# coding=utf-8
"""Arlo Tools setup script."""
from setuptools import setup

temp_install_reqs = []
install_reqs = []
dependency_links = []

with open("requirements.txt", "r") as f:
    temp_install_reqs = list(map(str.strip, f.readlines()))

for req in temp_install_reqs:
    # This if should be expanded with all the other possibilities that can exist.  However, this
    # simple version works for this program.
    if req.startswith("https://"):
        dependency_links.append(req)
        install_reqs.append(req[req.find("egg=") + 4:].replace("-", "==", 1))
    else:
        install_reqs.append(req)


setup(
    name='arlo_tools',
    packages=['bin'],
    version='0.0.1',
    description='Collection of out-of-the-box utility scripts for interfacing with Arlo cameras.',
    author='Chad Dotson',
    author_email='chad@cdotson.com',
    url='https://github.com/chaddotson/arlo_tools',
    license='',
    include_package_data=True,
    install_requires=install_reqs,
    dependency_links=dependency_links,
    test_suite='tests',
    keywords=[
        'arlo',
        'netgear',
        'camera',
        'home automation',
        'python',
        ],
    classifiers=[],
    entry_points={
        'console_scripts': [
            'check_arlo_mode = bin.check_arlo_mode:main',
        ]
    },
)
