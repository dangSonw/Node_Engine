#define SDL_MAIN_HANDLED
#include <RmlUi/Core.h>
#include <RmlUi/Core/Elements/ElementFormControl.h>
#include <RmlUi/Core/Elements/ElementProgress.h>
#include <RmlUi_Platform_SDL.h>
#include "ui_renderer.hpp"
#include "ui_session.hpp"
#include <nlohmann/json.hpp>
#include <SDL3_image/SDL_image.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>

using Json=nlohmann::json;
void require(bool ok,const std::string& message) { if(!ok) throw std::runtime_error(message+": "+SDL_GetError()); }
int main(int argc,char** argv) {
    try {
        bool headless=false,linear=false; std::string font,output,capture;
        for(int i=1;i<argc;++i) {
            std::string arg=argv[i];
            auto next=[&]() { require(++i<argc,"Missing argument"); return std::string(argv[i]); };
            if(arg=="--headless") headless=true;
            else if(arg=="--linear") linear=true;
            else if(arg=="--font") font=next();
            else if(arg=="--output") output=next();
            else if(arg=="--capture") capture=next();
            else throw std::runtime_error("Unknown option: "+arg);
        }
        Json checks=Json::array();
        auto check=[&](const char* label,bool ok) { require(ok,label); checks.push_back(label); };
        FT_Library ft=nullptr; FT_Face face=nullptr;
        require(FT_Init_FreeType(&ft)==0 && FT_New_Face(ft,font.c_str(),0,&face)==0,"Open font with FreeType");
        bool vietnamese=true;
        for(char32_t c:std::u32string(U"Tiếng Việt")) if(!FT_Get_Char_Index(face,c)) vietnamese=false;
        FT_Done_Face(face); FT_Done_FreeType(ft);
        SDL_Window* window=nullptr; SDL_GPUDevice* gpu=nullptr;
        std::unique_ptr<rt::UiRenderer> renderer;
        if(!headless) {
            require(SDL_Init(SDL_INIT_VIDEO),"Initialize SDL");
            window=SDL_CreateWindow("Node_Engine UI backend probe",640,480,0); require(window,"Create window");
            gpu=SDL_CreateGPUDevice(SDL_GPU_SHADERFORMAT_SPIRV,false,nullptr); require(gpu,"Create GPU");
            require(SDL_ClaimWindowForGPUDevice(gpu,window),"Claim window");
            require(SDL_SetGPUSwapchainParameters(gpu,window,linear ? SDL_GPU_SWAPCHAINCOMPOSITION_SDR_LINEAR : SDL_GPU_SWAPCHAINCOMPOSITION_SDR,SDL_GPU_PRESENTMODE_VSYNC),"Set swapchain");
            renderer=std::make_unique<rt::UiRenderer>(gpu,window,"shaders");
        }
        auto ui=std::make_unique<rt::UiSession>(font,renderer.get(),window);
        ui->update(0,640,480);
        const std::string markup=R"(
<rml><head><style>
body { margin:0; width:100%; height:100%; font-family:node-ui; font-size:20px; color:#eeeeee; }
#panel { position:absolute; left:16px; top:16px; width:608px; height:448px; background-color:#16283b; }
#title { position:absolute; left:32px; top:28px; font-size:24px; }
#score { position:absolute; left:32px; top:85px; }
#add { position:absolute; left:32px; top:150px; width:200px; height:48px; line-height:48px; text-align:center; background-color:#326cba; }
#add:hover { background-color:#417dcc; } #add:disabled { background-color:#555555; }
#text { position:absolute; left:32px; top:225px; width:300px; height:36px; background-color:#253e58; }
#progress { position:absolute; left:32px; top:300px; width:400px; height:24px; background-color:#345268; }
#progress fill { background-color:#35bd87; }
#swatch { position:absolute; left:520px; top:32px; width:80px; height:80px; background-color:#4080c0; }
#translucent { position:absolute; left:520px; top:130px; width:80px; height:40px; background-color:rgba(64,128,192,128); }
#scene-alpha { position:absolute; left:520px; top:468px; width:80px; height:10px; background-color:rgba(64,128,192,128); }
#image { position:absolute; left:520px; top:220px; width:64px; height:64px; }
#clip { position:absolute; left:520px; top:310px; width:40px; height:24px; overflow:hidden; }
#clip div { display:block; width:80px; height:24px; background-color:#4080c0; }
#range { position:absolute; left:32px; top:350px; width:200px; height:24px; }
#range slidertrack { background-color:#345268; height:8px; }
#range sliderbar { width:16px; height:24px; background-color:#35bd87; }
#toggle { position:absolute; left:260px; top:350px; width:24px; height:24px; background-color:#345268; }
#toggle:checked { background-color:#35bd87; }
#anchor { position:absolute; right:24px; bottom:24px; width:100px; height:24px; background-color:#c06020; }
</style></head><body><div id="panel"/><div id="title">Node_Engine UI</div><div id="score">Score: 0</div>
<input id="add" type="button" value="Add point"/><input id="text" type="text"/><progress id="progress" value="0"/>
<div id="swatch"/><div id="translucent"/><div id="scene-alpha"/><img id="image" src="image.png"/>
<div id="clip"><div/></div><input id="range" type="range" min="0" max="1" step="0.05" value="0.5"/>
<input id="toggle" type="checkbox"/><div id="anchor"/></body></rml>)";
        const auto source_path=(std::filesystem::current_path()/"layout.rml").generic_u8string();
        const std::string source(source_path.begin(),source_path.end());
        ui->load("hud",markup,source);
        auto update=[&]() { ui->update(0,640,480); };
        int clicks=0;
        auto consume_clicks=[&]() {
            for(const auto& event:ui->take_events()) if(event.type=="click" && event.document=="hud" && event.element=="add") {
                ++clicks; ui->set_text("hud","score","Score: "+std::to_string(clicks));
                ui->set_value("hud","progress",clicks*.2);
            }
        };
        auto draw=[&](const std::string& file) {
            if(headless) return;
            auto* command=SDL_AcquireGPUCommandBuffer(gpu); require(command,"Acquire GPU command");
            SDL_GPUTexture* swap=nullptr; Uint32 w=0,h=0;
            require(SDL_WaitAndAcquireGPUSwapchainTexture(command,window,&swap,&w,&h) && swap,"Acquire swapchain");
            auto background=[&](float v) { v/=255; return linear ? (v<=.04045f ? v/12.92f : std::pow((v+.055f)/1.055f,2.4f)) : v; };
            SDL_GPUColorTargetInfo color{}; color.texture=swap; color.clear_color={background(10),background(20),background(30),1};
            color.load_op=SDL_GPU_LOADOP_CLEAR; color.store_op=SDL_GPU_STOREOP_STORE;
            auto* pass=SDL_BeginGPURenderPass(command,&color,1,nullptr); require(pass,"Clear frame"); SDL_EndGPURenderPass(pass);
            renderer->begin(command,swap,w,h); ui->render(); renderer->end();
            SDL_GPUTransferBufferCreateInfo info{SDL_GPU_TRANSFERBUFFERUSAGE_DOWNLOAD,w*h*4,0};
            auto* transfer=SDL_CreateGPUTransferBuffer(gpu,&info); require(transfer,"Create readback");
            auto* copy=SDL_BeginGPUCopyPass(command); require(copy,"Readback pass");
            SDL_GPUTextureRegion region{}; region.texture=swap; region.w=w; region.h=h; region.d=1;
            SDL_GPUTextureTransferInfo destination{}; destination.transfer_buffer=transfer; destination.pixels_per_row=w; destination.rows_per_layer=h;
            SDL_DownloadFromGPUTexture(copy,&region,&destination); SDL_EndGPUCopyPass(copy);
            auto* fence=SDL_SubmitGPUCommandBufferAndAcquireFence(command); require(fence && SDL_WaitForGPUFences(gpu,true,&fence,1),"Readback fence");
            auto* bytes=SDL_MapGPUTransferBuffer(gpu,transfer,false); require(bytes,"Map pixels");
            auto format=SDL_GetGPUSwapchainTextureFormat(gpu,window);
            auto pixel_format=(format==SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM || format==SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM_SRGB) ? SDL_PIXELFORMAT_BGRA32 : SDL_PIXELFORMAT_RGBA32;
            auto* surface=SDL_CreateSurfaceFrom(w,h,pixel_format,bytes,w*4); require(surface,"Readback surface");
            require(SDL_SaveBMP(surface,file.c_str()),"Save UI image"); SDL_DestroySurface(surface);
            SDL_UnmapGPUTransferBuffer(gpu,transfer); SDL_ReleaseGPUFence(gpu,fence); SDL_ReleaseGPUTransferBuffer(gpu,transfer);
        };
        draw(capture+"-before.bmp");
        auto click=[&](int x,int y) {
            if(headless) { ui->pointer_move(x,y); ui->pointer_button(0,true); ui->pointer_button(0,false); }
            else {
                SDL_Event e{}; e.type=SDL_EVENT_MOUSE_MOTION; e.motion.x=float(x); e.motion.y=float(y); ui->process(e);
                e={}; e.type=SDL_EVENT_MOUSE_BUTTON_DOWN; e.button.button=SDL_BUTTON_LEFT;
                e.button.x=float(x); e.button.y=float(y); ui->process(e);
                e.type=SDL_EVENT_MOUSE_BUTTON_UP; ui->process(e);
            }
            update();
        };
        click(130,174); consume_clicks(); update(); check("Coordinate click reaches button and changes score",clicks==1);
        ui->set_enabled("hud","add",false); update(); click(130,174); consume_clicks();
        check("Disabled button rejects clicks",clicks==1 && !ui->enabled("hud","add"));
        ui->set_enabled("hud","add",true); ui->set_style("hud","add","display","none"); update(); click(130,174); consume_clicks();
        check("Hidden button rejects clicks",clicks==1);
        ui->set_style("hud","add","display","block"); update(); click(130,174); consume_clicks(); update();
        check("Showing the button restores interaction",clicks==2);
        click(120,240); std::string input="Node - Tiếng Việt";
        if(headless) ui->text_input(input);
        else { SDL_Event e{}; e.type=SDL_EVENT_TEXT_INPUT; e.text.text=input.c_str(); ui->process(e); }
        update();
        auto value=ui->text("hud","text");
        check("UTF-8 text input reaches focused control",value==input);
        if(!headless) {
            SDL_SetModState(SDL_KMOD_NONE);
            SDL_Event e{}; e.type=SDL_EVENT_KEY_DOWN; e.key.key=SDLK_A; e.key.mod=SDL_KMOD_LCTRL; ui->process(e);
            e.type=SDL_EVENT_KEY_UP; ui->process(e);
            e={}; e.type=SDL_EVENT_TEXT_INPUT; e.text.text="replacement"; ui->process(e);
            check("Ctrl+A uses event modifiers after the chord is released",ui->text("hud","text")=="replacement");
            ui->set_text("hud","text",input); update();
        }
        auto progress=ui->value("hud","progress");
        check("Progress reflects gameplay value",std::abs(progress-.4f)<.0001f);
        ui->update(0,800,600);
        if(!headless) {
            require(SDL_SetWindowSize(window,800,600),"Resize UI window"); SDL_SyncWindow(window);
            draw(capture+"-resized.bmp");
            require(SDL_SetWindowSize(window,640,480),"Restore UI window"); SDL_SyncWindow(window);
        }
        update(); draw(capture+"-after.bmp");
        auto events=ui->take_events();
        check("Typing yields change events carrying Unicode text",std::any_of(events.begin(),events.end(),[&](const auto& e){return e.type=="change" && e.element=="text" && e.value==input;}));
        ui->key_input(Rml::Input::KI_RETURN,true); ui->key_input(Rml::Input::KI_RETURN,false);
        events=ui->take_events();
        check("Enter submits the focused text with its value",std::count_if(events.begin(),events.end(),[&](const auto& e){return e.type=="submit" && e.value==input;})==1);
        ui->set_value("hud","range",.75); check("Slider accepts a normalized value",std::abs(ui->value("hud","range")-.75)<.001);
        update(); ui->take_events(); click(218,354); events=ui->take_events();
        check("Slider interaction changes value and emits a change event",ui->value("hud","range")>.75 && ui->value("hud","range")<=1 &&
            std::any_of(events.begin(),events.end(),[](const auto& e){return e.element=="range" && e.type=="change";}));
        ui->set_checked("hud","toggle",true); update(); ui->take_events(); click(270,360);
        events=ui->take_events();
        check("Checkbox click changes checked state and emits a value event",!ui->checked("hud","toggle") && std::any_of(events.begin(),events.end(),[](const auto& e){return e.type=="change" && e.element=="toggle" && !e.checked;}));
        ui->focus("hud","text");
        ui->key_input(Rml::Input::KI_END,true,Rml::Input::KM_CTRL); ui->key_input(Rml::Input::KI_END,false);
        ui->text_input("!");
        check("Programmatic focus routes text",ui->text("hud","text")==input+"!");
        const std::string literal="<img id='unexpected'/> & Tiếng Việt"; ui->set_text("hud","score",literal);
        check("Set Text escapes markup and preserves literal Unicode",ui->text("hud","score")==literal);
        auto rejected=[&](auto fn) { try { fn(); return false; } catch(const std::exception&) { return true; } };
        check("Missing element and wrong widget type report errors",rejected([&]{ui->set_value("hud","missing",.2);}) && rejected([&]{ui->set_checked("hud","score",true);}));
        check("Progress rejects an out-of-range value without mutation",rejected([&]{ui->set_value("hud","progress",2);}) && ui->value("hud","progress")==progress);
        check("Duplicate instance is rejected without changing the original",rejected([&]{ui->load("hud",markup);}) && ui->text("hud","score")==literal);
        check("Malformed replacement IDs roll back without losing live UI",rejected([&]{ui->load("invalid","<rml><body><div id='a'/><div id='a'/></body></rml>");}) && !ui->contains("invalid") && ui->contains("hud"));
        const bool strict=rejected([&]{ui->load("missing","<rml><body><img src='missing-image.png'/></body></rml>",source);});
        check("Missing texture diagnostics reject the template and preserve existing UI",strict && !ui->contains("missing") && ui->text("hud","score")==literal);
        {
            rt::UiSession replacement(font); replacement.load("hud",markup,source); replacement.set_text("hud","score","Replacement");
            check("Concurrent scene replacement has independent widget state",replacement.text("hud","score")=="Replacement" && ui->text("hud","score")==literal);
        }
        ui->show("hud",false); update(); ui->take_events(); click(130,174);
        check("Hidden documents receive no button clicks",ui->take_events().empty());
        ui->show("hud",true); update(); click(130,174); ui->destroy("hud");
        check("Destroy removes the instance and cancels its queued events",!ui->contains("hud") && ui->take_events().empty());
        ui->load("hud",markup,source); check("Recreating an instance restores template defaults",ui->text("hud","score")=="Score: 0" && ui->text("hud","text").empty());
        Json report={{"passed",true},{"checks",checks},{"state",{{"clicks",clicks},{"text",value},{"progress",progress}}},
            {"vietnamese_font_glyphs",vietnamese},{"strict_diagnostics",strict},{"version",Rml::GetVersion()},
            {"headless",headless},{"linear_swapchain",linear}};
        ui.reset();
        { rt::UiSession reopened(font); reopened.load("hud",markup,source); check("UI core reopens after all previous sessions close",reopened.contains("hud")); }
        report["checks"]=checks;
        if(renderer) { renderer.reset(); SDL_WaitForGPUIdle(gpu); SDL_ReleaseWindowFromGPUDevice(gpu,window); SDL_DestroyGPUDevice(gpu); SDL_DestroyWindow(window); SDL_Quit(); }
        std::ofstream(output)<<report.dump(2)<<"\n";
        std::cout<<report.dump(2)<<"\n"; return 0;
    } catch(const std::exception& e) { std::cerr<<e.what()<<"\n"; return 1; }
}
