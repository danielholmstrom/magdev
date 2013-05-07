"""
~~~~~~
Magdev
~~~~~~

Read more in the source or on github
<https://github.com/danielholmstrom/magdev>.
"""

import os
import sys
from setuptools import find_packages, setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()

# Requirements for the package
install_requires = [
    'docopt',
    'jinja2',
]

# Requirement for running tests
test_requires = install_requires

extra = {}
if sys.version_info >= (3,):
    extra['use_2to3'] = True

setup(name='magdev',
      version='0.1.0b1',
      description="Magento development tool",
      long_description=README,
      url='http://github.com/danielholmstrom/magdev/',
      license='MIT',
      author='Daniel Holmstrom',
      author_email='holmstrom.daniel@gmail.com',
      platforms='any',
      classifiers=['Development Status :: 4 - Beta',
                   'License :: OSI Approved :: MIT License',
                   'Environment :: Web Environment',
                   'Intended Audience :: Developers',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Topic :: Software Development :: '],
      py_modules=['magdev'],
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      tests_require=test_requires,
      test_suite='tests',
      scripts=['scripts/magdev'],
      **extra
      )
