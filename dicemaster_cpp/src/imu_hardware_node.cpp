#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <random>
#include <string>

#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>

// I2C helpers using I2C_RDWR ioctl (works on all adapters including software I2C)
static int i2c_write_reg(int fd, uint16_t addr, uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    struct i2c_msg msg = {
        .addr = addr,
        .flags = 0,
        .len = 2,
        .buf = buf
    };
    struct i2c_rdwr_ioctl_data rdwr = {
        .msgs = &msg,
        .nmsgs = 1
    };
    return ioctl(fd, I2C_RDWR, &rdwr);
}

static int i2c_read_block(int fd, uint16_t addr, uint8_t reg, uint8_t len, uint8_t* out) {
    struct i2c_msg msgs[2] = {
        { .addr = addr, .flags = 0,        .len = 1,   .buf = &reg },
        { .addr = addr, .flags = I2C_M_RD, .len = len, .buf = out  }
    };
    struct i2c_rdwr_ioctl_data rdwr = {
        .msgs = msgs,
        .nmsgs = 2
    };
    return ioctl(fd, I2C_RDWR, &rdwr);
}

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>

class ImuHardwareNode : public rclcpp::Node {
public:
    ImuHardwareNode() : Node("imu_hardware_cpp"), rng_(42) {
        // Parameters
        declare_parameter("i2c_bus", 6);
        declare_parameter("i2c_address", 0x68);
        declare_parameter("polling_rate", 50.0);
        declare_parameter("calibration_file", std::string(""));
        declare_parameter("simulate", false);

        i2c_bus_ = get_parameter("i2c_bus").as_int();
        i2c_address_ = static_cast<uint16_t>(get_parameter("i2c_address").as_int());
        double rate = get_parameter("polling_rate").as_double();
        std::string cal_file = get_parameter("calibration_file").as_string();
        simulate_ = get_parameter("simulate").as_bool();

        // Initialize I2C (skip if simulating)
        if (!simulate_) {
            init_i2c();
            if (i2c_fd_ < 0) {
                RCLCPP_WARN(get_logger(), "I2C unavailable — falling back to simulate mode");
                simulate_ = true;
            }
        }

        if (simulate_) {
            RCLCPP_INFO(get_logger(), "Running in SIMULATE mode (synthetic IMU data)");
        }

        // Load calibration
        load_calibration(cal_file);

        // Publisher
        pub_ = create_publisher<sensor_msgs::msg::Imu>("/imu/data_raw", 10);

        // Timer
        timer_ = create_wall_timer(
            std::chrono::microseconds(static_cast<int64_t>(1e6 / rate)),
            std::bind(&ImuHardwareNode::timer_callback, this));

        RCLCPP_INFO(get_logger(), "IMU hardware C++ node initialized (bus=%d, addr=0x%02X, rate=%.0fHz, sim=%s)",
                     i2c_bus_, i2c_address_, rate, simulate_ ? "true" : "false");
    }

    ~ImuHardwareNode() {
        if (i2c_fd_ >= 0) close(i2c_fd_);
    }

private:
    static constexpr double ACCEL_SCALE = 9.81 / 16384.0;   // ±2g -> m/s²
    static constexpr double GYRO_SCALE = M_PI / (180.0 * 131.0);  // ±250°/s -> rad/s
    static constexpr uint8_t ACCEL_XOUT_H = 0x3B;
    static constexpr uint8_t PWR_MGMT_1 = 0x6B;
    static constexpr uint8_t SMPLRT_DIV = 0x19;
    static constexpr uint8_t CONFIG_REG = 0x1A;
    static constexpr uint8_t GYRO_CONFIG = 0x1B;
    static constexpr uint8_t ACCEL_CONFIG = 0x1C;

    int i2c_fd_ = -1;
    int i2c_bus_;
    uint16_t i2c_address_;
    bool simulate_ = false;

    double acc_bias_[3] = {0, 0, 0};
    double gyro_bias_[3] = {0, 0, 0};
    bool calibrated_ = false;

    // Simulation state
    std::mt19937 rng_;
    std::normal_distribution<double> accel_noise_{0.0, 0.05};  // ~0.05 m/s² noise
    std::normal_distribution<double> gyro_noise_{0.0, 0.01};   // ~0.01 rad/s noise
    double sim_phase_ = 0.0;

    rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr pub_;
    rclcpp::TimerBase::SharedPtr timer_;

