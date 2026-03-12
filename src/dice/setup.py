from setuptools import setup

package_name = 'dice'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='DiceMaster Team',
    maintainer_email='dev@dicemaster.io',
    description='DiceMaster student SDK — ROS2 wrapper',
    license='MIT',
)
