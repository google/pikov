# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from os import path

from setuptools import setup, find_packages


here = path.abspath(path.dirname(__file__))
readme = open(path.join(here, 'README.rst'), encoding='utf-8').read()

setup(
    name='pikov',
    description='Pikov (PIxel art marKOV chain) animation tool',
    version='0.0.1.dev1',
    author='Tim Swast',
    author_email='swast@google.com',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=[
        'Pillow >= 5.2.0, < 6.0dev',
    ],
    license='Apache 2.0',
    long_description=readme,
    url='https://github.com/tswast/pikov',
    keywords='pixelart animation',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points={
        'console_scripts': [
            'pikov=pikov.pikov:main',
        ],
    },
)
