import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="hyperpeer", # Replace with your own username
    version="0.0.1",
    author="Jose F. Saenz-Cogollo",
    author_email="jsaenz@crs4.it",
    description="Python module for implementing media servers or backend peers in applications based on Hyperpeer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="http://156.148.14.162/icare2/hyperpeer-py",
    packages=setuptools.find_packages(),
    install_requires=['aiortc==0.9.22', 'websockets'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL-3.0 License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)