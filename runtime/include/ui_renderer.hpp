#pragma once
#include <RmlUi_Renderer_SDL_GPU.h>
#include <filesystem>

namespace rt {
// RmlUi blends CSS colors in sRGB space. Composite that layer into the linear
// game framebuffer with one transfer-function conversion and premultiplied alpha.
// The caller must destroy RmlUi contexts before this renderer and the GPU after it.
class UiRenderer final: public RenderInterface_SDL_GPU {
public:
    UiRenderer(SDL_GPUDevice*, SDL_Window*, const std::filesystem::path& shaders);
    ~UiRenderer();
    void begin(SDL_GPUCommandBuffer*, SDL_GPUTexture* destination, uint32_t width, uint32_t height);
    void end();
private:
    SDL_GPUDevice* gpu_;
    SDL_GPUTexture* layer_=nullptr;
    SDL_GPUGraphicsPipeline* composite_=nullptr;
    SDL_GPUSampler* sampler_=nullptr;
    SDL_GPUCommandBuffer* command_=nullptr;
    SDL_GPUTexture* destination_=nullptr;
    uint32_t width_=0, height_=0;
    float linear_=0;
    void release();
};
}
