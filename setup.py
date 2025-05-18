from setuptools import setup, Extension
import os

if os.name == "nt":
    extra_compile_args = ["/std:c++latest", "/O2", "/Oi", "/Ob2"]
else:
    extra_compile_args = ["-std=c++20", "-O3"]

ext_modules = [
    Extension(
        "clovers_utils.linecard.linecard_parsing",
        sources=["src/linecard_parsing.cpp"],
        extra_compile_args=extra_compile_args,
    ),
]
setup(ext_modules=ext_modules)
