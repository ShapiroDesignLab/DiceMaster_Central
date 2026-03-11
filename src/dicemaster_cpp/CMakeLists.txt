cmake_minimum_required(VERSION 3.8)
project(dicemaster_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -O2)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(dicemaster_central_msgs REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(yaml-cpp REQUIRED)

include_directories(include ${EIGEN3_INCLUDE_DIRS})

# IMU hardware node
add_executable(imu_hardware_cpp src/imu_hardware_node.cpp)
ament_target_dependencies(imu_hardware_cpp rclcpp sensor_msgs std_msgs)

# Chassis node
add_executable(chassis_cpp src/dice_orientation.cpp src/chassis_node.cpp)
target_link_libraries(chassis_cpp yaml-cpp)
ament_target_dependencies(chassis_cpp rclcpp sensor_msgs geometry_msgs std_msgs dicemaster_central_msgs ament_index_cpp Eigen3)

install(TARGETS imu_hardware_cpp chassis_cpp
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch)

ament_package()