    void init_i2c() {
        std::string dev = "/dev/i2c-" + std::to_string(i2c_bus_);
        i2c_fd_ = open(dev.c_str(), O_RDWR);
        if (i2c_fd_ < 0) {
            RCLCPP_ERROR(get_logger(), "Failed to open %s", dev.c_str());
            return;
        }

        // Probe: try to read WHO_AM_I register (0x75) via I2C_RDWR
        uint8_t who_am_i = 0;
        if (i2c_read_block(i2c_fd_, i2c_address_, 0x75, 1, &who_am_i) < 0) {
            RCLCPP_WARN(get_logger(), "No MPU6050 detected at 0x%02X on %s", i2c_address_, dev.c_str());
            close(i2c_fd_);
            i2c_fd_ = -1;
            return;
        }
        RCLCPP_INFO(get_logger(), "MPU6050 WHO_AM_I = 0x%02X", who_am_i);

        // Wake up MPU6050
        write_reg(PWR_MGMT_1, 0x00);
        usleep(100000);
        write_reg(SMPLRT_DIV, 7);
        write_reg(ACCEL_CONFIG, 0x00);
        write_reg(GYRO_CONFIG, 0x00);
        write_reg(CONFIG_REG, 0x00);
    }

    void write_reg(uint8_t reg, uint8_t val) {
        if (i2c_write_reg(i2c_fd_, i2c_address_, reg, val) < 0) {
            RCLCPP_WARN(get_logger(), "I2C write failed for reg 0x%02X", reg);
        }
    }

    void load_calibration(const std::string& path) {
        std::string cal_path = path;
        if (cal_path.empty()) {
            acc_bias_[0] = -0.02376398;
            acc_bias_[1] = -0.00155967;
            acc_bias_[2] =  0.18710161;
            gyro_bias_[0] = -0.12902888;
            gyro_bias_[1] = -0.01044459;
            gyro_bias_[2] =  0.00327823;
            calibrated_ = true;
            RCLCPP_INFO(get_logger(), "Using built-in calibration values");
            return;
        }

        std::ifstream f(cal_path);
        if (!f.is_open()) {
            RCLCPP_WARN(get_logger(), "No calibration file found at %s", cal_path.c_str());
            return;
        }
        RCLCPP_INFO(get_logger(), "Calibration loaded from %s", cal_path.c_str());
        calibrated_ = true;
    }

    void timer_callback() {
        double ax, ay, az, gx, gy, gz;

        if (simulate_) {
            // Synthetic data: gravity + gentle rotation + sensor noise
            sim_phase_ += 0.02;
            ax = 0.1 * std::sin(sim_phase_ * 0.7) + accel_noise_(rng_);
            ay = 0.1 * std::cos(sim_phase_ * 0.5) + accel_noise_(rng_);
            az = 9.81 + 0.05 * std::sin(sim_phase_ * 0.3) + accel_noise_(rng_);
            gx = 0.02 * std::sin(sim_phase_ * 0.4) + gyro_noise_(rng_);
            gy = 0.02 * std::cos(sim_phase_ * 0.6) + gyro_noise_(rng_);
            gz = 0.01 * std::sin(sim_phase_ * 0.2) + gyro_noise_(rng_);
        } else {
            // Real I2C read
            uint8_t buf[14];
            if (i2c_read_block(i2c_fd_, i2c_address_, ACCEL_XOUT_H, 14, buf) < 0) {
                RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000, "I2C read failed");
                return;
            }
            auto parse_i16 = [](const uint8_t* p) -> int16_t {
                return static_cast<int16_t>((p[0] << 8) | p[1]);
            };
            ax = parse_i16(buf + 0) * ACCEL_SCALE;
            ay = parse_i16(buf + 2) * ACCEL_SCALE;
            az = parse_i16(buf + 4) * ACCEL_SCALE;
            gx = parse_i16(buf + 8) * GYRO_SCALE;
            gy = parse_i16(buf + 10) * GYRO_SCALE;
            gz = parse_i16(buf + 12) * GYRO_SCALE;
        }

        // Apply calibration
        if (calibrated_) {
            ax -= acc_bias_[0];
            ay -= acc_bias_[1];
            az -= acc_bias_[2];
            gx -= gyro_bias_[0];
            gy -= gyro_bias_[1];
            gz -= gyro_bias_[2];
        }

        // Publish
        auto msg = sensor_msgs::msg::Imu();
        msg.header.stamp = now();
        msg.header.frame_id = "imu_link";
        msg.linear_acceleration.x = ax;
        msg.linear_acceleration.y = ay;
        msg.linear_acceleration.z = az;
        msg.angular_velocity.x = gx;
        msg.angular_velocity.y = gy;
        msg.angular_velocity.z = gz;
        msg.orientation_covariance[0] = -1.0;
        msg.angular_velocity_covariance[0] = 0.01;
        msg.linear_acceleration_covariance[0] = 0.1;
        pub_->publish(msg);
    }
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<ImuHardwareNode>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    executor.spin();
    rclcpp::shutdown();
    return 0;
}
