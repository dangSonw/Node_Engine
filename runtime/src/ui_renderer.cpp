#include "ui_renderer.hpp"
#include <stdexcept>
#include <vector>
#include <fstream>

namespace rt {
namespace {
void require(bool ok, const char* what) {
    if(!ok) throw std::runtime_error(std::string(what)+": "+SDL_GetError());
}
SDL_GPUShader* load_shader(SDL_GPUDevice* gpu, const std::filesystem::path& path, bool fragment) {
    std::ifstream file(path,std::ios::binary);
    if(!file) throw std::runtime_error("Cannot read UI shader: "+path.string());
    std::vector<unsigned char> code((std::istreambuf_iterator<char>(file)),{});
    SDL_GPUShaderCreateInfo info{};
    info.code_size=code.size(); info.code=code.data(); info.entrypoint="main";
    info.format=SDL_GPU_SHADERFORMAT_SPIRV;
    info.stage=fragment ? SDL_GPU_SHADERSTAGE_FRAGMENT : SDL_GPU_SHADERSTAGE_VERTEX;
    info.num_samplers=fragment ? 1 : 0; info.num_uniform_buffers=fragment ? 1 : 0;
    auto* shader=SDL_CreateGPUShader(gpu,&info); require(shader,"Create UI shader"); return shader;
}
}
UiRenderer::UiRenderer(SDL_GPUDevice* gpu, SDL_Window* window, const std::filesystem::path& shaders):
    RenderInterface_SDL_GPU(gpu,window,SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM),gpu_(gpu) {
    SDL_GPUShader *vertex=nullptr,*fragment=nullptr;
    try {
        auto format=SDL_GetGPUSwapchainTextureFormat(gpu,window);
        if(format!=SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM && format!=SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM &&
           format!=SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM_SRGB && format!=SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM_SRGB)
            throw std::runtime_error("UI compositor requires an SDR swapchain");
        linear_=(format==SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM_SRGB || format==SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM_SRGB) ? 1.f : 0.f;
        vertex=load_shader(gpu,shaders/"UiComposite.vert.spv",false);
        fragment=load_shader(gpu,shaders/"UiComposite.frag.spv",true);
        SDL_GPUColorTargetDescription target{}; target.format=format;
        target.blend_state.enable_blend=true;
        target.blend_state.src_color_blendfactor=SDL_GPU_BLENDFACTOR_ONE;
        target.blend_state.dst_color_blendfactor=SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;
        target.blend_state.color_blend_op=SDL_GPU_BLENDOP_ADD;
        target.blend_state.src_alpha_blendfactor=SDL_GPU_BLENDFACTOR_ONE;
        target.blend_state.dst_alpha_blendfactor=SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;
        target.blend_state.alpha_blend_op=SDL_GPU_BLENDOP_ADD;
        SDL_GPUGraphicsPipelineCreateInfo pipeline{};
        pipeline.vertex_shader=vertex; pipeline.fragment_shader=fragment;
        pipeline.primitive_type=SDL_GPU_PRIMITIVETYPE_TRIANGLELIST;
        pipeline.target_info.num_color_targets=1; pipeline.target_info.color_target_descriptions=&target;
        composite_=SDL_CreateGPUGraphicsPipeline(gpu,&pipeline); require(composite_,"Create UI composite pipeline");
        SDL_GPUSamplerCreateInfo sampling{};
        sampling.address_mode_u=sampling.address_mode_v=sampling.address_mode_w=SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE;
        sampling.min_filter=sampling.mag_filter=SDL_GPU_FILTER_NEAREST;
        sampler_=SDL_CreateGPUSampler(gpu,&sampling); require(sampler_,"Create UI compositor sampler");
    } catch(...) {
        if(vertex) SDL_ReleaseGPUShader(gpu,vertex);
        if(fragment) SDL_ReleaseGPUShader(gpu,fragment);
        release(); Shutdown(); throw;
    }
    SDL_ReleaseGPUShader(gpu,vertex); SDL_ReleaseGPUShader(gpu,fragment);
}
void UiRenderer::release() {
    if(layer_) SDL_ReleaseGPUTexture(gpu_,layer_);
    if(sampler_) SDL_ReleaseGPUSampler(gpu_,sampler_);
    if(composite_) SDL_ReleaseGPUGraphicsPipeline(gpu_,composite_);
}
UiRenderer::~UiRenderer() { Shutdown(); release(); }
void UiRenderer::begin(SDL_GPUCommandBuffer* command, SDL_GPUTexture* destination, uint32_t width, uint32_t height) {
    if(command_) throw std::runtime_error("UI frame already open");
    if(!command || !destination || !width || !height) throw std::runtime_error("Invalid UI frame target");
    if(width_!=width || height_!=height) {
        SDL_GPUTextureCreateInfo info{}; info.type=SDL_GPU_TEXTURETYPE_2D;
        info.format=SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM;
        info.usage=SDL_GPU_TEXTUREUSAGE_COLOR_TARGET | SDL_GPU_TEXTUREUSAGE_SAMPLER;
        info.width=width; info.height=height; info.layer_count_or_depth=1; info.num_levels=1;
        auto* replacement=SDL_CreateGPUTexture(gpu_,&info); require(replacement,"Create UI layer");
        if(layer_) SDL_ReleaseGPUTexture(gpu_,layer_);
        layer_=replacement; width_=width; height_=height;
    }
    SDL_GPUColorTargetInfo target{}; target.texture=layer_;
    target.load_op=SDL_GPU_LOADOP_CLEAR; target.store_op=SDL_GPU_STOREOP_STORE;
    auto* pass=SDL_BeginGPURenderPass(command,&target,1,nullptr); require(pass,"Clear UI layer");
    SDL_EndGPURenderPass(pass);
    command_=command; destination_=destination;
    BeginFrame(command,layer_,width,height);
}
void UiRenderer::end() {
    if(!command_) throw std::runtime_error("UI frame is not open");
    EndFrame();
    SDL_GPUColorTargetInfo target{}; target.texture=destination_;
    target.load_op=SDL_GPU_LOADOP_LOAD; target.store_op=SDL_GPU_STOREOP_STORE;
    auto* pass=SDL_BeginGPURenderPass(command_,&target,1,nullptr); require(pass,"Composite UI layer");
    SDL_BindGPUGraphicsPipeline(pass,composite_);
    SDL_GPUTextureSamplerBinding binding{layer_,sampler_};
    SDL_BindGPUFragmentSamplers(pass,0,&binding,1);
    float parameters[4]={linear_,0,0,0};
    SDL_PushGPUFragmentUniformData(command_,0,parameters,sizeof(parameters));
    SDL_DrawGPUPrimitives(pass,3,1,0,0); SDL_EndGPURenderPass(pass);
    command_=nullptr; destination_=nullptr;
}
}
