#include "display.hpp"
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/type_ptr.hpp>
#include <cstring>
#include <fstream>
#include <limits>

namespace rt {
static void require(bool okay) { if(!okay) throw std::runtime_error(SDL_GetError()); }
static SDL_GPUShader* shader(SDL_GPUDevice* gpu, const char* filename, SDL_GPUShaderStage stage, uint32_t uniforms, uint32_t samplers=0) {
    std::filesystem::path path=std::filesystem::u8path(SDL_GetBasePath())/"shaders"/filename;
    auto encoded=path.u8string();
    size_t length=0; void* bytes=SDL_LoadFile(reinterpret_cast<const char*>(encoded.c_str()),&length);
    if(!bytes) throw std::runtime_error("Cannot read shader: "+path.string());
    SDL_GPUShaderCreateInfo info{};
    info.code_size=length; info.code=static_cast<Uint8*>(bytes); info.entrypoint="main";
    info.format=SDL_GPU_SHADERFORMAT_SPIRV; info.stage=stage; info.num_uniform_buffers=uniforms;
    info.num_samplers=samplers;
    auto* result=SDL_CreateGPUShader(gpu,&info); SDL_free(bytes); require(result!=nullptr); return result;
}
Display::Display() {
    require(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS));
    window=SDL_CreateWindow("Node_Engine - Game View",960,640,SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY);
    require(window!=nullptr);
    gpu=SDL_CreateGPUDevice(SDL_GPU_SHADERFORMAT_SPIRV,false,nullptr); require(gpu!=nullptr);
    require(SDL_ClaimWindowForGPUDevice(gpu,window));
    require(SDL_SetGPUSwapchainParameters(gpu,window,SDL_GPU_SWAPCHAINCOMPOSITION_SDR_LINEAR,SDL_GPU_PRESENTMODE_VSYNC));
    auto* vs=shader(gpu,"Mesh.vert.spv",SDL_GPU_SHADERSTAGE_VERTEX,1);
    auto* fs=shader(gpu,"Mesh.frag.spv",SDL_GPU_SHADERSTAGE_FRAGMENT,1,2);
    SDL_GPUVertexBufferDescription vb{}; vb.slot=0; vb.pitch=sizeof(Vertex); vb.input_rate=SDL_GPU_VERTEXINPUTRATE_VERTEX;
    SDL_GPUVertexAttribute attrs[5]{};
    attrs[0].location=0; attrs[0].buffer_slot=0; attrs[0].format=SDL_GPU_VERTEXELEMENTFORMAT_FLOAT3; attrs[0].offset=0;
    attrs[1].location=1; attrs[1].buffer_slot=0; attrs[1].format=SDL_GPU_VERTEXELEMENTFORMAT_FLOAT4; attrs[1].offset=12;
    attrs[2].location=2; attrs[2].buffer_slot=0; attrs[2].format=SDL_GPU_VERTEXELEMENTFORMAT_FLOAT2; attrs[2].offset=28;
    attrs[3].location=3; attrs[3].buffer_slot=0; attrs[3].format=SDL_GPU_VERTEXELEMENTFORMAT_FLOAT; attrs[3].offset=36;
    attrs[4].location=4; attrs[4].buffer_slot=0; attrs[4].format=SDL_GPU_VERTEXELEMENTFORMAT_FLOAT3; attrs[4].offset=40;
    SDL_GPUColorTargetDescription target_desc{}; target_desc.format=SDL_GetGPUSwapchainTextureFormat(gpu,window);
    SDL_GPUGraphicsPipelineCreateInfo info{};
    info.vertex_shader=vs; info.fragment_shader=fs;
    info.vertex_input_state={&vb,1,attrs,5};
    info.primitive_type=SDL_GPU_PRIMITIVETYPE_TRIANGLELIST;
    info.rasterizer_state.fill_mode=SDL_GPU_FILLMODE_FILL;
    info.rasterizer_state.cull_mode=SDL_GPU_CULLMODE_NONE;
    info.multisample_state.sample_count=SDL_GPU_SAMPLECOUNT_1;
    info.depth_stencil_state.enable_depth_test=true; info.depth_stencil_state.enable_depth_write=true;
    info.depth_stencil_state.compare_op=SDL_GPU_COMPAREOP_LESS_OR_EQUAL;
    info.target_info.color_target_descriptions=&target_desc; info.target_info.num_color_targets=1;
    info.target_info.has_depth_stencil_target=true; info.target_info.depth_stencil_format=SDL_GPU_TEXTUREFORMAT_D32_FLOAT;
    pipeline=SDL_CreateGPUGraphicsPipeline(gpu,&info);
    info.depth_stencil_state.enable_depth_write=false;
    auto& blend=target_desc.blend_state;
    blend.enable_blend=true;
    blend.src_color_blendfactor=SDL_GPU_BLENDFACTOR_SRC_ALPHA;
    blend.dst_color_blendfactor=SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;
    blend.color_blend_op=SDL_GPU_BLENDOP_ADD;
    blend.src_alpha_blendfactor=SDL_GPU_BLENDFACTOR_ONE;
    blend.dst_alpha_blendfactor=SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;
    blend.alpha_blend_op=SDL_GPU_BLENDOP_ADD;
    blend_pipeline=SDL_CreateGPUGraphicsPipeline(gpu,&info);
    SDL_ReleaseGPUShader(gpu,vs); SDL_ReleaseGPUShader(gpu,fs); require(pipeline && blend_pipeline);
}
Display::~Display() {
    if(gpu) {
        SDL_WaitForGPUIdle(gpu);
        ui_renderer.reset();
        if(depth) SDL_ReleaseGPUTexture(gpu,depth);
        deformations.clear(); meshes.clear();
        if(pipeline) SDL_ReleaseGPUGraphicsPipeline(gpu,pipeline);
        if(blend_pipeline) SDL_ReleaseGPUGraphicsPipeline(gpu,blend_pipeline);
        if(window) SDL_ReleaseWindowFromGPUDevice(gpu,window);
        SDL_DestroyGPUDevice(gpu);
    }
    if(window) SDL_DestroyWindow(window);
    SDL_Quit();
}
static std::shared_ptr<GpuMesh> upload_mesh(SDL_GPUDevice* gpu,const MeshData& mesh) {
    auto result=std::make_shared<GpuMesh>(); result->gpu=gpu;
    const auto vbytes=static_cast<Uint32>(mesh.vertices.size()*sizeof(Vertex));
    const auto ibytes=static_cast<Uint32>(mesh.indices.size()*sizeof(uint32_t));
    SDL_GPUBufferCreateInfo vi{SDL_GPU_BUFFERUSAGE_VERTEX,vbytes,0}, ii{SDL_GPU_BUFFERUSAGE_INDEX,ibytes,0};
    result->vertex=SDL_CreateGPUBuffer(gpu,&vi); result->index=SDL_CreateGPUBuffer(gpu,&ii);
    require(result->vertex && result->index);
    SDL_GPUTransferBufferCreateInfo ti{SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD,vbytes+ibytes,0};
    auto* transfer=SDL_CreateGPUTransferBuffer(gpu,&ti); require(transfer!=nullptr);
    auto release_transfer=[gpu](SDL_GPUTransferBuffer* value) { SDL_ReleaseGPUTransferBuffer(gpu,value); };
    std::unique_ptr<SDL_GPUTransferBuffer,decltype(release_transfer)> owner(transfer,release_transfer);
    auto* memory=static_cast<char*>(SDL_MapGPUTransferBuffer(gpu,transfer,false)); require(memory!=nullptr);
    std::memcpy(memory,mesh.vertices.data(),vbytes); std::memcpy(memory+vbytes,mesh.indices.data(),ibytes);
    SDL_UnmapGPUTransferBuffer(gpu,transfer);
    auto* command=SDL_AcquireGPUCommandBuffer(gpu); require(command!=nullptr);
    auto cancel=[](SDL_GPUCommandBuffer* value) { SDL_CancelGPUCommandBuffer(value); };
    std::unique_ptr<SDL_GPUCommandBuffer,decltype(cancel)> command_owner(command,cancel);
    auto* copy=SDL_BeginGPUCopyPass(command);
    require(copy!=nullptr);
    SDL_GPUTransferBufferLocation vl{transfer,0}, il{transfer,vbytes};
    SDL_GPUBufferRegion vr{result->vertex,0,vbytes}, ir{result->index,0,ibytes};
    SDL_UploadToGPUBuffer(copy,&vl,&vr,false); SDL_UploadToGPUBuffer(copy,&il,&ir,false);
    SDL_EndGPUCopyPass(copy); require(SDL_SubmitGPUCommandBuffer(command_owner.release()));
    for(size_t i=0;i<mesh.images.size();++i) {
        const auto& image=mesh.images[i];
        const bool mips=std::any_of(mesh.materials.begin(),mesh.materials.end(),[&](const auto& m){return (m.image==i || m.normal_image==i) && m.mipmaps;});
        const bool normal=std::any_of(mesh.materials.begin(),mesh.materials.end(),[&](const auto& m){return m.normal_image==i;});
        SDL_GPUTextureCreateInfo info{};
        info.type=SDL_GPU_TEXTURETYPE_2D; info.format=normal ? SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM : SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM_SRGB;
        info.usage=SDL_GPU_TEXTUREUSAGE_SAMPLER | (mips ? SDL_GPU_TEXTUREUSAGE_COLOR_TARGET : 0);
        info.width=image.width; info.height=image.height; info.layer_count_or_depth=1;
        info.num_levels=mips ? uint32_t(std::floor(std::log2(std::max(image.width,image.height))))+1 : 1;
        info.sample_count=SDL_GPU_SAMPLECOUNT_1;
        auto* texture=SDL_CreateGPUTexture(gpu,&info); require(texture!=nullptr);
        result->textures.push_back(texture);
        result->texels.emplace_back(1.f/image.width,1.f/image.height);
        SDL_GPUTransferBufferCreateInfo upload_info{SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD,Uint32(image.rgba.size()),0};
        std::unique_ptr<SDL_GPUTransferBuffer,decltype(release_transfer)> upload(SDL_CreateGPUTransferBuffer(gpu,&upload_info),release_transfer);
        require(upload!=nullptr);
        auto* pixels=SDL_MapGPUTransferBuffer(gpu,upload.get(),false); require(pixels!=nullptr);
        std::memcpy(pixels,image.rgba.data(),image.rgba.size()); SDL_UnmapGPUTransferBuffer(gpu,upload.get());
        std::unique_ptr<SDL_GPUCommandBuffer,decltype(cancel)> cmd(SDL_AcquireGPUCommandBuffer(gpu),cancel);
        require(cmd!=nullptr);
        auto* copy_texture=SDL_BeginGPUCopyPass(cmd.get()); require(copy_texture!=nullptr);
        SDL_GPUTextureTransferInfo source{}; source.transfer_buffer=upload.get();
        source.pixels_per_row=image.width; source.rows_per_layer=image.height;
        SDL_GPUTextureRegion region{}; region.texture=texture; region.w=image.width; region.h=image.height; region.d=1;
        SDL_UploadToGPUTexture(copy_texture,&source,&region,false); SDL_EndGPUCopyPass(copy_texture);
        if(info.num_levels>1) SDL_GenerateMipmapsForGPUTexture(cmd.get(),texture);
        require(SDL_SubmitGPUCommandBuffer(cmd.release()));
    }
    for(const auto& material:mesh.materials) {
        auto* sampler=SDL_CreateGPUSampler(gpu,&material.sampler); require(sampler!=nullptr);
        result->samplers.push_back(sampler);
        auto* normal_sampler=SDL_CreateGPUSampler(gpu,&material.sampler); require(normal_sampler!=nullptr);
        result->normal_samplers.push_back(normal_sampler);
    }
    result->parts=mesh.parts; result->materials=mesh.materials;
    result->minimum=mesh.minimum; result->maximum=mesh.maximum;
    result->animation=mesh.animation;
    if(mesh.animation) { result->vertices=mesh.vertices; result->deformation=mesh.deformation; }
    return result;
}
void Display::upload(const std::map<std::string,MeshData>& data,const Ctx& ctx) {
    commit_upload(prepare_upload(data)); frame_scene(ctx);
}
std::map<std::string,std::shared_ptr<GpuMesh>> Display::prepare_upload(const std::map<std::string,MeshData>& data) {
    std::map<std::string,std::shared_ptr<GpuMesh>> prepared;
    for(const auto& [key,mesh]:data) prepared.emplace(key,upload_mesh(gpu,mesh));
    require(SDL_WaitForGPUIdle(gpu));
    return prepared;
}
void Display::commit_upload(std::map<std::string,std::shared_ptr<GpuMesh>>&& prepared) noexcept {
    deformations.clear(); meshes.swap(prepared);
    needs_initial_frame=true; auto_frame=true;
}
void Display::frame_scene(const Ctx& ctx) {
    auto_frame=true;
    const auto entities=RenderEntities(ctx);
    if(entities.empty()) return;
    Vec3 minimum(std::numeric_limits<double>::max()), maximum(std::numeric_limits<double>::lowest());
    bool any=false;
    for(const auto& instance:entities) {
        const auto& mesh=*meshes.at(instance.mesh);
        auto matrix=instance.matrix;
        for(int corner=0;corner<8;++corner) {
            glm::vec3 local;
            for(int axis=0;axis<3;++axis) local[axis]=float(corner&(1<<axis) ? mesh.maximum[axis] : mesh.minimum[axis]);
            Vec3 world(glm::vec3(matrix*glm::vec4(local,1.f)));
            minimum=glm::min(minimum,world); maximum=glm::max(maximum,world); any=true;
        }
    }
    if(any) {
        needs_initial_frame=false;
        target=(minimum+maximum)*.5;
        int w=960,h=640; SDL_GetWindowSizeInPixels(window,&w,&h);
        const double aspect=double(std::max(w,1))/std::max(h,1);
        const double half_fov=std::atan(std::tan(glm::radians(22.5))*std::min(1.,aspect));
        distance=std::max(1.,glm::length(maximum-minimum)*.5/std::sin(half_fov)*1.15);
    }
}
void Display::screenshot(const std::filesystem::path& path) { capture_path=path; }
void Display::prepare_ui(Ctx& ctx,const std::filesystem::path& root) {
    if(!UiAssets(ctx).empty()) ensure_ui_renderer();
    PrepareUi(ctx,root,ui_renderer.get(),window);
    update_ui(ctx);
}
void Display::ensure_ui_renderer() {
    if(!ui_renderer) ui_renderer=std::make_unique<UiRenderer>(gpu,window,std::filesystem::u8path(SDL_GetBasePath())/"shaders");
}
void Display::update_ui(Ctx& ctx) {
    int w=0,h=0; SDL_GetWindowSizeInPixels(window,&w,&h);
    UpdateUi(ctx,w,h,SDL_GetWindowDisplayScale(window));
}
void Display::validate_checkpoint_resources(const Ctx& ctx) const {
    for(const auto& mesh:SceneMeshes(ctx))
        if(!meshes.contains(mesh)) throw std::runtime_error("Saved mesh is absent from the loaded GPU resource library");
    for(const auto& asset:SpriteAssets(ctx))
        if(!meshes.contains("@sprite:"+asset.at("id").get<std::string>())) throw std::runtime_error("Saved sprite is absent from the loaded GPU resource library");
    for(const auto& entity:RenderEntities(ctx))
        if(!meshes.contains(entity.mesh)) throw std::runtime_error("Saved entity refers to an unavailable GPU resource");
}
void Display::update_animations(const Ctx& ctx) {
    const auto entities=RenderEntities(ctx);
    std::set<std::pair<std::string,std::string>> used;
    for(const auto& entity:entities) {
        const auto mesh=meshes.at(entity.mesh); if(!mesh->animation) continue;
        const auto key=std::make_pair(entity.id,entity.mesh); used.insert(key);
        auto vertices=mesh->vertices; auto parts=mesh->parts;
        const auto pose=EntityAnimationPose(ctx,{entity.id},*mesh->animation);
        for(auto& part:parts) {
            glm::vec3 minimum(std::numeric_limits<float>::max()),maximum(std::numeric_limits<float>::lowest());
            for(size_t i=part.first;i<part.first+part.count;++i) {
                const auto& binding=mesh->deformation[i];
                const auto p=part.skin>=0 ? SkinPosition(pose,part.skin,binding.position,{binding.weights.data(),binding.count}) :
                    glm::vec3(pose.nodes.at(part.node)*glm::vec4(binding.position,1));
                vertices[i].x=p.x; vertices[i].y=p.y; vertices[i].z=p.z;
                minimum=glm::min(minimum,p); maximum=glm::max(maximum,p);
            }
            part.center=(minimum+maximum)*.5f;
            for(size_t i=part.first;i<part.first+part.count;i+=3) {
                auto& a=vertices[i]; auto& b=vertices[i+1]; auto& c=vertices[i+2];
                const auto cross=glm::cross(glm::vec3(b.x-a.x,b.y-a.y,b.z-a.z),glm::vec3(c.x-a.x,c.y-a.y,c.z-a.z));
                const auto n=glm::length(cross)>0 ? glm::normalize(cross) : glm::vec3(0,0,1);
                const float shade=.35f+.65f*std::max(0.f,glm::dot(n,glm::normalize(glm::vec3(.3f,.8f,.5f))));
                a.shade=b.shade=c.shade=shade;
                a.nx=b.nx=c.nx=n.x; a.ny=b.ny=c.ny=n.y; a.nz=b.nz=c.nz=n.z;
            }
        }
        const auto bytes=static_cast<Uint32>(vertices.size()*sizeof(Vertex));
        if(!deformations.contains(key)) {
            auto item=std::make_unique<GpuDeformation>(); item->gpu=gpu; item->mesh=mesh;
            SDL_GPUBufferCreateInfo info{SDL_GPU_BUFFERUSAGE_VERTEX,bytes,0};
            item->vertex=SDL_CreateGPUBuffer(gpu,&info); require(item->vertex!=nullptr);
            SDL_GPUTransferBufferCreateInfo transfer{SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD,bytes,0};
            item->transfer=SDL_CreateGPUTransferBuffer(gpu,&transfer); require(item->transfer!=nullptr);
            deformations.emplace(key,std::move(item));
        }
        auto& item=*deformations.at(key); item.parts=std::move(parts);
        auto* memory=SDL_MapGPUTransferBuffer(gpu,item.transfer,true); require(memory!=nullptr);
        std::memcpy(memory,vertices.data(),bytes); SDL_UnmapGPUTransferBuffer(gpu,item.transfer);
        auto cancel=[](SDL_GPUCommandBuffer* p){SDL_CancelGPUCommandBuffer(p);};
        std::unique_ptr<SDL_GPUCommandBuffer,decltype(cancel)> command(SDL_AcquireGPUCommandBuffer(gpu),cancel);
        require(command!=nullptr); auto* copy=SDL_BeginGPUCopyPass(command.get()); require(copy!=nullptr);
        SDL_GPUTransferBufferLocation source{item.transfer,0}; SDL_GPUBufferRegion destination{item.vertex,0,bytes};
        SDL_UploadToGPUBuffer(copy,&source,&destination,true); SDL_EndGPUCopyPass(copy);
        require(SDL_SubmitGPUCommandBuffer(command.release()));
    }
    std::erase_if(deformations,[&](const auto& item){return !used.contains(item.first);});
}
void Display::render(Ctx& ctx) {
    update_animations(ctx);
    if(auto_frame && needs_initial_frame) frame_scene(ctx);
    auto* command=SDL_AcquireGPUCommandBuffer(gpu); require(command!=nullptr);
    SDL_GPUTexture* swap=nullptr; Uint32 w=0,h=0;
    if(!SDL_WaitAndAcquireGPUSwapchainTexture(command,window,&swap,&w,&h)) {
        SDL_CancelGPUCommandBuffer(command); throw std::runtime_error(SDL_GetError());
    }
    if(!swap || !w || !h) { SDL_SubmitGPUCommandBuffer(command); return; }
    if(w!=width || h!=height) {
        if(depth) SDL_ReleaseGPUTexture(gpu,depth);
        SDL_GPUTextureCreateInfo info{};
        info.type=SDL_GPU_TEXTURETYPE_2D; info.format=SDL_GPU_TEXTUREFORMAT_D32_FLOAT;
        info.usage=SDL_GPU_TEXTUREUSAGE_DEPTH_STENCIL_TARGET;
        info.width=w; info.height=h; info.layer_count_or_depth=1; info.num_levels=1; info.sample_count=SDL_GPU_SAMPLECOUNT_1;
        depth=SDL_CreateGPUTexture(gpu,&info); require(depth!=nullptr); width=w; height=h;
        if(auto_frame) frame_scene(ctx);
    }
    SDL_GPUColorTargetInfo color{}; color.texture=swap;
    // Linear values preserve the existing dark background on the sRGB swapchain.
    color.clear_color={.003333f,.004809f,.007454f,1}; color.load_op=SDL_GPU_LOADOP_CLEAR; color.store_op=SDL_GPU_STOREOP_STORE;
    SDL_GPUDepthStencilTargetInfo depth_info{}; depth_info.texture=depth; depth_info.clear_depth=1.0f;
    depth_info.load_op=SDL_GPU_LOADOP_CLEAR; depth_info.store_op=SDL_GPU_STOREOP_DONT_CARE;
    depth_info.stencil_load_op=SDL_GPU_LOADOP_DONT_CARE; depth_info.stencil_store_op=SDL_GPU_STOREOP_DONT_CARE;
    auto* pass=SDL_BeginGPURenderPass(command,&color,1,&depth_info); require(pass!=nullptr);
    const auto entities=RenderEntities(ctx);
    const bool selected=uses_game_camera(ctx);
    const auto camera=selected ? GameCameraMatrices(ctx,double(w)/h) : std::nullopt;
    if(!entities.empty() && (!selected || camera)) {
        float ry=glm::radians(float(yaw)), rp=glm::radians(float(pitch));
        glm::vec3 center(target);
        glm::vec3 eye=center+float(distance)*glm::vec3(std::sin(ry)*std::cos(rp),std::sin(rp),std::cos(ry)*std::cos(rp));
        auto view=glm::lookAtRH(eye,center,glm::vec3(0,1,0));
        auto projection=glm::perspectiveRH_ZO(glm::radians(45.f),float(w)/float(h),0.01f,float(distance*30+100));
        if(camera) { view=camera->first; projection=camera->second; }
        // Up to four directional/point lights are uploaded to the compact mesh
        // material UBO. Clustered-light authoring remains a later scale-up.
        glm::vec4 pbr(-1.f,1.f,0.f,0.f), scene_emission(0.f);
        glm::vec4 light_direction_intensity[4]={{.3f,.8f,.5f,1.f},{0,0,0,0},{0,0,0,0},{0,0,0,0}};
        glm::vec4 light_color_kind[4]={{1.f,1.f,1.f,0.f},{0,0,0,0},{0,0,0,0},{0,0,0,0}};
        std::string feature_normal_map;
        const auto features=FeatureMetadata(ctx);
        if(features.contains("3d") && features.at("3d").is_object()) {
            const auto& three_d=features.at("3d");
            if(three_d.contains("pbr") && three_d.at("pbr").is_object()) {
                const auto& value=three_d.at("pbr");
                pbr.x=float(value.value("metallic",0.0)); pbr.y=float(value.value("roughness",.5)); pbr.z=1.f;
                feature_normal_map=value.value("normal_map",std::string());
                if(value.contains("emission") && value.at("emission").is_array() && value.at("emission").size()==3)
                    scene_emission=glm::vec4(value.at("emission")[0],value.at("emission")[1],value.at("emission")[2],0.f);
            }
            if(three_d.contains("lights") && three_d.at("lights").is_array() && !three_d.at("lights").empty()) {
                const auto& lights=three_d.at("lights");
                const auto count=std::min<std::size_t>(4,lights.size());
                for(std::size_t light=0;light<count;++light) {
                    const auto& value=lights.at(light); if(!value.is_object()) continue;
                    const auto color=value.value("color",Json::array({1.,1.,1.}));
                    if(!color.is_array()||color.size()!=3) continue;
                    light_color_kind[light]={float(color[0]),float(color[1]),float(color[2]),0.f};
                    light_direction_intensity[light].w=float(value.value("intensity",1.0));
                    const auto kind=value.value("kind",std::string("directional"));
                    if(kind!="directional" && value.contains("position") && value.at("position").is_array() && value.at("position").size()==3) {
                        const auto& position=value.at("position");
                        light_direction_intensity[light].x=float(position[0]); light_direction_intensity[light].y=float(position[1]); light_direction_intensity[light].z=float(position[2]);
                        light_color_kind[light].w=1.f;
                    } else if(value.contains("direction") && value.at("direction").is_array() && value.at("direction").size()==3) {
                        const auto& direction=value.at("direction");
                        light_direction_intensity[light].x=float(direction[0]); light_direction_intensity[light].y=float(direction[1]); light_direction_intensity[light].z=float(direction[2]);
                    }
                }
            }
        }
        const GpuMesh* feature_normal=nullptr;
        if(!feature_normal_map.empty()) {
            if(auto found=meshes.find("@pbr_normal:"+feature_normal_map); found!=meshes.end()) feature_normal=found->second.get();
        }
        struct Draw { const RenderEntity* instance; const GpuMesh* mesh; const MeshPart* part; SDL_GPUBuffer* vertex; float z; };
        std::vector<Draw> opaque,transparent;
        for(const auto& instance:entities) {
            const auto& mesh=*meshes.at(instance.mesh);
            const auto* deformation=mesh.animation ? deformations.at({instance.id,instance.mesh}).get() : nullptr;
            for(const auto& part:deformation ? deformation->parts : mesh.parts) {
                const float z=(view*instance.matrix*glm::vec4(part.center,1.f)).z;
                const bool blend=instance.material ? instance.material->alpha_mode=="blend" : mesh.materials[part.material].alpha_mode==2;
                auto& list=blend ? transparent : opaque;
                list.push_back({&instance,&mesh,&part,deformation ? deformation->vertex : mesh.vertex,z});
            }
        }
        // shortcut: sort transparent primitives by center; intersecting transparent
        // triangles need order-independent transparency when that renderer arrives.
        auto order=[](const auto& a,const auto& b) {
            if(a.instance->sorting_layer!=b.instance->sorting_layer) return a.instance->sorting_layer<b.instance->sorting_layer;
            if(a.instance->sorting_order!=b.instance->sorting_order) return a.instance->sorting_order<b.instance->sorting_order;
            return a.z<b.z;
        };
        std::stable_sort(opaque.begin(),opaque.end(),order);
        std::stable_sort(transparent.begin(),transparent.end(),order);
        auto draw=[&](const Draw& item) {
            const auto& instance=*item.instance; const auto& mesh=*item.mesh; const auto& part=*item.part;
            auto matrix=projection*view*instance.matrix;
            struct { glm::mat4 matrix; glm::vec4 uv; glm::mat4 model; } transform{matrix,instance.uv,instance.matrix};
            SDL_PushGPUVertexUniformData(command,0,&transform,sizeof(transform));
            const auto& material=mesh.materials[part.material];
            glm::vec4 parameters[14]={{float(material.alpha_mode),material.alpha_cutoff,material.unlit ? 1.f : 0.f,0},material.base_color,{},pbr,
                scene_emission+glm::vec4(material.emission,0.f),light_direction_intensity[0],light_direction_intensity[1],light_direction_intensity[2],light_direction_intensity[3],
                light_color_kind[0],light_color_kind[1],light_color_kind[2],light_color_kind[3],glm::vec4(eye,1.f)};
            if(pbr.z!=0 && (material.normal_image!=std::numeric_limits<std::size_t>::max() || feature_normal)) parameters[3].w=material.normal_image==std::numeric_limits<std::size_t>::max() ? 1.f : material.normal_scale;
            if(instance.material) {
                const auto& value=*instance.material;
                const float mode=value.alpha_mode=="blend" ? 2.f : value.alpha_mode=="mask" ? 1.f : 0.f;
                parameters[0]={mode,float(value.alpha_cutoff),value.unlit ? 1.f : 0.f,0};
                parameters[1]=glm::vec4(glm::vec3(value.color),float(value.opacity));
            }
            if(instance.sprite) {
                parameters[0].w=1;
                const auto start=glm::vec2(instance.uv.z,instance.uv.w);
                const auto end=start+glm::vec2(instance.uv.x,instance.uv.y);
                const auto half=mesh.texels[material.image]*.5f;
                parameters[2]=glm::vec4(glm::min(start,end)+half,glm::max(start,end)-half);
            }
            SDL_PushGPUFragmentUniformData(command,0,parameters,sizeof(parameters));
            const auto normal_image=material.normal_image==std::numeric_limits<std::size_t>::max() ? material.image : material.normal_image;
            SDL_GPUTextureSamplerBinding textures[2]={{mesh.textures[material.image],mesh.samplers[part.material]},
                {feature_normal ? feature_normal->textures[0] : mesh.textures[normal_image],
                 feature_normal ? feature_normal->samplers[0] : mesh.normal_samplers[part.material]}};
            SDL_BindGPUFragmentSamplers(pass,0,textures,2);
            SDL_GPUBufferBinding vb{item.vertex,0}, ib{mesh.index,0};
            SDL_BindGPUVertexBuffers(pass,0,&vb,1); SDL_BindGPUIndexBuffer(pass,&ib,SDL_GPU_INDEXELEMENTSIZE_32BIT);
            SDL_DrawGPUIndexedPrimitives(pass,part.count,1,part.first,0,0);
        };
        SDL_BindGPUGraphicsPipeline(pass,pipeline); for(const auto& item:opaque) draw(item);
        SDL_BindGPUGraphicsPipeline(pass,blend_pipeline); for(const auto& item:transparent) draw(item);
    }
    SDL_EndGPURenderPass(pass);
    if(ui_renderer && !UiAssets(ctx).empty()) {
        UpdateUi(ctx,w,h,SDL_GetWindowDisplayScale(window));
        ui_renderer->begin(command,swap,w,h);
        RenderUi(ctx);
        ui_renderer->end();
    }
    if(!capture_path.empty()) {
        SDL_GPUTransferBufferCreateInfo ti{SDL_GPU_TRANSFERBUFFERUSAGE_DOWNLOAD,w*h*4,0};
        auto* transfer=SDL_CreateGPUTransferBuffer(gpu,&ti); require(transfer!=nullptr);
        auto* copy=SDL_BeginGPUCopyPass(command);
        SDL_GPUTextureRegion region{}; region.texture=swap; region.w=w; region.h=h; region.d=1;
        SDL_GPUTextureTransferInfo dest{}; dest.transfer_buffer=transfer; dest.pixels_per_row=w; dest.rows_per_layer=h;
        SDL_DownloadFromGPUTexture(copy,&region,&dest); SDL_EndGPUCopyPass(copy);
        auto* fence=SDL_SubmitGPUCommandBufferAndAcquireFence(command); require(fence!=nullptr);
        require(SDL_WaitForGPUFences(gpu,true,&fence,1));
        auto* pixels=SDL_MapGPUTransferBuffer(gpu,transfer,false); require(pixels!=nullptr);
        auto format=SDL_GetGPUSwapchainTextureFormat(gpu,window);
        SDL_PixelFormat pixel_format=(format==SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM || format==SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM_SRGB) ? SDL_PIXELFORMAT_BGRA32 : SDL_PIXELFORMAT_RGBA32;
        auto* surface=SDL_CreateSurfaceFrom(w,h,pixel_format,pixels,w*4); require(surface!=nullptr);
        const auto filename=capture_path.u8string();
        require(SDL_SaveBMP(surface,reinterpret_cast<const char*>(filename.c_str())));
        SDL_DestroySurface(surface); SDL_UnmapGPUTransferBuffer(gpu,transfer);
        SDL_ReleaseGPUFence(gpu,fence); SDL_ReleaseGPUTransferBuffer(gpu,transfer);
        completed_capture=capture_path; capture_path.clear();
    } else require(SDL_SubmitGPUCommandBuffer(command));
}
}
