from setuptools import setup, find_packages


setup(
    name="Scout",
    version="0.1.0",
    description="Spline builder",
    url="https://github.com/TheBB/Scout",
    maintainer="Eivind Fonn",
    maintainer_email="evfonn@gmail.com",
    license="GNU public license v3",
    packages=find_packages('scout'),
    install_requires=[
        'mayavi',
        'splipy',
    ],
    entry_points={
        'console_scripts': [
            'scout=scout.__main__:main',
        ],
    },
)
