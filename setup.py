#!/usr/bin/env python
import os

version = '0.2.1'

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(name='redisco',
      version=version,
      description='Python Containers and Simple Models for Redis',
      url='http://xwssole.github.com/redisco',
      download_url='',
      long_description=read('README.rst'),
      install_requires=read('requirements.txt').splitlines(),
      author='Tim Medina',
      author_email='iamteem@gmail.com',
      maintainer='Sebastien Requiem',
      maintainer_email='sebastien.requiem@gmail.com',
      keywords=['Redis', 'model', 'container'],
      license='MIT',
      packages=['redisco', 'redisco.models'],
      test_suite='tests.all_tests',
      classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python'],
    )

