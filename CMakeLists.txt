cmake_minimum_required(VERSION 3.8)
project(dicemaster_central)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)

# Generate custom messages
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RawIMU.msg"
  "msg/MotionDetection.msg"
  "msg/IMUCalibration.msg"
  "msg/NotificationRequest.msg"
  "msg/NotificationResponse.msg"
  "msg/DatasetInfo.msg"
  DEPENDENCIES geometry_msgs sensor_msgs std_msgs
)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install Python executables
install(PROGRAMS
  DiceMaster_Central/hw/imu.py
  DiceMaster_Central/hw/chassis.py
  DiceMaster_Central/hw/screen.py
  DiceMaster_Central/hw/usb_connector_checker.py
  DiceMaster_Central/managers/dataset_loader.py
  DiceMaster_Central/managers/notifications.py
  DiceMaster_Central/managers/strategy_manager.py
  scripts/dataset_manager.py
  scripts/dataset_consumer_example.py
  tests/test_imu.py
  tests/test_imu_data_recording.py
  tests/test_dataset_loader.py
  tests/test_chassis.py
  tests/test_notifications.py
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch files
install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}/
)

# Install test files
install(DIRECTORY
  tests
  DESTINATION share/${PROJECT_NAME}/
)

# Install documentation
install(DIRECTORY
  docs
  DESTINATION share/${PROJECT_NAME}/
)

# Install message files
install(DIRECTORY
  msg
  DESTINATION share/${PROJECT_NAME}/
)

# Install resource files
install(DIRECTORY
  resource
  DESTINATION share/${PROJECT_NAME}/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # Add Python test dependencies
  find_package(ament_cmake_pytest REQUIRED)
  
  # Register tests
  ament_add_pytest_test(test_imu tests/test_imu.py)
  ament_add_pytest_test(test_dataset_loader tests/test_dataset_loader.py)
  ament_add_pytest_test(test_notifications tests/test_notifications.py)
  ament_add_pytest_test(test_chassis tests/test_chassis.py)
  
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
