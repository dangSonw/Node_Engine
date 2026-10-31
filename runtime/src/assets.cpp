#include "display.hpp"
#include <SDL3_image/SDL_image.h>
#include <fastgltf/core.hpp>
#include <fastgltf/tools.hpp>
#include <fastgltf/glm_element_traits.hpp>
#include <cstring>
#include <fstream>
#include <limits>
#include <span>

namespace rt {
namespace {
constexpr size_t image_limit=64*1024*1024, decoded_limit=256*1024*1024, index_limit=3000000;
void check(bool okay,const char* message) { if(!okay) throw std::runtime_error(message); }
void geometry_buffers(const fastgltf::Asset& asset) {
    for(const auto& buffer:asset.buffers) std::visit([&](const auto& data) {
        if constexpr(requires{data.bytes;}) check(data.bytes.size()>=buffer.byteLength,"Truncated model buffer");
        else throw std::runtime_error("Unsupported model buffer source");
    },buffer.data);
    for(const auto& view:asset.bufferViews) {
        const auto size=asset.buffers.at(view.bufferIndex).byteLength;
        check(!view.meshoptCompression && view.byteOffset<=size && view.byteLength<=size-view.byteOffset,"Invalid model buffer view");
    }
    auto range=[](size_t offset,size_t count,size_t stride,size_t element,size_t size) {
        check(offset<=size && count && element<=size-offset && stride>=element &&
              count-1<=(size-offset-element)/stride,"Model accessor exceeds buffer view");
    };
    for(const auto& a:asset.accessors) {
        const auto element=fastgltf::getElementByteSize(a.type,a.componentType);
        const auto width=fastgltf::getComponentByteSize(a.componentType);
        check(element && width && a.count && a.count<=index_limit,"Invalid model accessor size");
        if(a.bufferViewIndex) {
            const auto& view=asset.bufferViews.at(*a.bufferViewIndex); const auto stride=view.byteStride.value_or(element);
            check(a.byteOffset%width==0 && view.byteOffset%width==0 && stride%width==0,"Misaligned model accessor");
            range(a.byteOffset,a.count,stride,element,view.byteLength);
        }
        if(a.sparse) {
            const auto& s=*a.sparse; const auto& indices=asset.bufferViews.at(s.indicesBufferView);
            const auto& values=asset.bufferViews.at(s.valuesBufferView);
            const auto size=s.indexComponentType==fastgltf::ComponentType::UnsignedByte ? 1u :
                s.indexComponentType==fastgltf::ComponentType::UnsignedShort ? 2u :
                s.indexComponentType==fastgltf::ComponentType::UnsignedInt ? 4u : 0u;
            check(size && s.count<=a.count && !indices.byteStride && !values.byteStride &&
                  s.indicesByteOffset%size==0 && s.valuesByteOffset%width==0,"Invalid sparse model accessor");
            range(s.indicesByteOffset,s.count,size,size,indices.byteLength);
            range(s.valuesByteOffset,s.count,element,element,values.byteLength);
            const auto bytes=fastgltf::DefaultBufferDataAdapter{}(asset,s.indicesBufferView);
            uint32_t previous=0;
            for(size_t i=0;i<s.count;++i) {
                uint32_t value=0;
                for(size_t b=0;b<size;++b) value|=uint32_t(std::to_integer<uint8_t>(bytes[s.indicesByteOffset+i*size+b]))<<(8*b);
                check(value<a.count && (!i || value>previous),"Sparse model indices must be ordered and in range"); previous=value;
            }
        }
    }
}
void check_image_dimensions(std::span<const std::byte> bytes) {
    auto u8=[&](size_t i){return std::to_integer<uint32_t>(bytes[i]);};
    auto u16=[&](size_t i){return (u8(i)<<8)|u8(i+1);};
    auto u32=[&](size_t i){return (u16(i)<<16)|u16(i+2);};
    uint32_t width=0,height=0;
    if(bytes.size()>=24 && std::memcmp(bytes.data(),"\x89PNG\r\n\x1a\n",8)==0) {
        check(u32(8)==13 && std::memcmp(bytes.data()+12,"IHDR",4)==0,"Invalid PNG header");
        width=u32(16); height=u32(20);
    } else if(bytes.size()>=4 && u16(0)==0xffd8) {
        size_t offset=2;
        while(offset<bytes.size()) {
            check(u8(offset++)==0xff,"Invalid JPEG marker");
            while(offset<bytes.size() && u8(offset)==0xff) ++offset;
            check(offset<bytes.size(),"Truncated JPEG marker");
            const auto marker=u8(offset++);
            if(marker==0xd9 || marker==0xda) break;
            if(marker==1 || (marker>=0xd0 && marker<=0xd7)) continue;
            check(offset+2<=bytes.size(),"Truncated JPEG segment");
            const auto length=u16(offset);
            check(length>=2 && length<=bytes.size()-offset,"Invalid JPEG segment length");
            if(marker>=0xc0 && marker<=0xcf && marker!=0xc4 && marker!=0xc8 && marker!=0xcc) {
                check(length>=8,"Invalid JPEG frame header");
                height=u16(offset+3); width=u16(offset+5); break;
            }
            offset+=length;
        }
    } else throw std::runtime_error("Base-color textures must be PNG or JPEG");
    check(width && height && width<=8192 && height<=8192 && uint64_t(width)*height*4<=image_limit,
          "Texture header exceeds 8192 per axis or 64 MiB, or is invalid");
}
ImageData decode_pixels(std::span<const std::byte> bytes) {
    check(!bytes.empty() && bytes.size()<=image_limit,"Encoded texture exceeds 64 MiB or is empty");
    check_image_dimensions(bytes); // Reject decompression bombs before the decoder allocates pixels.
    auto* io=SDL_IOFromConstMem(bytes.data(),bytes.size());
    if(!io) throw std::runtime_error(SDL_GetError());
    if(!IMG_isPNG(io) && !IMG_isJPG(io)) {
        SDL_CloseIO(io); throw std::runtime_error("Base-color textures must be PNG or JPEG");
    }
    std::unique_ptr<SDL_Surface,decltype(&SDL_DestroySurface)> loaded(IMG_Load_IO(io,true),SDL_DestroySurface);
    if(!loaded) throw std::runtime_error("Cannot decode texture: "+std::string(SDL_GetError()));
    check(loaded->w>0 && loaded->h>0 && loaded->w<=8192 && loaded->h<=8192 &&
          uint64_t(loaded->w)*loaded->h*4<=image_limit,"Decoded texture exceeds 8192 per axis or 64 MiB");
    std::unique_ptr<SDL_Surface,decltype(&SDL_DestroySurface)> rgba(
        SDL_ConvertSurface(loaded.get(),SDL_PIXELFORMAT_RGBA32),SDL_DestroySurface);
    if(!rgba) throw std::runtime_error(SDL_GetError());
    ImageData image; image.width=rgba->w; image.height=rgba->h;
    image.rgba.resize(size_t(image.width)*image.height*4);
    for(uint32_t y=0;y<image.height;++y)
        std::memcpy(image.rgba.data()+size_t(y)*image.width*4,
                    static_cast<uint8_t*>(rgba->pixels)+size_t(y)*rgba->pitch,image.width*4);
    return image;
}
ImageData decode_image(const fastgltf::Asset& asset,size_t index,const std::filesystem::path& root) {
    std::vector<std::byte> external;
    std::span<const std::byte> bytes;
    std::visit([&](const auto& source) {
        using T=std::decay_t<decltype(source)>;
        if constexpr(std::is_same_v<T,fastgltf::sources::URI>) {
            const auto& uri=source.uri;
            check(uri.isLocalPath() && uri.query().empty() && uri.fragment().empty() && !source.fileByteOffset,
                  "Texture URI must be a relative local file");
            const auto relative=uri.fspath();
            check(!relative.is_absolute() && !relative.has_root_name(),"Texture URI must be relative");
            const auto file=std::filesystem::canonical(root/relative);
            const auto local=file.lexically_relative(std::filesystem::canonical(root));
            check(!local.empty() && *local.begin()!="..", "Texture URI escapes model directory");
            const auto length=std::filesystem::file_size(file);
            check(length && length<=image_limit,"Encoded texture exceeds 64 MiB or is empty");
            external.resize(length);
            std::ifstream input(file,std::ios::binary);
            check(bool(input.read(reinterpret_cast<char*>(external.data()),length)),"Cannot read texture");
            bytes=external;
        } else if constexpr(std::is_same_v<T,fastgltf::sources::BufferView>) {
            const auto view=fastgltf::DefaultBufferDataAdapter{}(asset,source.bufferViewIndex);
            bytes={view.data(),view.size()};
        } else if constexpr(std::is_same_v<T,fastgltf::sources::Array> ||
                            std::is_same_v<T,fastgltf::sources::Vector> ||
                            std::is_same_v<T,fastgltf::sources::ByteView>) {
            bytes={source.bytes.data(),source.bytes.size()};
        } else throw std::runtime_error("Unsupported texture data source");
    },asset.images.at(index).data);
    return decode_pixels(bytes);
}

SDL_GPUSamplerAddressMode wrap(fastgltf::Wrap value) {
    switch(value) {
    case fastgltf::Wrap::Repeat: return SDL_GPU_SAMPLERADDRESSMODE_REPEAT;
    case fastgltf::Wrap::MirroredRepeat: return SDL_GPU_SAMPLERADDRESSMODE_MIRRORED_REPEAT;
    case fastgltf::Wrap::ClampToEdge: return SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE;
    }
    throw std::runtime_error("Invalid texture wrap mode");
}
MaterialData material_data(const fastgltf::Asset& asset,const fastgltf::Material* material) {
    MaterialData result;
    auto& s=result.sampler;
    s.min_filter=s.mag_filter=SDL_GPU_FILTER_LINEAR;
    s.mipmap_mode=SDL_GPU_SAMPLERMIPMAPMODE_LINEAR;
    s.address_mode_u=s.address_mode_v=s.address_mode_w=SDL_GPU_SAMPLERADDRESSMODE_REPEAT;
    if(!material) return result;
    const auto& factor=material->pbrData.baseColorFactor;
    result.base_color={factor[0],factor[1],factor[2],factor[3]};
    result.metallic=material->pbrData.metallicFactor;
    result.roughness=material->pbrData.roughnessFactor;
    result.emission={material->emissiveFactor[0],material->emissiveFactor[1],material->emissiveFactor[2]};
    check(std::isfinite(result.metallic) && result.metallic>=0 && result.metallic<=1 &&
          std::isfinite(result.roughness) && result.roughness>=0 && result.roughness<=1 &&
          std::isfinite(result.emission.x) && std::isfinite(result.emission.y) && std::isfinite(result.emission.z) &&
          result.emission.x>=0 && result.emission.y>=0 && result.emission.z>=0,"Invalid PBR material factors");
    if(material->normalTexture) {
        result.normal_scale=material->normalTexture->scale;
        check(std::isfinite(result.normal_scale) && result.normal_scale>=0,"Invalid normal map scale");
        result.normal_image=material->normalTexture->textureIndex;
    }
    result.unlit=material->unlit;
    result.alpha_mode=material->alphaMode==fastgltf::AlphaMode::Mask ? 1 :
                      material->alphaMode==fastgltf::AlphaMode::Blend ? 2 : 0;
    result.alpha_cutoff=material->alphaCutoff;
    check(std::isfinite(result.alpha_cutoff) && result.alpha_cutoff>=0,"Invalid alpha cutoff");
    if(material->pbrData.baseColorTexture) {
        result.mipmaps=true;
        const auto& texture=asset.textures.at(material->pbrData.baseColorTexture->textureIndex);
        if(texture.samplerIndex) {
            const auto& sampler=asset.samplers.at(*texture.samplerIndex);
            s.address_mode_u=wrap(sampler.wrapS); s.address_mode_v=wrap(sampler.wrapT);
            const auto min=sampler.minFilter.value_or(fastgltf::Filter::LinearMipMapLinear);
            const auto mag=sampler.magFilter.value_or(fastgltf::Filter::Linear);
            check(min==fastgltf::Filter::Nearest || min==fastgltf::Filter::Linear ||
                  min==fastgltf::Filter::NearestMipMapNearest || min==fastgltf::Filter::LinearMipMapNearest ||
                  min==fastgltf::Filter::NearestMipMapLinear || min==fastgltf::Filter::LinearMipMapLinear,
                  "Invalid minification filter");
            check(mag==fastgltf::Filter::Nearest || mag==fastgltf::Filter::Linear,"Invalid magnification filter");
            s.mag_filter=mag==fastgltf::Filter::Nearest ? SDL_GPU_FILTER_NEAREST : SDL_GPU_FILTER_LINEAR;
            s.min_filter=(min==fastgltf::Filter::Nearest || min==fastgltf::Filter::NearestMipMapNearest ||
                          min==fastgltf::Filter::NearestMipMapLinear) ? SDL_GPU_FILTER_NEAREST : SDL_GPU_FILTER_LINEAR;
            result.mipmaps=min!=fastgltf::Filter::Nearest && min!=fastgltf::Filter::Linear;
            s.mipmap_mode=(min==fastgltf::Filter::NearestMipMapNearest || min==fastgltf::Filter::LinearMipMapNearest) ?
                          SDL_GPU_SAMPLERMIPMAPMODE_NEAREST : SDL_GPU_SAMPLERMIPMAPMODE_LINEAR;
        }
    }
    s.max_lod=result.mipmaps ? 32.f : 0.f;
    return result;
}
}
MeshData LoadSprite(const std::filesystem::path& root,const Json& asset) {
    ReadSpriteAssets(Json::array({asset}));
    const auto folder=std::filesystem::canonical(root/"assets");
    check(folder==std::filesystem::canonical(root)/"assets","Sprite assets directory must stay inside the project");
    const auto file=std::filesystem::canonical(root/std::filesystem::u8path(asset.at("texture").get<std::string>()));
    const auto local=file.lexically_relative(folder);
    check(!local.empty() && *local.begin()!=".." && !local.is_absolute(),"Sprite texture escapes assets directory");
    const auto length=std::filesystem::file_size(file);
    check(length && length<=image_limit,"Encoded texture exceeds 64 MiB or is empty");
    std::vector<std::byte> bytes(length); std::ifstream input(file,std::ios::binary);
    check(bool(input.read(reinterpret_cast<char*>(bytes.data()),length)),"Cannot read sprite texture");
    auto image=decode_pixels(bytes);
    const uint32_t columns=asset.at("columns"),rows=asset.at("rows");
    check(image.width%columns==0 && image.height%rows==0,"Sprite grid must divide texture dimensions exactly");
    const float width=asset.at("width"),height=asset.at("height"),px=asset.at("pivot")[0],py=asset.at("pivot")[1];
    const float left=-px*width,right=(1-px)*width,bottom=-py*height,top=(1-py)*height;
    MeshData mesh;
    mesh.minimum={left,bottom,0}; mesh.maximum={right,top,0};
    mesh.vertices={{left,bottom,0,1,1,1,1,0,1},{right,bottom,0,1,1,1,1,1,1},
                   {right,top,0,1,1,1,1,1,0},{left,top,0,1,1,1,1,0,0}};
    mesh.indices={0,1,2,0,2,3};
    mesh.images.push_back(std::move(image));
    MaterialData material; material.unlit=true; material.alpha_mode=2;
    auto& sampler=material.sampler;
    sampler.min_filter=sampler.mag_filter=asset.at("filter")=="nearest" ? SDL_GPU_FILTER_NEAREST : SDL_GPU_FILTER_LINEAR;
    sampler.mipmap_mode=SDL_GPU_SAMPLERMIPMAPMODE_NEAREST;
    sampler.address_mode_u=sampler.address_mode_v=sampler.address_mode_w=SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE;
    mesh.materials.push_back(material);
    mesh.parts.push_back({0,6,0,glm::vec3((left+right)/2,(bottom+top)/2,0)});
    return mesh;
}
MeshData LoadTilemap(const std::filesystem::path& root,const Json& tilemap,const Json& sprite_asset) {
    const auto base=LoadSprite(root,sprite_asset);
    const int width=tilemap.at("width"), height=tilemap.at("height");
    const auto& tiles=tilemap.at("tiles");
    check(tiles.is_array() && tiles.size()==static_cast<std::size_t>(width*height),"Invalid tilemap tiles");
    const int columns=sprite_asset.at("columns"), rows=sprite_asset.at("rows");
    const float tile_width=tilemap.at("tile_width"), tile_height=tilemap.at("tile_height");
    MeshData mesh=base; mesh.vertices.clear(); mesh.indices.clear(); mesh.parts.clear();
    bool any=false; float minimum_x=std::numeric_limits<float>::max(), minimum_y=std::numeric_limits<float>::max();
    float maximum_x=std::numeric_limits<float>::lowest(), maximum_y=std::numeric_limits<float>::lowest();
    for(int y=0;y<height;++y) for(int x=0;x<width;++x) {
        const int tile=tiles.at(static_cast<std::size_t>(y*width+x)); if(tile<0) continue;
        check(tile<columns*rows,"Tilemap tile index is outside its sprite atlas");
        const float left=x*tile_width, right=left+tile_width, bottom=-(y+1)*tile_height, top=-y*tile_height;
        const float u=1.f/columns, v=1.f/rows, u0=(tile%columns)*u, v0=(tile/columns)*v;
        const uint32_t first=static_cast<uint32_t>(mesh.vertices.size());
        mesh.vertices.push_back({left,bottom,0,1,1,1,1,u0,v0+v});
        mesh.vertices.push_back({right,bottom,0,1,1,1,1,u0+u,v0+v});
        mesh.vertices.push_back({right,top,0,1,1,1,1,u0+u,v0});
        mesh.vertices.push_back({left,top,0,1,1,1,1,u0,v0});
        mesh.indices.insert(mesh.indices.end(),{first,first+1,first+2,first,first+2,first+3});
        any=true; minimum_x=std::min(minimum_x,left); minimum_y=std::min(minimum_y,bottom);
        maximum_x=std::max(maximum_x,right); maximum_y=std::max(maximum_y,top);
    }
    if(!any) { mesh.vertices={{0,0,0,1,1,1,1,0,0},{0,0,0,1,1,1,1,0,0},{0,0,0,1,1,1,1,0,0}}; mesh.indices={0,1,2}; minimum_x=minimum_y=maximum_x=maximum_y=0; }
    mesh.minimum={minimum_x,minimum_y,0}; mesh.maximum={maximum_x,maximum_y,0};
    mesh.parts.push_back({0,static_cast<uint32_t>(mesh.indices.size()),0,glm::vec3((minimum_x+maximum_x)*.5f,(minimum_y+maximum_y)*.5f,0)});
    return mesh;
}
MeshData LoadRuntimeTexture(const std::filesystem::path& root,const std::string& relative,const std::string& filter) {
    check(!relative.empty() && relative.find('\\')==std::string::npos,"Runtime texture path must use forward slashes");
    const auto project=std::filesystem::canonical(root);
    const auto file=std::filesystem::canonical(root/std::filesystem::u8path(relative));
    const auto local=file.lexically_relative(project);
    check(!local.empty() && !local.is_absolute() && *local.begin()!="..","Runtime texture escapes the project");
    const auto length=std::filesystem::file_size(file);
    check(length && length<=image_limit,"Runtime texture exceeds 64 MiB or is empty");
    std::vector<std::byte> bytes(length); std::ifstream input(file,std::ios::binary);
    check(bool(input.read(reinterpret_cast<char*>(bytes.data()),length)),"Cannot read runtime texture");
    MeshData mesh;
    mesh.images.push_back(decode_pixels(bytes));
    // Runtime-only textures are uploaded through the same GPU resource path as
    // sprites.  A tiny hidden quad keeps the resource valid for SDL_GPU while
    // no scene entity references this key until a future texture binding does.
    mesh.vertices={{-.001f,-.001f,0,1,1,1,1,0,1},{.001f,-.001f,0,1,1,1,1,1,1},
                   {.001f,.001f,0,1,1,1,1,1,0},{-.001f,.001f,0,1,1,1,1,0,0}};
    mesh.indices={0,1,2,0,2,3}; mesh.minimum={-.001,-.001,0}; mesh.maximum={.001,.001,0};
    MaterialData material; material.unlit=true; material.alpha_mode=2;
    material.sampler.min_filter=material.sampler.mag_filter=filter=="nearest" ? SDL_GPU_FILTER_NEAREST : SDL_GPU_FILTER_LINEAR;
    material.sampler.mipmap_mode=SDL_GPU_SAMPLERMIPMAPMODE_NEAREST;
    material.sampler.address_mode_u=material.sampler.address_mode_v=material.sampler.address_mode_w=SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE;
    mesh.materials.push_back(material); mesh.parts.push_back({0,6,0,{0,0,0}});
    return mesh;
}
MeshData LoadGltf(const std::filesystem::path& path) {
    fastgltf::Parser parser(fastgltf::Extensions::KHR_materials_unlit | fastgltf::Extensions::KHR_texture_transform);
    auto data=fastgltf::GltfDataBuffer::FromPath(path);
    if(data.error()!=fastgltf::Error::None) throw std::runtime_error("Cannot read glTF: "+path.string());
    auto result=parser.loadGltf(data.get(),path.parent_path(),fastgltf::Options::LoadExternalBuffers | fastgltf::Options::GenerateMeshIndices);
    if(result.error()!=fastgltf::Error::None)
        throw std::runtime_error("Invalid glTF: "+std::string(fastgltf::getErrorMessage(result.error())));
    auto& asset=result.get();
    geometry_buffers(asset);
    if(auto error=fastgltf::validate(asset);error!=fastgltf::Error::None)
        throw std::runtime_error("Invalid glTF structure: "+std::string(fastgltf::getErrorMessage(error)));
    check(!asset.scenes.empty(),"glTF has no scene");
    MeshData mesh;
    if(!asset.skins.empty() || !asset.animations.empty()) mesh.animation=AnimationAsset::Load(path);
    const auto rest=mesh.animation ? mesh.animation->rest_pose() : AnimationPose{};
    mesh.images.emplace_back(); // White fallback also serves untextured primitives.
    mesh.minimum=Vec3(std::numeric_limits<double>::max());
    mesh.maximum=Vec3(std::numeric_limits<double>::lowest());
    std::map<size_t,size_t> materials,images;
    size_t decoded_bytes=4;
    fastgltf::iterateSceneNodes(asset,asset.defaultScene.value_or(0),fastgltf::math::fmat4x4(),
        [&](fastgltf::Node& node, fastgltf::math::fmat4x4 transform) {
        if(!node.meshIndex) return;
        for(auto& primitive:asset.meshes[*node.meshIndex].primitives) {
            check(primitive.type==fastgltf::PrimitiveType::Triangles,"Only triangle primitives are currently supported");
            const auto* attribute=primitive.findAttribute("POSITION");
            check(attribute!=primitive.attributes.end(),"Mesh has no POSITION accessor");
            const auto* material=primitive.materialIndex ? &asset.materials.at(*primitive.materialIndex) : nullptr;
            const auto key=primitive.materialIndex.value_or(asset.materials.size());
            if(!materials.contains(key)) {
                auto value=material_data(asset,material);
                if(material && material->pbrData.baseColorTexture) {
                    const auto& texture=asset.textures.at(material->pbrData.baseColorTexture->textureIndex);
                    check(texture.imageIndex.has_value(),"Base-color texture has no supported PNG/JPEG source");
                    const auto image=*texture.imageIndex;
                    if(!images.contains(image)) {
                        auto decoded=decode_image(asset,image,path.parent_path());
                        decoded_bytes+=decoded.rgba.size();
                        check(decoded_bytes<=decoded_limit,"Model decoded texture budget exceeds 256 MiB");
                        images[image]=mesh.images.size(); mesh.images.push_back(std::move(decoded));
                    }
                    value.image=images.at(image);
                }
                if(material && material->normalTexture) {
                    const auto& texture=asset.textures.at(material->normalTexture->textureIndex);
                    check(texture.imageIndex.has_value(),"Normal texture has no supported PNG/JPEG source");
                    const auto image=*texture.imageIndex;
                    if(!images.contains(image)) {
                        auto decoded=decode_image(asset,image,path.parent_path());
                        decoded_bytes+=decoded.rgba.size();
                        check(decoded_bytes<=decoded_limit,"Model decoded texture budget exceeds 256 MiB");
                        images[image]=mesh.images.size(); mesh.images.push_back(std::move(decoded));
                    }
                    value.normal_image=images.at(image);
                }
                materials[key]=mesh.materials.size(); mesh.materials.push_back(value);
            }
            MeshPart part; part.first=static_cast<uint32_t>(mesh.indices.size()); part.material=materials.at(key);
            part.node=static_cast<size_t>(&node-asset.nodes.data());
            part.skin=node.skinIndex ? static_cast<int>(*node.skinIndex) : -1;
            check(primitive.targets.empty(),"Morph targets are not supported by the animation renderer");
            glm::vec4 color(1.f);
            if(material) {
                const auto& c=material->pbrData.baseColorFactor; color={c[0],c[1],c[2],c[3]};
            }
            for(int i=0;i<4;++i) check(std::isfinite(color[i]) && color[i]>=0 && color[i]<=1,"Invalid base-color factor");
            const auto& accessor=asset.accessors.at(attribute->accessorIndex);
            check(accessor.count<=1000000,"Mesh vertex limit exceeded");
            check(accessor.type==fastgltf::AccessorType::Vec3,"POSITION must be VEC3");
            std::vector<Vertex> vertices;
            std::vector<DeformVertex> deformation;
            vertices.reserve(accessor.count);
            Vec3 minimum(std::numeric_limits<double>::max()),maximum(std::numeric_limits<double>::lowest());
            fastgltf::iterateAccessor<fastgltf::math::fvec3>(asset,accessor,[&](fastgltf::math::fvec3 p) {
                auto world=transform*fastgltf::math::fvec4(p[0],p[1],p[2],1.0f);
                if(part.skin>=0) world={p[0],p[1],p[2],1.f};
                if(mesh.animation) deformation.push_back({glm::vec3(p[0],p[1],p[2])});
                Vec3 v=finite(Vec3{world[0],world[1],world[2]});
                minimum=glm::min(minimum,v); maximum=glm::max(maximum,v);
                vertices.push_back({float(v.x),float(v.y),float(v.z),1,1,1,1});
            });
            if(part.skin>=0) {
                size_t sets=0;
                for(;sets<4;++sets) {
                    const auto* joints=primitive.findAttribute("JOINTS_"+std::to_string(sets));
                    const auto* weights=primitive.findAttribute("WEIGHTS_"+std::to_string(sets));
                    if(joints==primitive.attributes.end() && weights==primitive.attributes.end()) break;
                    check(joints!=primitive.attributes.end() && weights!=primitive.attributes.end(),"Skin requires matching JOINTS and WEIGHTS accessors");
                    const auto& j=asset.accessors.at(joints->accessorIndex); const auto& w=asset.accessors.at(weights->accessorIndex);
                    check(j.count==vertices.size() && w.count==vertices.size() && j.type==fastgltf::AccessorType::Vec4 && w.type==fastgltf::AccessorType::Vec4,
                          "Invalid skin accessor count or shape");
                    check(!j.normalized && (j.componentType==fastgltf::ComponentType::UnsignedByte || j.componentType==fastgltf::ComponentType::UnsignedShort),"Invalid skin joint component type");
                    check((w.componentType==fastgltf::ComponentType::Float && !w.normalized) ||
                          ((w.componentType==fastgltf::ComponentType::UnsignedByte || w.componentType==fastgltf::ComponentType::UnsignedShort) && w.normalized),"Invalid skin weight component type");
                    fastgltf::iterateAccessorWithIndex<glm::uvec4>(asset,j,[&](auto v,size_t i) {
                        for(size_t k=0;k<4;++k) deformation[i].weights[sets*4+k].joint=v[k];
                    });
                    fastgltf::iterateAccessorWithIndex<glm::vec4>(asset,w,[&](auto v,size_t i) {
                        for(size_t k=0;k<4;++k) deformation[i].weights[sets*4+k].weight=v[k];
                    });
                }
                check(sets>0,"Skinned primitive requires JOINTS_0 and WEIGHTS_0");
                for(const auto& attr:primitive.attributes) if(attr.name.starts_with("JOINTS_") || attr.name.starts_with("WEIGHTS_")) {
                    bool found=false;
                    for(size_t set=0;set<sets;++set) found|=std::string_view(attr.name)=="JOINTS_"+std::to_string(set) || std::string_view(attr.name)=="WEIGHTS_"+std::to_string(set);
                    check(found,"Skin supports contiguous JOINTS/WEIGHTS sets 0 through 3");
                }
                minimum=Vec3(std::numeric_limits<double>::max()); maximum=Vec3(std::numeric_limits<double>::lowest());
                for(size_t i=0;i<vertices.size();++i) {
                    auto& binding=deformation[i]; binding.count=sets*4;
                    const auto v=SkinPosition(rest,part.skin,binding.position,{binding.weights.data(),binding.count});
                    vertices[i].x=v.x; vertices[i].y=v.y; vertices[i].z=v.z;
                    minimum=glm::min(minimum,Vec3(v)); maximum=glm::max(maximum,Vec3(v));
                }
            }
            if(material && material->pbrData.baseColorTexture) {
                const auto& tex=*material->pbrData.baseColorTexture;
                auto channel=tex.texCoordIndex;
                if(tex.transform && tex.transform->texCoordIndex) channel=*tex.transform->texCoordIndex;
                const auto* uv=primitive.findAttribute("TEXCOORD_"+std::to_string(channel));
                check(uv!=primitive.attributes.end(),"Textured primitive is missing its TEXCOORD accessor");
                const auto& a=asset.accessors.at(uv->accessorIndex);
                check(a.count==vertices.size() && a.type==fastgltf::AccessorType::Vec2,"Invalid TEXCOORD accessor");
                fastgltf::iterateAccessorWithIndex<fastgltf::math::fvec2>(asset,a,[&](auto p,size_t i) {
                    if(tex.transform) {
                        const auto& t=*tex.transform;
                        float u=p[0]*t.uvScale[0],v=p[1]*t.uvScale[1];
                        p={t.uvOffset[0]+std::cos(t.rotation)*u-std::sin(t.rotation)*v,
                           t.uvOffset[1]+std::sin(t.rotation)*u+std::cos(t.rotation)*v};
                    }
                    check(std::isfinite(p[0]) && std::isfinite(p[1]),"Non-finite texture coordinate");
                    vertices[i].u=p[0]; vertices[i].v=p[1];
                });
            }
            if(const auto* colors=primitive.findAttribute("COLOR_0");colors!=primitive.attributes.end()) {
                const auto& a=asset.accessors.at(colors->accessorIndex);
                check(a.count==vertices.size(),"COLOR_0 count differs from POSITION");
                auto apply=[&](glm::vec4 c,size_t i) {
                    for(int n=0;n<4;++n) check(std::isfinite(c[n]) && c[n]>=0 && c[n]<=1,"Invalid vertex color");
                    auto& v=vertices[i]; v.r*=c.r; v.g*=c.g; v.b*=c.b; v.a*=c.a;
                };
                if(a.type==fastgltf::AccessorType::Vec3)
                    fastgltf::iterateAccessorWithIndex<glm::vec3>(asset,a,[&](auto c,size_t i){apply(glm::vec4(c,1),i);});
                else if(a.type==fastgltf::AccessorType::Vec4)
                    fastgltf::iterateAccessorWithIndex<glm::vec4>(asset,a,apply);
                else throw std::runtime_error("COLOR_0 must be VEC3 or VEC4");
            }
            check(primitive.indicesAccessor.has_value(),"Mesh has no indices");
            const auto& indices=asset.accessors.at(*primitive.indicesAccessor);
            check(indices.count && indices.count%3==0 && indices.count<=index_limit-mesh.indices.size(),
                  "Invalid triangle count or mesh exceeds 3000000 expanded vertices");
            check(!mesh.animation || indices.count<=500000-mesh.vertices.size(),"Animated model exceeds 500000 expanded vertices");
            std::vector<uint32_t> local_indices;
            local_indices.reserve(indices.count);
            fastgltf::iterateAccessor<uint32_t>(asset,indices,[&](uint32_t index) {
                check(index<vertices.size(),"Mesh index out of bounds"); local_indices.push_back(index);
            });
            const glm::vec3 light=glm::normalize(glm::vec3(.3f,.8f,.5f));
            for(size_t i=0;i<local_indices.size();i+=3) {
                auto a=vertices[local_indices[i]],b=vertices[local_indices[i+1]],c=vertices[local_indices[i+2]];
                auto normal=glm::cross(glm::vec3(b.x-a.x,b.y-a.y,b.z-a.z),glm::vec3(c.x-a.x,c.y-a.y,c.z-a.z));
                // shortcut: fixed face lighting; replace when dynamic light/PBR nodes are implemented.
                const auto n=glm::length(normal)>0 ? glm::normalize(normal) : glm::vec3(0,0,1);
                float shade=.35f+.65f*std::max(0.f,glm::dot(n,light));
                for(size_t k=0;k<3;++k) {
                    auto v=vertices[local_indices[i+k]];
                    v.shade=shade;
                    v.nx=n.x; v.ny=n.y; v.nz=n.z;
                    mesh.indices.push_back(static_cast<uint32_t>(mesh.vertices.size())); mesh.vertices.push_back(v);
                    if(mesh.animation) mesh.deformation.push_back(deformation[local_indices[i+k]]);
                }
            }
            part.count=static_cast<uint32_t>(mesh.indices.size())-part.first;
            part.center=glm::vec3((minimum+maximum)*.5); mesh.parts.push_back(part);
            mesh.minimum=glm::min(mesh.minimum,minimum); mesh.maximum=glm::max(mesh.maximum,maximum);
        }
    });
    check(!mesh.vertices.empty() && !mesh.indices.empty(),"Model has no valid triangles");
    return mesh;
}
}
