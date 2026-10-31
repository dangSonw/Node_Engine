#include "animation_asset.hpp"
#include <fastgltf/core.hpp>
#include <fastgltf/tools.hpp>
#include <fastgltf/glm_element_traits.hpp>
#include <ozz/animation/offline/raw_skeleton.h>
#include <ozz/animation/offline/skeleton_builder.h>
#include <ozz/animation/runtime/skeleton.h>
#include <ozz/animation/runtime/local_to_model_job.h>
#include <ozz/base/maths/soa_transform.h>
#include <glm/gtc/quaternion.hpp>
#include <algorithm>
#include <cmath>
#include <fstream>
#include <functional>
#include <set>
#include <stdexcept>

namespace rt {
namespace {
using Path=fastgltf::AnimationPath;
using Interpolation=fastgltf::AnimationInterpolation;
using Transform=ozz::math::Transform;
constexpr size_t byte_limit=128*1024*1024, key_limit=1000000;
void require(bool okay,const char* reason) { if(!okay) throw std::runtime_error(reason); }
void finite(glm::vec4 v) {
    for(int i=0;i<4;++i) require(std::isfinite(v[i]),"Non-finite animation value");
}
void finite(const glm::mat4& m) { for(int i=0;i<4;++i) finite(m[i]); }
glm::quat quaternion(glm::vec4 v) { return {v.w,v.x,v.y,v.z}; }
glm::vec4 xyzw(glm::quat q) { return {q.x,q.y,q.z,q.w}; }
glm::vec4 normalized_rotation(glm::vec4 v) {
    finite(v);
    require(glm::dot(v,v)>1.e-12f,"Animation quaternion has zero length");
    return glm::normalize(v);
}
glm::mat4 matrix(const ozz::math::Float4x4& m) {
    glm::mat4 result;
    for(int col=0;col<4;++col) ozz::math::StorePtrU(m.cols[col],&result[col][0]);
    finite(result); return result;
}
void affine(const glm::mat4& m) {
    finite(m);
    require(std::abs(m[0][3])<1.e-6f && std::abs(m[1][3])<1.e-6f &&
            std::abs(m[2][3])<1.e-6f && std::abs(m[3][3]-1)<1.e-6f,"Animation matrix must be affine");
}
void range(size_t offset,size_t count,size_t stride,size_t element,size_t size) {
    require(offset<=size && count && element<=size-offset && stride>=element &&
            count-1<=(size-offset-element)/stride,"Animation accessor exceeds its buffer view");
}
const fastgltf::Accessor& accessor(const fastgltf::Asset& asset,size_t id,fastgltf::AccessorType type) {
    const auto& a=asset.accessors.at(id);
    require(a.count && a.count<=key_limit && a.type==type && a.componentType==fastgltf::ComponentType::Float && !a.normalized,
            "Invalid animation accessor type or count");
    const auto element=fastgltf::getElementByteSize(a.type,a.componentType);
    if(a.bufferViewIndex) {
        const auto& view=asset.bufferViews.at(*a.bufferViewIndex);
        const auto stride=view.byteStride.value_or(element);
        require(a.byteOffset%4==0 && view.byteOffset%4==0 && stride%4==0,"Misaligned animation accessor");
        range(a.byteOffset,a.count,stride,element,view.byteLength);
    }
    if(a.sparse) {
        const auto& s=*a.sparse;
        require(s.count && s.count<=a.count,"Invalid sparse animation count");
        const auto& indices=asset.bufferViews.at(s.indicesBufferView);
        const auto& values=asset.bufferViews.at(s.valuesBufferView);
        require(!indices.byteStride && !values.byteStride,"Sparse animation views must be tightly packed");
        const auto width=s.indexComponentType==fastgltf::ComponentType::UnsignedByte ? 1u :
                         s.indexComponentType==fastgltf::ComponentType::UnsignedShort ? 2u :
                         s.indexComponentType==fastgltf::ComponentType::UnsignedInt ? 4u : 0u;
        require(width && s.indicesByteOffset%width==0 && s.valuesByteOffset%4==0,"Invalid sparse animation indices");
        range(s.indicesByteOffset,s.count,width,width,indices.byteLength);
        range(s.valuesByteOffset,s.count,element,element,values.byteLength);
        const auto bytes=fastgltf::DefaultBufferDataAdapter{}(asset,s.indicesBufferView);
        uint32_t previous=0;
        for(size_t i=0;i<s.count;++i) {
            uint32_t value=0;
            for(size_t b=0;b<width;++b) value|=uint32_t(std::to_integer<uint8_t>(bytes[s.indicesByteOffset+i*width+b]))<<(8*b);
            require(value<a.count && (!i || value>previous),"Sparse animation indices must be ordered and in range");
            previous=value;
        }
    }
    return a;
}

struct Channel {
    size_t node;
    Path path;
    Interpolation interpolation;
    std::vector<float> times;
    std::vector<glm::vec4> values;
    glm::vec4 sample(double time) const {
        const bool cubic=interpolation==Interpolation::CubicSpline;
        auto key=[&](size_t i){return values[cubic ? i*3+1 : i];};
        glm::vec4 value;
        if(time<=times.front()) value=key(0);
        else if(time>=times.back()) value=key(times.size()-1);
        else {
            const auto right=static_cast<size_t>(std::upper_bound(times.begin(),times.end(),time)-times.begin());
            const auto left=right-1;
            const auto interval=times[right]-times[left];
            const float u=static_cast<float>((time-times[left])/interval);
            if(interpolation==Interpolation::Step) value=key(left);
            else if(cubic) {
                const float u2=u*u,u3=u2*u;
                value=(2*u3-3*u2+1)*key(left)+(u3-2*u2+u)*interval*values[left*3+2]
                     +(-2*u3+3*u2)*key(right)+(u3-u2)*interval*values[right*3];
            } else if(path==Path::Rotation) value=xyzw(glm::slerp(quaternion(key(left)),quaternion(key(right)),u));
            else value=glm::mix(key(left),key(right),u);
        }
        finite(value);
        return path==Path::Rotation ? normalized_rotation(value) : value;
    }
};
struct Skin { std::vector<uint32_t> nodes; std::vector<glm::mat4> inverse_bind; };
}

struct AnimationAsset::Impl {
    ozz::unique_ptr<ozz::animation::Skeleton> skeleton;
    std::vector<size_t> order;
    std::vector<std::string> names;
    std::vector<int> parents;
    std::vector<Transform> rest;
    std::vector<AnimationClipInfo> clips;
    std::vector<std::vector<Channel>> channels;
    std::vector<Skin> skins;

