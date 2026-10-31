#include "animation_asset.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include <iostream>
#include <limits>
using Json=nlohmann::json;
Json Matrix(const glm::mat4& matrix) {
    auto out=Json::array();
    for(int c=0;c<4;++c) for(int r=0;r<4;++r) out.push_back(matrix[c][r]);
    return out;
}
Json Pose(const rt::AnimationPose& pose) {
    Json out={{"nodes",Json::array()},{"skins",Json::array()}};
    for(const auto& matrix:pose.nodes) out["nodes"].push_back(Matrix(matrix));
    for(const auto& palette:pose.skins) {
        auto matrices=Json::array();
        for(const auto& matrix:palette) matrices.push_back(Matrix(matrix));
        out["skins"].push_back(matrices);
    }
    return out;
}
int main(int argc,char** argv) {
    try {
        if(argc!=2) throw std::runtime_error("Expected a JSON request file");
        std::ifstream input(std::filesystem::u8path(argv[1])); Json request; input>>request;
        auto asset=rt::AnimationAsset::Load(std::filesystem::u8path(request.at("file").get<std::string>()));
        Json out={{"ok",true},{"nodes",asset->node_names()},{"parents",asset->parents()},
                  {"clips",Json::array()},{"rest",Pose(asset->rest_pose())},{"samples",Json::array()}};
        for(const auto& clip:asset->clips()) out["clips"].push_back({{"name",clip.name},{"duration",clip.duration},{"channels",clip.channels}});
        for(const auto& sample:request.value("samples",Json::array())) {
            const double time=sample.value("nonfinite",false) ? std::numeric_limits<double>::infinity() : sample.at("time").get<double>();
            const auto pose=asset->sample(sample.at("clip").get<size_t>(),time,sample.value("loop",false));
            auto value=Pose(pose); value["positions"]=Json::array();
            for(const auto& vertex:sample.value("vertices",Json::array())) {
                std::vector<rt::SkinInfluence> influences;
                for(const auto& influence:vertex.at("weights")) influences.push_back({influence[0].get<uint32_t>(),influence[1].get<float>()});
                const auto& p=vertex.at("position");
                auto v=rt::SkinPosition(pose,vertex.value("skin",0),{p[0],p[1],p[2]},influences);
                value["positions"].push_back({v.x,v.y,v.z});
            }
            out["samples"].push_back(value);
        }
        std::cout<<out.dump()<<'\n'; return 0;
    } catch(const std::exception& error) {
        std::cout<<Json{{"ok",false},{"error",error.what()}}.dump()<<'\n'; return 1;
    }
}
