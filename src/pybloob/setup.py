from setuptools import setup, find_packages

setup(
   name='pybloob',
   version='0.1',
   description='Utils for the Blueberry voice assistant',
   author='Issac Dowling',
   author_email='contact@issacdowling.com',
   packages=find_packages(),
   install_requires=['paho-mqtt'], #external packages as dependencies
)