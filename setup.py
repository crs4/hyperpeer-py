import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="hyperpeer-py",
    version="0.2.0",
    author="Jose F. Saenz-Cogollo",
    author_email="jsaenz@crs4.it",
    description="Python module for implementing media servers or backend peers in applications based on Hyperpeer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/crs4/hyperpeer-py",
    packages=setuptools.find_packages(),
    install_requires=['aiortc==0.9.28', 'websockets', 'numpy==1.19.1'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL-3.0 License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X"
    ],
    python_requires='>=3.7',
)