    AnimationPose evaluate(const std::vector<Transform>& transforms) const {
        std::vector<ozz::math::SoaTransform> locals(skeleton->num_soa_joints());
        for(size_t block=0;block<locals.size();++block) {
            ozz::math::SimdFloat4 translations[4],rotations[4],scales[4];
            for(size_t lane=0;lane<4;++lane) {
                const auto i=block*4+lane;
                const auto t=i<order.size() ? transforms[order[i]] : Transform::identity();
                translations[lane]=ozz::math::simd_float4::Load(t.translation.x,t.translation.y,t.translation.z,0);
                rotations[lane]=ozz::math::simd_float4::Load(t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w);
                scales[lane]=ozz::math::simd_float4::Load(t.scale.x,t.scale.y,t.scale.z,0);
            }
            ozz::math::Transpose4x3(translations,&locals[block].translation.x);
            ozz::math::Transpose4x4(rotations,&locals[block].rotation.x);
            ozz::math::Transpose4x3(scales,&locals[block].scale.x);
        }
        std::vector<ozz::math::Float4x4> models(order.size());
        ozz::animation::LocalToModelJob job;
        job.skeleton=skeleton.get(); job.input={locals.data(),locals.size()}; job.output={models.data(),models.size()};
        require(job.Run(),"ozz local-to-model evaluation failed");
        AnimationPose pose; pose.nodes.resize(order.size());
        for(size_t i=0;i<order.size();++i) pose.nodes[order[i]]=matrix(models[i]);
        for(const auto& skin:skins) {
            auto& palette=pose.skins.emplace_back();
            for(size_t i=0;i<skin.nodes.size();++i) {
                auto m=pose.nodes[skin.nodes[i]]*skin.inverse_bind[i]; finite(m); palette.push_back(m);
            }
        }
        return pose;
    }
};

AnimationAsset::AnimationAsset():impl(std::make_unique<Impl>()) {}
AnimationAsset::~AnimationAsset()=default;
const std::vector<AnimationClipInfo>& AnimationAsset::clips() const { return impl->clips; }
const std::vector<std::string>& AnimationAsset::node_names() const { return impl->names; }
const std::vector<int>& AnimationAsset::parents() const { return impl->parents; }
const std::vector<uint32_t>& AnimationAsset::skin_joints(size_t skin) const {
    require(skin<impl->skins.size(),"Skin index is out of range"); return impl->skins[skin].nodes;
}
AnimationPose AnimationAsset::rest_pose() const { return impl->evaluate(impl->rest); }
AnimationPose AnimationAsset::sample(size_t clip,double seconds,bool loop) const {
    require(std::isfinite(seconds),"Animation time must be finite");
    require(clip<impl->clips.size(),"Animation clip index is out of range");
    const auto duration=impl->clips.at(clip).duration;
    double time=std::clamp(seconds,0.,duration);
    if(loop && duration>0) { time=std::fmod(seconds,duration); if(time<0) time+=duration; }
    auto transforms=impl->rest;
    for(const auto& channel:impl->channels.at(clip)) {
        auto& transform=transforms[channel.node]; const auto value=channel.sample(time);
        if(channel.path==Path::Translation) transform.translation={value.x,value.y,value.z};
        else if(channel.path==Path::Scale) transform.scale={value.x,value.y,value.z};
        else transform.rotation={value.x,value.y,value.z,value.w};
    }
    return impl->evaluate(transforms);
}

std::shared_ptr<const AnimationAsset> AnimationAsset::Load(const std::filesystem::path& file) {
    require(std::filesystem::file_size(file)<=64*1024*1024,"Animation document exceeds 64 MiB");
    fastgltf::Parser parser(fastgltf::Extensions::KHR_materials_unlit | fastgltf::Extensions::KHR_texture_transform);
    auto bytes=fastgltf::GltfDataBuffer::FromPath(file);
    require(bytes.error()==fastgltf::Error::None,"Cannot read animation document");
    auto parsed=parser.loadGltf(bytes.get(),file.parent_path());
    if(parsed.error()!=fastgltf::Error::None)
        throw std::runtime_error("Invalid animation glTF: "+std::string(fastgltf::getErrorMessage(parsed.error())));
    auto& asset=parsed.get();
    require(asset.nodes.size()>0 && asset.nodes.size()<=ozz::animation::Skeleton::kMaxJoints,"Animation hierarchy exceeds ozz joint limit or is empty");
    require(asset.buffers.size()<=256 && asset.skins.size()<=256 && asset.animations.size()<=256,"Animation asset count limit exceeded");
    size_t total=0;
    const auto root=std::filesystem::canonical(std::filesystem::absolute(file).parent_path());
    for(auto& buffer:asset.buffers) {
        require(buffer.byteLength<=byte_limit-total,"Animation buffers exceed 128 MiB"); total+=buffer.byteLength;
        if(const auto* uri=std::get_if<fastgltf::sources::URI>(&buffer.data)) {
            require(uri->uri.isLocalPath() && uri->uri.query().empty() && uri->uri.fragment().empty() && !uri->fileByteOffset,
                    "Animation buffer must be a relative local file");
            const auto relative=uri->uri.fspath();
            require(!relative.is_absolute() && !relative.has_root_name(),"Animation buffer must be relative");
            const auto path=std::filesystem::canonical(root/relative);
            const auto local=path.lexically_relative(root);
            require(!local.empty() && *local.begin()!="..","Animation buffer escapes model directory");
            require(std::filesystem::file_size(path)>=buffer.byteLength,"Animation buffer is truncated");
            fastgltf::sources::Array loaded{fastgltf::StaticVector<std::byte>(buffer.byteLength)};
            std::ifstream input(path,std::ios::binary);
            require(bool(input.read(reinterpret_cast<char*>(loaded.bytes.data()),buffer.byteLength)),"Cannot read animation buffer");
            buffer.data=std::move(loaded);
        }
        std::visit([&](const auto& data) {
            if constexpr(requires{data.bytes;}) require(data.bytes.size()>=buffer.byteLength,"Animation buffer is truncated");
            else throw std::runtime_error("Unsupported animation buffer source");
        },buffer.data);
    }
    for(const auto& view:asset.bufferViews) {
        const auto size=asset.buffers.at(view.bufferIndex).byteLength;
        require(!view.meshoptCompression && view.byteOffset<=size && view.byteLength<=size-view.byteOffset,"Invalid animation buffer view");
    }
    require(fastgltf::validate(asset)==fastgltf::Error::None,"Invalid animation glTF structure");
    auto result=std::shared_ptr<AnimationAsset>(new AnimationAsset()); auto& out=*result->impl;
    out.parents.assign(asset.nodes.size(),-1); out.rest.resize(asset.nodes.size()); out.names.resize(asset.nodes.size());
    for(size_t i=0;i<asset.nodes.size();++i) {
        const auto& node=asset.nodes[i]; out.names[i]=std::string(node.name);
        for(auto child:node.children) {
            require(child<asset.nodes.size() && child!=i && out.parents[child]==-1,"Animation hierarchy has duplicate parents or a cycle");
            out.parents[child]=static_cast<int>(i);
        }
        auto& t=out.rest[i];
        if(const auto* trs=std::get_if<fastgltf::TRS>(&node.transform)) {
            finite({trs->translation[0],trs->translation[1],trs->translation[2],0});
            finite({trs->scale[0],trs->scale[1],trs->scale[2],0});
            const glm::vec4 raw{trs->rotation[0],trs->rotation[1],trs->rotation[2],trs->rotation[3]};
            require(std::abs(glm::dot(raw,raw)-1)<.002f,"Node quaternion must have unit length");
            const auto q=normalized_rotation(raw);
            t.translation={trs->translation[0],trs->translation[1],trs->translation[2]};
            t.rotation={q.x,q.y,q.z,q.w}; t.scale={trs->scale[0],trs->scale[1],trs->scale[2]};
        } else {
            const auto& input=std::get<fastgltf::math::fmat4x4>(node.transform);
            ozz::math::Float4x4 m;
            for(int c=0;c<4;++c) m.cols[c]=ozz::math::simd_float4::Load(input[c][0],input[c][1],input[c][2],input[c][3]);
            const auto original=matrix(m); affine(original);
            require(ozz::math::ToAffine(m,&t),"Node matrix cannot be decomposed to TRS");
            const auto rebuilt=matrix(ozz::math::Float4x4::FromAffine(t));
            for(int c=0;c<4;++c) for(int r=0;r<4;++r)
                require(std::abs(original[c][r]-rebuilt[c][r])<=1.e-4f*std::max(1.f,std::abs(original[c][r])),"Node matrix contains unsupported shear");
        }
    }
    ozz::animation::offline::RawSkeleton raw;
    std::function<void(size_t,ozz::animation::offline::RawSkeleton::Joint&,size_t)> visit;
    visit=[&](size_t i,auto& joint,size_t depth) {
        require(depth<=256,"Animation hierarchy depth exceeds 256");
        out.order.push_back(i); joint.name=std::to_string(i).c_str(); joint.transform=out.rest[i];
        const auto& children=asset.nodes[i].children; joint.children.resize(children.size());
        for(size_t j=0;j<children.size();++j) visit(children[j],joint.children[j],depth+1);
    };
    for(size_t i=0;i<asset.nodes.size();++i) if(out.parents[i]<0) {
        raw.roots.emplace_back(); visit(i,raw.roots.back(),0);
    }
    require(out.order.size()==asset.nodes.size(),"Animation hierarchy contains a cycle");
    out.skeleton=ozz::animation::offline::SkeletonBuilder{}(raw);
    require(bool(out.skeleton),"ozz skeleton build failed");
    for(size_t i=0;i<out.order.size();++i)
        require(std::string(out.skeleton->joint_names()[i])==std::to_string(out.order[i]),"ozz skeleton order differs from node mapping");
    auto tree_root=[&](size_t node) {
        while(out.parents[node]>=0) node=static_cast<size_t>(out.parents[node]);
        return node;
    };
    for(const auto& skin:asset.skins) {
        require(!skin.joints.empty() && skin.joints.size()<=asset.nodes.size(),"Invalid skin joint count");
        Skin value; std::set<size_t> used;
        for(auto joint:skin.joints) {
            require(joint<asset.nodes.size() && used.insert(joint).second,"Invalid or duplicated skin joint");
            require(tree_root(joint)==tree_root(skin.joints.front()),"Skin joints must share a common ancestor");
            value.nodes.push_back(static_cast<uint32_t>(joint));
        }
        if(skin.skeleton) {
            require(*skin.skeleton<asset.nodes.size(),"Invalid skeleton root");
            for(auto joint:skin.joints) {
                int ancestor=static_cast<int>(joint);
                while(ancestor>=0 && size_t(ancestor)!=*skin.skeleton) ancestor=out.parents[ancestor];
                require(ancestor>=0,"Skeleton root is not an ancestor of every skin joint");
            }
        }
        value.inverse_bind.assign(value.nodes.size(),glm::mat4(1));
        if(skin.inverseBindMatrices) {
            const auto& a=accessor(asset,*skin.inverseBindMatrices,fastgltf::AccessorType::Mat4);
            require(a.count>=value.nodes.size(),"Inverse bind count is smaller than skin joint count");
            fastgltf::iterateAccessorWithIndex<glm::mat4>(asset,a,[&](auto m,size_t i) {
                if(i<value.nodes.size()) { affine(m); value.inverse_bind[i]=m; }
            });
        }
        out.skins.push_back(std::move(value));
    }
    for(const auto& scene:asset.scenes) {
        std::set<size_t> roots;
        for(auto node:scene.nodeIndices) {
            require(node<asset.nodes.size() && out.parents[node]<0,"Scene roots must have no parent"); roots.insert(node);
        }
        for(size_t i=0;i<asset.nodes.size();++i) if(asset.nodes[i].skinIndex && roots.contains(tree_root(i))) {
            const auto& skin=out.skins.at(*asset.nodes[i].skinIndex);
            require(roots.contains(tree_root(skin.nodes.front())),"Skin skeleton must belong to the same scene as its mesh");
        }
    }
    size_t keys=0; std::set<std::string> names;
    for(size_t index=0;index<asset.animations.size();++index) {
        const auto& animation=asset.animations[index];
        require(!animation.channels.empty() && animation.channels.size()<=asset.nodes.size()*3,"Invalid animation channel count");
        std::string name=animation.name.empty() ? "Animation "+std::to_string(index+1) : std::string(animation.name);
        const auto base=name; int suffix=2;
        while(!names.insert(name).second) name=base+" ("+std::to_string(suffix++)+")";
        AnimationClipInfo info{name,0,animation.channels.size()}; std::vector<Channel> channels;
        std::set<std::pair<size_t,Path>> targets;
        for(const auto& source:animation.channels) {
            require(source.nodeIndex && *source.nodeIndex<asset.nodes.size(),"Animation channel has no valid node");
            require(source.path==Path::Translation || source.path==Path::Rotation || source.path==Path::Scale,"Morph weight animation is not implemented");
            require(std::holds_alternative<fastgltf::TRS>(asset.nodes[*source.nodeIndex].transform),"Animation cannot target a matrix node");
            require(targets.emplace(*source.nodeIndex,source.path).second,"Duplicate animation channel for node property");
            const auto& sampler=animation.samplers.at(source.samplerIndex);
            require(sampler.interpolation==Interpolation::Linear || sampler.interpolation==Interpolation::Step ||
                    sampler.interpolation==Interpolation::CubicSpline,"Unsupported animation interpolation");
            Channel c{*source.nodeIndex,source.path,sampler.interpolation,{},{}};
            const auto& times=accessor(asset,sampler.inputAccessor,fastgltf::AccessorType::Scalar);
            require(times.count<=key_limit-keys,"Animation exceeds one million keys"); keys+=times.count;
            c.times.reserve(times.count);
            fastgltf::iterateAccessor<float>(asset,times,[&](float time) {
                require(std::isfinite(time) && time>=0 && (c.times.empty() || time>c.times.back()),"Animation times must be finite, nonnegative and strictly increasing");
                c.times.push_back(time);
            });
            const bool cubic=c.interpolation==Interpolation::CubicSpline;
            require(!cubic || times.count>=2,"Cubic animation needs at least two keys");
            const auto& values=accessor(asset,sampler.outputAccessor,source.path==Path::Rotation ? fastgltf::AccessorType::Vec4 : fastgltf::AccessorType::Vec3);
            require(values.count==times.count*(cubic?3:1),"Animation output count does not match times/interpolation");
            c.values.reserve(values.count);
            auto add=[&](glm::vec4 value) {
                finite(value);
                if(c.path==Path::Rotation && (!cubic || c.values.size()%3==1)) {
                    require(std::abs(glm::dot(value,value)-1)<.002f,"Animation key quaternion must have unit length");
                    value=normalized_rotation(value);
                }
                c.values.push_back(value);
            };
            if(c.path==Path::Rotation) fastgltf::iterateAccessor<glm::vec4>(asset,values,add);
            else fastgltf::iterateAccessor<glm::vec3>(asset,values,[&](auto v){add(glm::vec4(v,0));});
            info.duration=std::max(info.duration,double(c.times.back())); channels.push_back(std::move(c));
        }
        out.clips.push_back(info); out.channels.push_back(std::move(channels));
    }
    result->rest_pose(); // Reject overflowing parent transforms before publishing the immutable asset.
    return result;
}

glm::vec3 SkinPosition(const AnimationPose& pose,size_t skin,glm::vec3 position,std::span<const SkinInfluence> influences) {
    finite(glm::vec4(position,1));
    require(!influences.empty() && influences.size()<=16,"Skin vertex must have 1 to 16 influences");
    require(skin<pose.skins.size(),"Skin index is out of range");
    const auto& palette=pose.skins[skin]; glm::vec4 result(0); float sum=0;
    for(const auto& influence:influences) {
        require(std::isfinite(influence.weight) && influence.weight>=0 && influence.weight<=1,"Invalid skin weight");
        require(influence.joint<palette.size(),"Skin joint index is out of range");
        const auto& transform=palette[influence.joint];
        result+=influence.weight*(transform*glm::vec4(position,1)); sum+=influence.weight;
    }
    require(sum>0,"Skin weights sum to zero"); result/=sum; finite(result);
    return glm::vec3(result);
}
}
