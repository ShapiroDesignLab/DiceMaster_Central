#include <cmath>
#include <deque>
#include <map>
#include <mutex>
#include <string>

#include <rclcpp/rclcpp.hpp>
#include <ament_index_cpp/get_package_share_directory.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <dicemaster_central_msgs/msg/chassis_orientation.hpp>
#include <dicemaster_central_msgs/msg/screen_pose.hpp>
#include <dicemaster_central_msgs/msg/motion_detection.hpp>

#include "dicemaster_cpp/dice_orientation.hpp"

class ChassisNode : public rclcpp::Node {
public:
    ChassisNode() : Node("dice_chassis_cpp") {
        declare_parameter("orientation_rate", 10.0);
        declare_parameter("config_path", std::string(""));
        declare_parameter("edge_detection_frames", 2);

        double rate = get_parameter("orientation_rate").as_double();
        std::string cfg_path = get_parameter("config_path").as_string();
        edge_frames_required_ = get_parameter("edge_detection_frames").as_int();

        // Find config
        if (cfg_path.empty()) {
            // Try ament share directory
            try {
                std::string share = ament_index_cpp::get_package_share_directory("dicemaster_central");
                cfg_path = share + "/resource/dice_geometry.yaml";
            } catch (...) {
                RCLCPP_ERROR(get_logger(), "Cannot find dice_geometry.yaml - provide config_path parameter");
                throw;
            }
        }

        dice_orient_ = std::make_unique<DiceOrientation>(cfg_path);
        RCLCPP_INFO(get_logger(), "DiceOrientation loaded from %s", cfg_path.c_str());

        // Publishers
        chassis_pub_ = create_publisher<dicemaster_central_msgs::msg::ChassisOrientation>(
            "/chassis/orientation", 10);
        motion_pub_ = create_publisher<dicemaster_central_msgs::msg::MotionDetection>(
            "/imu/motion", 10);
        for (int i = 1; i <= 6; ++i) {
            screen_pubs_[i] = create_publisher<dicemaster_central_msgs::msg::ScreenPose>(
                "/chassis/screen_" + std::to_string(i) + "_pose", 10);
        }

        // Subscriber
        imu_sub_ = create_subscription<sensor_msgs::msg::Imu>(
            "/imu/data", 10,
            std::bind(&ChassisNode::imu_callback, this, std::placeholders::_1));

        alt_imu_sub_ = create_subscription<sensor_msgs::msg::Imu>(
            "/data/imu", 10,
            std::bind(&ChassisNode::imu_callback, this, std::placeholders::_1));

        // Orientation timer
        orient_timer_ = create_wall_timer(
            std::chrono::microseconds(static_cast<int64_t>(1e6 / rate)),
            std::bind(&ChassisNode::orientation_callback, this));

        // Init state
        for (int i = 1; i <= 6; ++i) {
            edge_rotations_[i] = 0;
            edge_consecutive_[i] = 0;
            last_edge_[i] = "";
        }

        RCLCPP_INFO(get_logger(), "Chassis C++ node initialized (orientation_rate=%.0fHz)", rate);
    }

private:
    // DiceOrientation
    std::unique_ptr<DiceOrientation> dice_orient_;

    // IMU state
    std::mutex imu_mutex_;
    double imu_quat_[4] = {1.0, 0.0, 0.0, 0.0};  // x, y, z, w (default: pi around X)
    bool imu_connected_ = false;
    rclcpp::Time last_imu_time_;
    bool has_imu_ = false;

    // Motion detection
    std::deque<double> accel_mag_history_;
    std::deque<double> gyro_mag_history_;
    static constexpr size_t HISTORY_SIZE = 50;
    static constexpr double SHAKE_GYRO_THRESH = 5.0;
    static constexpr double SHAKE_VAR_THRESH = 5.0;

    // Edge detection state
    int edge_frames_required_;
    std::map<int, int> edge_rotations_;
    std::map<int, int> edge_consecutive_;
    std::map<int, std::string> last_edge_;

    // ROS interfaces
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr alt_imu_sub_;
    rclcpp::Publisher<dicemaster_central_msgs::msg::ChassisOrientation>::SharedPtr chassis_pub_;
    rclcpp::Publisher<dicemaster_central_msgs::msg::MotionDetection>::SharedPtr motion_pub_;
    std::map<int, rclcpp::Publisher<dicemaster_central_msgs::msg::ScreenPose>::SharedPtr> screen_pubs_;
    rclcpp::TimerBase::SharedPtr orient_timer_;

    void imu_callback(const sensor_msgs::msg::Imu::SharedPtr msg) {
        {
            std::lock_guard<std::mutex> lock(imu_mutex_);
            imu_quat_[0] = msg->orientation.x;
            imu_quat_[1] = msg->orientation.y;
            imu_quat_[2] = msg->orientation.z;
            imu_quat_[3] = msg->orientation.w;
            last_imu_time_ = now();
            if (!imu_connected_) {
                imu_connected_ = true;
                RCLCPP_INFO(get_logger(), "IMU data connected");
            }
            has_imu_ = true;
        }

        // Motion detection: accumulate magnitudes
        double ax = msg->linear_acceleration.x;
        double ay = msg->linear_acceleration.y;
        double az = msg->linear_acceleration.z;
        double gx = msg->angular_velocity.x;
        double gy = msg->angular_velocity.y;
        double gz = msg->angular_velocity.z;

        double accel_mag = std::sqrt(ax*ax + ay*ay + az*az);
        double gyro_mag = std::sqrt(gx*gx + gy*gy + gz*gz);

        accel_mag_history_.push_back(accel_mag);
        gyro_mag_history_.push_back(gyro_mag);
        if (accel_mag_history_.size() > HISTORY_SIZE) accel_mag_history_.pop_front();
        if (gyro_mag_history_.size() > HISTORY_SIZE) gyro_mag_history_.pop_front();
    }

