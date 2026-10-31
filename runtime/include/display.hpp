#pragma once
#include "runtime.hpp"
#include "ui_renderer.hpp"
#include <SDL3/SDL.h>
#include <filesystem>
#include <memory>
#include <array>
#include <limits>
namespace rt {
// Position/color/UV plus the authored geometric normal.  The final three
// fields were appended so old aggregate initializers keep their defaults.
struct Vertex { float x,y,z,r,g,b,a,u=0,v=0,shade=1,nx=0,ny=0,nz=1; };
struct ImageData { uint32_t width=1,height=1; std::vector<uint8_t> rgba{255,255,255,255}; };
struct MaterialData {
    glm::vec4 base_color{1};
    size_t image=0;
    SDL_GPUSamplerCreateInfo sampler{};
    bool mipmaps=false, unlit=false;
    // 0 = opaque, 1 = mask, 2 = blend, matching the fragment uniform.
    int alpha_mode=0;
    float alpha_cutoff=.5f;
    float metallic=0, roughness=1, normal_scale=1;
    glm::vec3 emission{0};
    std::size_t normal_image=std::numeric_limits<std::size_t>::max();
};
struct MeshPart {
    uint32_t first=0,count=0;
    size_t material=0;
    glm::vec3 center{0};
    size_t node=0;
    int skin=-1;
};
struct DeformVertex { glm::vec3 position; std::array<SkinInfluence,16> weights{}; size_t count=0; };
struct MeshData {
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
    std::vector<ImageData> images;
    std::vector<MaterialData> materials;
    std::vector<MeshPart> parts;
    Vec3 minimum{0}, maximum{0};
    std::shared_ptr<const AnimationAsset> animation;
    std::vector<DeformVertex> deformation;
};
MeshData LoadGltf(const std::filesystem::path&);
MeshData LoadSprite(const std::filesystem::path&,const Json&);
MeshData LoadTilemap(const std::filesystem::path&,const Json&,const Json&);
MeshData LoadRuntimeTexture(const std::filesystem::path&,const std::string&,const std::string& filter="linear");
struct GpuMesh {
    SDL_GPUDevice* gpu=nullptr;
    SDL_GPUBuffer* vertex=nullptr;
    SDL_GPUBuffer* index=nullptr;
    std::vector<SDL_GPUTexture*> textures;
    std::vector<glm::vec2> texels;
    std::vector<SDL_GPUSampler*> samplers;
    std::vector<SDL_GPUSampler*> normal_samplers;
    std::vector<MaterialData> materials;
    std::vector<MeshPart> parts;
    Vec3 minimum{0}, maximum{0};
    std::shared_ptr<const AnimationAsset> animation;
    std::vector<Vertex> vertices;
    std::vector<DeformVertex> deformation;
    ~GpuMesh() {
        if(vertex) SDL_ReleaseGPUBuffer(gpu,vertex);
        if(index) SDL_ReleaseGPUBuffer(gpu,index);
        for(auto* texture:textures) if(texture) SDL_ReleaseGPUTexture(gpu,texture);
        for(auto* sampler:samplers) if(sampler) SDL_ReleaseGPUSampler(gpu,sampler);
        for(auto* sampler:normal_samplers) if(sampler) SDL_ReleaseGPUSampler(gpu,sampler);
    }
};
struct GpuDeformation {
    SDL_GPUDevice* gpu=nullptr;
    SDL_GPUBuffer* vertex=nullptr;
    SDL_GPUTransferBuffer* transfer=nullptr;
    std::shared_ptr<GpuMesh> mesh;
    std::vector<MeshPart> parts;
    ~GpuDeformation() {
        if(vertex) SDL_ReleaseGPUBuffer(gpu,vertex);
        if(transfer) SDL_ReleaseGPUTransferBuffer(gpu,transfer);
    }
};
class Display {
public:
    SDL_Window* window=nullptr;
    SDL_GPUDevice* gpu=nullptr;
    SDL_GPUGraphicsPipeline* pipeline=nullptr;
    SDL_GPUGraphicsPipeline* blend_pipeline=nullptr;
    SDL_GPUTexture* depth=nullptr;
    std::unique_ptr<UiRenderer> ui_renderer;
    std::map<std::string,std::shared_ptr<GpuMesh>> meshes;
    std::map<std::pair<std::string,std::string>,std::unique_ptr<GpuDeformation>> deformations;
    uint32_t width=0,height=0;
    double yaw=35, pitch=20, distance=5;
    bool auto_frame=true, needs_initial_frame=true;
    bool game_camera=true;
    bool uses_game_camera(const Ctx& c) const { return game_camera && !GetActiveCamera(c).id.empty(); }
    std::filesystem::path completed_capture;
    Vec3 target{0};
    Display();
    ~Display();
    void upload(const std::map<std::string,MeshData>&,const Ctx&);
    std::map<std::string,std::shared_ptr<GpuMesh>> prepare_upload(const std::map<std::string,MeshData>&);
    void commit_upload(std::map<std::string,std::shared_ptr<GpuMesh>>&&) noexcept;
    void ensure_ui_renderer();
    void frame_scene(const Ctx&);
    void render(Ctx&);
    void prepare_ui(Ctx&,const std::filesystem::path& root);
    void update_ui(Ctx&);
    void validate_checkpoint_resources(const Ctx&) const;
    void screenshot(const std::filesystem::path&);
private:
    void update_animations(const Ctx&);
    std::filesystem::path capture_path;
};
}
