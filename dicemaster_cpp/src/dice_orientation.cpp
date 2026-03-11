#include "dicemaster_cpp/dice_orientation.hpp"
#include <yaml-cpp/yaml.h>
#include <stdexcept>
#include <limits>

const std::array<std::string, 4> DiceOrientation::EDGE_NAMES = {"top", "left", "bottom", "right"};
const std::map<std::string, int> DiceOrientation::EDGE_TO_ROTATION = {
    {"bottom", 0}, {"right", 1}, {"top", 2}, {"left", 3}
};

DiceOrientation::DiceOrientation(const std::string& config_path) {
    precompute(config_path);
}

void DiceOrientation::precompute(const std::string& config_path) {
    YAML::Node cfg = YAML::LoadFile(config_path);

    // Base joint rotation: imu_link -> base_link
    auto bq = cfg["base_joint"]["quaternion"];
    // YAML stores [x, y, z, w]
    Eigen::Quaterniond base_q(bq[3].as<double>(), bq[0].as<double>(),
                               bq[1].as<double>(), bq[2].as<double>());
    base_rotation_ = base_q.normalized();

    double face_offset = cfg["face_offset"].as<double>();
    Eigen::Vector3d canonical_face_offset(0.0, 0.0, face_offset);
    Eigen::Vector3d canonical_normal(0.0, 0.0, 1.0);

    // Canonical edge offsets
    auto ce = cfg["canonical_edges"];
    std::array<Eigen::Vector3d, 4> canonical_edges;
    for (int i = 0; i < 4; ++i) {
        auto e = ce[EDGE_NAMES[i]];
        canonical_edges[i] = Eigen::Vector3d(e[0].as<double>(), e[1].as<double>(), e[2].as<double>());
    }

    // Collect screen IDs (sorted)
    auto screens = cfg["screens"];
    screen_ids_.clear();
    for (auto it = screens.begin(); it != screens.end(); ++it) {
        screen_ids_.push_back(it->first.as<int>());
    }
    std::sort(screen_ids_.begin(), screen_ids_.end());
    n_screens_ = static_cast<int>(screen_ids_.size());

    // Precompute per-screen geometry
    face_normals_.resize(n_screens_, 3);
    face_centres_.resize(n_screens_, 3);
    edge_positions_.resize(n_screens_);

    for (int i = 0; i < n_screens_; ++i) {
        int sid = screen_ids_[i];
        auto jq = screens[sid]["joint_quaternion"];
        Eigen::Quaterniond joint_q(jq[3].as<double>(), jq[0].as<double>(),
                                    jq[1].as<double>(), jq[2].as<double>());
        joint_q.normalize();

        // Face normal in base_link frame
        Eigen::Vector3d normal = joint_q * canonical_normal;
        face_normals_.row(i) = normal.transpose();

        // Face centre in base_link frame
        Eigen::Vector3d centre = joint_q * canonical_face_offset;
        face_centres_.row(i) = centre.transpose();

        // Edge positions in base_link frame
        for (int j = 0; j < 4; ++j) {
            edge_positions_[i][j] = joint_q * canonical_edges[j] + centre;
        }
    }
}

OrientationResult DiceOrientation::compute(double qx, double qy, double qz, double qw) const {
    // Composite rotation: world <- imu <- base_link
    Eigen::Quaterniond imu_rot(qw, qx, qy, qz);
    Eigen::Quaterniond world_rot = imu_rot * base_rotation_;
    Eigen::Matrix3d rot_mat = world_rot.toRotationMatrix();

    OrientationResult result;

    double max_z = -std::numeric_limits<double>::infinity();
    double min_z = std::numeric_limits<double>::infinity();
    int top_idx = 0, bottom_idx = 0;

    for (int i = 0; i < n_screens_; ++i) {
        // Rotate face normal -> extract z component (up alignment)
        Eigen::Vector3d world_normal = rot_mat * face_normals_.row(i).transpose();
        double up_alignment = world_normal.z();

        // Face centre z in world frame
        Eigen::Vector3d world_centre = rot_mat * face_centres_.row(i).transpose();
        double fz = world_centre.z();

        int sid = screen_ids_[i];
        result.up_alignments[sid] = up_alignment;
        result.face_z[sid] = fz;

        if (up_alignment > max_z) {
            max_z = up_alignment;
            top_idx = i;
        }
        if (up_alignment < min_z) {
            min_z = up_alignment;
            bottom_idx = i;
        }
    }

    result.top_screen = screen_ids_[top_idx];
    result.bottom_screen = screen_ids_[bottom_idx];

    // Compute edge z for top screen
    double min_edge_z = std::numeric_limits<double>::infinity();
    int lowest_edge_idx = 0;
    for (int j = 0; j < 4; ++j) {
        Eigen::Vector3d world_edge = rot_mat * edge_positions_[top_idx][j];
        double ez = world_edge.z();
        result.top_edge_z[EDGE_NAMES[j]] = ez;
        if (ez < min_edge_z) {
            min_edge_z = ez;
            lowest_edge_idx = j;
        }
    }

    auto it = EDGE_TO_ROTATION.find(EDGE_NAMES[lowest_edge_idx]);
    result.top_rotation = (it != EDGE_TO_ROTATION.end()) ? it->second : 0;

    return result;
}