    void orientation_callback() {
        double qx, qy, qz, qw;
        {
            std::lock_guard<std::mutex> lock(imu_mutex_);
            if (!has_imu_) return;
            auto elapsed = (now() - last_imu_time_).seconds();
            if (elapsed > 1.0) {
                if (imu_connected_) {
                    imu_connected_ = false;
                    RCLCPP_WARN(get_logger(), "IMU signal lost");
                }
                return;
            }
            qx = imu_quat_[0];
            qy = imu_quat_[1];
            qz = imu_quat_[2];
            qw = imu_quat_[3];
        }

        auto result = dice_orient_->compute(qx, qy, qz, qw);

        // Edge rotation for top screen
        int top_rotation = compute_edge_rotation(result.top_screen, result.top_edge_z);

        // Publish chassis orientation
        auto chassis_msg = dicemaster_central_msgs::msg::ChassisOrientation();
        chassis_msg.top_screen_id = result.top_screen;
        chassis_msg.bottom_screen_id = result.bottom_screen;
        chassis_msg.stamp = now();
        chassis_pub_->publish(chassis_msg);

        // Publish screen poses
        auto stamp = now();
        for (auto& [sid, up_align] : result.up_alignments) {
            auto screen_msg = dicemaster_central_msgs::msg::ScreenPose();
            screen_msg.screen_id = sid;
            screen_msg.rotation = (sid == result.top_screen) ? top_rotation : edge_rotations_[sid];
            screen_msg.up_alignment = static_cast<float>(up_align);
            screen_msg.is_facing_up = (sid == result.top_screen && up_align > 0.7);
            screen_msg.stamp = stamp;
            if (screen_pubs_.count(sid)) {
                screen_pubs_[sid]->publish(screen_msg);
            }
        }

        // Publish motion
        auto motion_msg = dicemaster_central_msgs::msg::MotionDetection();
        motion_msg.header.stamp = stamp;
        motion_msg.shaking = detect_shaking();
        double shake = get_shake_intensity();
        motion_msg.shake_intensity = shake;
        motion_msg.stillness_factor = std::max(0.0, 1.0 - shake);
        motion_pub_->publish(motion_msg);
    }

    int compute_edge_rotation(int screen_id, const std::map<std::string, double>& top_edge_z) {
        // Find lowest edge
        std::string lowest_edge;
        double min_z = std::numeric_limits<double>::infinity();
        for (auto& [name, z] : top_edge_z) {
            if (z < min_z) {
                min_z = z;
                lowest_edge = name;
            }
        }

        // Debounce
        if (last_edge_[screen_id] == lowest_edge) {
            edge_consecutive_[screen_id]++;
        } else {
            edge_consecutive_[screen_id] = 1;
            last_edge_[screen_id] = lowest_edge;
        }

        if (edge_consecutive_[screen_id] >= edge_frames_required_) {
            static const std::map<std::string, int> edge_to_rot = {
                {"bottom", 0}, {"right", 1}, {"top", 2}, {"left", 3}
            };
            auto it = edge_to_rot.find(lowest_edge);
            if (it != edge_to_rot.end()) {
                edge_rotations_[screen_id] = it->second;
            }
        }

        return edge_rotations_[screen_id];
    }

    bool detect_shaking() const {
        if (accel_mag_history_.size() < 20) return false;
        // Use last 20 samples
        double sum_a = 0, sum_a2 = 0, sum_g = 0;
        size_t n = 20;
        auto ait = accel_mag_history_.end() - n;
        auto git = gyro_mag_history_.end() - std::min(n, gyro_mag_history_.size());
        for (size_t i = 0; i < n; ++i) {
            double a = *(ait + i);
            sum_a += a;
            sum_a2 += a * a;
        }
        size_t gn = std::min(n, gyro_mag_history_.size());
        for (size_t i = 0; i < gn; ++i) {
            sum_g += *(git + i);
        }
        double mean_a = sum_a / n;
        double var_a = sum_a2 / n - mean_a * mean_a;
        double std_a = std::sqrt(std::max(0.0, var_a));
        double mean_g = (gn > 0) ? sum_g / gn : 0.0;
        return std_a > SHAKE_VAR_THRESH || mean_g > SHAKE_GYRO_THRESH;
    }

    double get_shake_intensity() const {
        if (accel_mag_history_.size() < 10) return 0.0;
        double sum_a = 0, sum_a2 = 0, sum_g = 0;
        size_t n = 10;
        auto ait = accel_mag_history_.end() - n;
        for (size_t i = 0; i < n; ++i) {
            double a = *(ait + i);
            sum_a += a;
            sum_a2 += a * a;
        }
        size_t gn = std::min(n, gyro_mag_history_.size());
        auto git = gyro_mag_history_.end() - gn;
        for (size_t i = 0; i < gn; ++i) sum_g += *(git + i);

        double mean_a = sum_a / n;
        double std_a = std::sqrt(std::max(0.0, sum_a2 / n - mean_a * mean_a));
        double mean_g = (gn > 0) ? sum_g / gn : 0.0;

        double accel_i = std::min(std_a / 10.0, 1.0);
        double gyro_i = std::min(mean_g / 5.0, 1.0);
        return (accel_i + gyro_i) / 2.0;
    }
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<ChassisNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    executor.spin();
    rclcpp::shutdown();
    return 0;
}
