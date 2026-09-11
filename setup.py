from pathlib import Path

from setuptools import find_packages, setup

package_name = "tui_img_view"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("tests", "tests.*")),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=[
        "numpy>=1.21",
        "pillow>=9",
        "textual>=0.86",
        "rich>=13",
    ],
    extras_require={
        "bag": ["mcap>=1.0", "mcap-ros2-support>=0.5"],
        "docs": ["mkdocs>=1.6,<2", "mkdocs-material>=9.5,<10", "mkdocstrings[python]>=0.24"],
        "dev": [
            "pytest>=7",
            "pytest-asyncio>=0.21",
            "ruff>=0.4",
            "mcap>=1.0",
            "mcap-ros2-support>=0.5",
        ],
    },
    python_requires=">=3.10",
    zip_safe=True,
    maintainer="Erwin Lejeune",
    maintainer_email="erwin.lejeune15@gmail.com",
    description=(
        "Terminal UI to view image topics and bounding boxes, "
        "with pluggable transports (ROS 2 first)."
    ),
    license="MIT",
    license_files=("LICENSE",),
    url="https://github.com/guilyx/tui_img_view_ros2",
    project_urls={
        "Documentation": "https://guilyx.github.io/tui_img_view_ros2/",
        "Source": "https://github.com/guilyx/tui_img_view_ros2",
        "Issues": "https://github.com/guilyx/tui_img_view_ros2/issues",
        "Changelog": "https://github.com/guilyx/tui_img_view_ros2/blob/main/CHANGELOG.md",
    },
    long_description=Path(__file__).with_name("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Image Processing",
        "Topic :: Terminals",
    ],
    keywords="ros2 tui terminal image viewer bounding-box textual",
    entry_points={
        "console_scripts": [
            "tui-img-view = tui_img_view.cli:main",
            "viewer = tui_img_view.cli:main",
        ],
    },
)
