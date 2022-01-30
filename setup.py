import setuptools

with open("README.rst", "r") as fh:
	long_description = fh.read()

setuptools.setup(
	name="subpop",
	version="2.0.0",
	author="Daniel Robbins",
	author_email="drobbins@funtoo.org",
	description="A gentle evolution of the POP paradigm.",
	long_description=long_description,
	long_description_content_type="text/x-rst",
	url="https://code.funtoo.org/bitbucket/users/drobbins/repos/subpop/browse",
	classifiers=[
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: Apache Software License",
		"Operating System :: POSIX :: Linux",
	],
	python_requires=">=3.7",
	install_requires=["PyYAML"],
	tests_require=["pytest-forked"],
	packages=setuptools.find_packages(),
	package_data={},
)
