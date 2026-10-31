#pragma once
#include <cstdint>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <vector>
#include <glm/glm.hpp>

namespace rt {
struct AnimationClipInfo {
    std::string name;
    double duration=0;
    size_t channels=0;
};
struct AnimationPose {
    // Document node order, then skin/joint order as authored in glTF.
    std::vector<glm::mat4> nodes;
    std::vector<std::vector<glm::mat4>> skins;
};
struct SkinInfluence { uint32_t joint; float weight; };

class AnimationAsset {
public:
    static std::shared_ptr<const AnimationAsset> Load(const std::filesystem::path&);
    ~AnimationAsset();
    const std::vector<AnimationClipInfo>& clips() const;
    const std::vector<std::string>& node_names() const;
    const std::vector<int>& parents() const;
    const std::vector<uint32_t>& skin_joints(size_t skin) const;
    AnimationPose rest_pose() const;
    AnimationPose sample(size_t clip,double seconds,bool loop=false) const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl;
    AnimationAsset();
};

// Skin matrices map the original vertex to model space; do not apply the glTF
// mesh node transform a second time. The engine entity transform still applies.
glm::vec3 SkinPosition(const AnimationPose&,size_t skin,glm::vec3 position,std::span<const SkinInfluence>);
}
