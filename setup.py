from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'dicemaster_central'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
        ('share/' + package_name + '/resource', glob('resource/*')),
        ('share/' + package_name + '/msg', glob('msg/*.msg')),
    ],
    install_requires=[
        'setuptools',
        'matplotlib',
        'numpy',
        'Pillow',
        'RPi.GPIO; platform_machine=="armv7l"',
        'spidev; platform_machine=="armv7l"'
    ],
    zip_safe=True,
    maintainer='DiceMaster Team',
    maintainer_email='dicemaster@umich.edu',
    description='DiceMaster Central Control Package',
    license='MIT',
    tests_require=[
        'pytest',
        'matplotlib',
        'numpy'
    ],
    entry_points={
        'console_scripts': [
            'screen_node = scripts.screen_node:main',
            'imu_node = DiceMaster_Central.hw.imu:main',
            'chassis_node = DiceMaster_Central.hw.chassis:main',
            'remote_logger = DiceMaster_Central.remote_logger:main',
            'dataset_loader_service = DiceMaster_Central.managers.dataset_loader:main',
            'usb_connector_checker = DiceMaster_Central.hw.usb_connector_checker:main',
            'notification_manager = DiceMaster_Central.managers.notifications:main',
            'dataset_manager = scripts.dataset_manager:main',
            'test_dataset_loader = scripts.test_dataset_loader:main',
            'test_imu = scripts.test_imu:main',
            'test_chassis = scripts.test_chassis:main',
            'imu_example = scripts.imu_example:main',
        ],
    },
)
