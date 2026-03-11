#pragma once

#include <array>
#include <map>
#include <string>
#include <vector>

#include <Eigen/Dense>
#include <Eigen/Geometry>

struct OrientationResult {
    std::map<int, double> face_z;
    std::map<int, double> up_alignments;
    int top_screen;
    int bottom_screen;
    int top_rotation;  // 0/1/2/3
    std::map<std::string, double> top_edge_z;
};

class DiceOrientation {
public:
    explicit DiceOrientation(const std::string& config_path);

    OrientationResult compute(double qx, double qy, double qz, double qw) const;

    static constexpr int NUM_SCREENS = 6;
    static constexpr int NUM_EDGES = 4;

private:
    void precompute(const std::string& config_path);

    Eigen::Quaterniond base_rotation_;
    std::vector<int> screen_ids_;
    int n_screens_;

    // Precomputed geometry in base_link frame: per-screen arrays
    Eigen::MatrixXd face_normals_;   // (N, 3)
    Eigen::MatrixXd face_centres_;   // (N, 3)
    // Edge positions: edge_positions_[screen_idx][edge_idx] = Vector3d
    std::vector<std::array<Eigen::Vector3d, 4>> edge_positions_;

    static const std::array<std::string, 4> EDGE_NAMES;
    static const std::map<std::string, int> EDGE_TO_ROTATION;
};
