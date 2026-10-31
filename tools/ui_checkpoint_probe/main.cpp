#define SDL_MAIN_HANDLED
#include "runtime.hpp"
#include "ui_renderer.hpp"
#include <RmlUi/Core.h>
#include <SDL3/SDL.h>
#include <filesystem>
#include <fstream>
#include <iostream>

using namespace rt;
namespace {
Json checks=Json::array();
void Require(bool ok,const std::string& message) { if(!ok) throw std::runtime_error(message); }
void Check(const std::string& name,bool ok) { Require(ok,name); checks.push_back(name); }
template<class F> void Fails(F f) { bool failed=false; try { f(); } catch(const std::exception&) { failed=true; } Require(failed,"Expected checkpoint rejection"); }
const std::string markup=R"(
<rml><head><style>
body { margin:0; width:100%; height:100%; font-family:node-ui; font-size:18px; color:#eeeeee; }
#panel { position:absolute; left:10px; top:10px; width:550px; height:400px; background-color:#183149; }
#label { position:absolute; left:20px; top:15px; }
#button { position:absolute; left:20px; top:55px; width:140px; height:40px; background-color:#3275b6; }
#button:hover { background-color:#4285c6; }
#text { position:absolute; left:20px; top:110px; width:230px; height:30px; }
#range { position:absolute; left:20px; top:165px; width:200px; height:25px; }
#range slidertrack { height:8px; background-color:#345268; }
#range sliderbar { width:14px; height:25px; background-color:#35bd87; }
#toggle { position:absolute; left:250px; top:165px; width:25px; height:25px; background-color:#345268; }
#toggle:checked { background-color:#35bd87; }
#progress { position:absolute; left:20px; top:210px; width:260px; height:20px; background-color:#345268; }
#progress fill { background-color:#35bd87; }
#area { display:block; position:absolute; left:20px; top:250px; width:290px; height:60px; overflow-y:auto; }
scrollbarvertical { width:12px; }
scrollbarhorizontal { height:12px; }
scrollbarvertical sliderbar { width:12px; min-height:12px; background-color:#35bd87; }
#disabled { position:absolute; left:350px; top:300px; width:100px; height:30px; }
</style></head><body id="root"><div id="panel"/><div id="label">Default</div>
<input id="button" type="button" value="Click"/><input id="text" type="text" value="abcdef"/>
<input id="range" type="range" min="0" max="1" step="0.05" value="0.2"/>
<input id="toggle" type="checkbox"/><progress id="progress" value="0"/>
<textarea id="area"></textarea><input id="disabled" type="button" value="Disabled"/>
</body></rml>)";
struct Display {
    SDL_Window* window=nullptr; SDL_GPUDevice* gpu=nullptr; std::unique_ptr<UiRenderer> renderer;
    explicit Display(bool enabled) {
        if(!enabled) return;
        Require(SDL_Init(SDL_INIT_VIDEO),SDL_GetError());
        window=SDL_CreateWindow("Node_Engine checkpoint verification",640,480,0); Require(window,SDL_GetError());
        gpu=SDL_CreateGPUDevice(SDL_GPU_SHADERFORMAT_SPIRV,false,nullptr); Require(gpu,SDL_GetError());
        Require(SDL_ClaimWindowForGPUDevice(gpu,window),SDL_GetError());
        renderer=std::make_unique<UiRenderer>(gpu,window,"shaders");
    }
    ~Display() {
        renderer.reset();
        if(gpu) { SDL_WaitForGPUIdle(gpu); SDL_ReleaseWindowFromGPUDevice(gpu,window); SDL_DestroyGPUDevice(gpu); }
        if(window) { SDL_DestroyWindow(window); SDL_Quit(); }
    }
    void capture(Ctx& c,const std::filesystem::path& file) {
        if(!renderer) return;
        auto* command=SDL_AcquireGPUCommandBuffer(gpu); Require(command,SDL_GetError());
        SDL_GPUTexture* swap=nullptr; Uint32 w=0,h=0;
        Require(SDL_WaitAndAcquireGPUSwapchainTexture(command,window,&swap,&w,&h) && swap,SDL_GetError());
        SDL_GPUColorTargetInfo color{}; color.texture=swap; color.clear_color={.03f,.05f,.08f,1};
        color.load_op=SDL_GPU_LOADOP_CLEAR; color.store_op=SDL_GPU_STOREOP_STORE;
        auto* pass=SDL_BeginGPURenderPass(command,&color,1,nullptr); Require(pass,SDL_GetError()); SDL_EndGPURenderPass(pass);
        renderer->begin(command,swap,w,h); RenderUi(c); renderer->end();
        SDL_GPUTransferBufferCreateInfo info{SDL_GPU_TRANSFERBUFFERUSAGE_DOWNLOAD,w*h*4,0};
        auto* transfer=SDL_CreateGPUTransferBuffer(gpu,&info); Require(transfer,SDL_GetError());
        auto* copy=SDL_BeginGPUCopyPass(command); Require(copy,SDL_GetError());
        SDL_GPUTextureRegion region{}; region.texture=swap; region.w=w; region.h=h; region.d=1;
        SDL_GPUTextureTransferInfo destination{}; destination.transfer_buffer=transfer; destination.pixels_per_row=w; destination.rows_per_layer=h;
        SDL_DownloadFromGPUTexture(copy,&region,&destination); SDL_EndGPUCopyPass(copy);
        auto* fence=SDL_SubmitGPUCommandBufferAndAcquireFence(command); Require(fence && SDL_WaitForGPUFences(gpu,true,&fence,1),SDL_GetError());
        auto* bytes=SDL_MapGPUTransferBuffer(gpu,transfer,false); Require(bytes,SDL_GetError());
        const auto format=SDL_GetGPUSwapchainTextureFormat(gpu,window);
        const auto pixels=(format==SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM || format==SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM_SRGB) ? SDL_PIXELFORMAT_BGRA32 : SDL_PIXELFORMAT_RGBA32;
        auto* surface=SDL_CreateSurfaceFrom(w,h,pixels,bytes,w*4); Require(surface,SDL_GetError());
        Require(SDL_SaveBMP(surface,file.string().c_str()),SDL_GetError()); SDL_DestroySurface(surface);
        SDL_UnmapGPUTransferBuffer(gpu,transfer); SDL_ReleaseGPUFence(gpu,fence); SDL_ReleaseGPUTransferBuffer(gpu,transfer);
    }
};
Json Scene() { return {{"version",1},{"entities",Json::array()},{"variables",Json::object()},
    {"ui_assets",{{{"version",1},{"id","template"},{"type","ui"},{"name","Checkpoint HUD"},{"rml",markup}}}}}; }
void Bind(Ctx& c) {
    for(auto kind:{"change","click","submit"}) BindUiEvent(c,std::string("node-")+kind,kind,"","",[](Ctx& c,const UiEvent& e){
        c.logs.push_back(e.document+"/"+e.element+":"+e.type+":"+e.value+":"+(e.checked ? "1" : "0"));
        if(e.type=="click") SetWidgetText(c,e.document,"label","Clicked "+std::to_string(c.logs.size()));
    });
}
void Click(Ctx& c,int x,int y) { AdvanceUiInput(c,{{{"type","move"},{"x",x},{"y",y}},
    {{"type","button"},{"button",0},{"down",true}},{{"type","button"},{"button",0},{"down",false}}}); }
void Key(Ctx& c,const std::string& key) { AdvanceUiInput(c,{{{"type","key"},{"key",key},{"down",true}},{{"type","key"},{"key",key},{"down",false}}}); }
void Text(Ctx& c,const std::string& value) { AdvanceUiInput(c,{{{"type","text"},{"text",value}}}); }
Ctx Initial(const std::filesystem::path& root,Display& display) {
    Ctx c; LoadScene(c,Scene()); Bind(c); PrepareUi(c,root,display.renderer.get(),display.window);
    c.time=12.25; UpdateUi(c,640,480);
    CreateWidget(c,"template","z-back"); CreateWidget(c,"template","a-front"); CreateWidget(c,"template","hidden");
    ShowWidget(c,"hidden",false);
    SetWidgetText(c,"z-back","label","Back"); SetWidgetText(c,"a-front","label","HUD <literal> & Việt");
    SetWidgetText(c,"hidden","label","Hidden edits"); SetWidgetEnabled(c,"a-front","disabled",false);
    SetWidgetChecked(c,"a-front","toggle",true); SetWidgetValue(c,"a-front","range",.65); SetWidgetValue(c,"a-front","progress",.375);
    SetWidgetStyle(c,"a-front","button","margin","2px 4px"); SetWidgetStyle(c,"a-front","button","margin-left","9px");
    SetWidgetStyle(c,"a-front","label","color","#f0b030"); SetWidgetPosition(c,"a-front","button",30,55); SetWidgetSize(c,"a-front","button",180,40);
    SetWidgetText(c,"a-front","area","one\ntwo\nthree\nfour\nfive\nsix\nseven\neight\nnine\nten");
    SetWidgetFocus(c,"a-front","area"); for(int n=0;n<12;++n) Key(c,"Down");
    SetWidgetFocus(c,"a-front","text"); Key(c,"End"); Key(c,"Left"); Text(c," Việt");
    // Keep both stale and live queued events. Hidden generation invalidates only
    // events captured before Hide, even when Show follows before dispatch.
    ShowWidget(c,"a-front",false); ShowWidget(c,"a-front",true);
    SetWidgetFocus(c,"a-front","area"); for(int n=0;n<12;++n) Key(c,"Down");
    SetWidgetFocus(c,"a-front","text"); Key(c,"End"); Text(c,"!"); Key(c,"Return");
    AdvanceUiInput(c,{{{"type","move"},{"x",90},{"y",70}}}); UpdateUi(c,640,480);
    return c;
}
Json Capture(const Ctx& c) { return {{"checkpoint",UiCheckpoint(c)},{"snapshot",UiSnapshot(c)},{"logs",c.logs}}; }
Ctx Restore(const Json& state,const std::filesystem::path& root,Display& display) {
    Ctx program; LoadScene(program,Scene()); Bind(program);
    Ctx c; LoadScene(c,Scene()); c.time=state.at("checkpoint").at("session").at("seconds"); c.logs=state.at("logs").get<std::vector<std::string>>();
    RestoreUiCheckpoint(c,program,state.at("checkpoint"),root,display.renderer.get(),display.window); return c;
}
void Step(Ctx& c,int frame) {
    c.remaining=c.budget; c.time=13.+frame; UpdateUi(c,640,480);
    if(frame==0) { Text(c," restored"); Key(c,"Return"); }
    if(frame==1) Click(c,100,75);
    if(frame==2) { Click(c,260,175); Click(c,200,175); }
    if(frame==3) { SetWidgetFocus(c,"a-front","area"); Text(c,"\nlast"); }
    if(frame==4) { Click(c,375,310); ShowWidget(c,"a-front",false); Click(c,90,70); }
    if(frame==5) { ShowWidget(c,"a-front",true); SetWidgetFocus(c,"a-front","text"); Key(c,"Home"); Text(c,"Start "); }
    if(frame==6) { DestroyWidget(c,"hidden"); CreateWidget(c,"template","hidden"); ShowWidget(c,"hidden",false); }
    if(frame==7) { SetWidgetStyle(c,"a-front","button","margin","0px"); SetWidgetStyle(c,"a-front","button","background-color","#934582"); Click(c,90,70); }
    if(frame==8) { ShowWidget(c,"a-front",false); ShowWidget(c,"z-back",false); }
    if(frame==9) { ShowWidget(c,"a-front",true); SetWidgetFocus(c,"a-front","text"); Key(c,"End"); Text(c," Done"); }
    DrainUiEvents(c); UpdateUi(c,640,480);
}
Json Continue(Ctx& c,int cut,Display& display,const std::filesystem::path& root,const std::string& prefix) {
    Json trace=Json::array();
    for(int frame=cut;frame<10;++frame) { Step(c,frame); trace.push_back(Capture(c)); }
    display.capture(c,root/(prefix+"-"+std::to_string(cut)+".bmp")); return trace;
}
void Invalid(const std::filesystem::path& root,Display& display) {
    auto c=Initial(root,display); auto state=Capture(c); auto other=Restore(state,root,display);
    Check("Distinct candidate UI reproduces widgets, edits, focus, generations and pending events",Capture(other)==state && c.ui!=other.ui);
    Check("Textarea scroll position is nonzero before saving",!state["checkpoint"]["session"]["documents"][0]["scroll"].empty());
    const auto before=c.ui;
    using Damage=std::function<void(Json&)>;
    const std::vector<std::pair<std::string,Damage>> damage={
        {"version",[](Json& j){j["version"]=1.0;}}, {"extra field",[](Json& j){j["extra"]=0;}},
        {"missing session",[](Json& j){j.erase("session");}}, {"different program",[](Json& j){j["bindings"][0]["node"]="unknown";}},
        {"different template",[](Json& j){j["assets"][0]["rml"]="<rml><body/></rml>";}},
        {"unknown template",[](Json& j){j["instances"]["a-front"]="missing";}},
        {"unknown instance",[](Json& j){j["instances"]["other"]="template";}},
        {"session version",[](Json& j){j["session"]["version"]=2;}},
        {"serial",[](Json& j){j["session"]["serial"]=-1;}}, {"overflow serial",[](Json& j){j["session"]["serial"]=UINT64_MAX;}},
        {"generation",[](Json& j){j["session"]["documents"][0]["generation"]=0;}},
        {"document duplication",[](Json& j){j["session"]["documents"][1]=j["session"]["documents"][0];}},
        {"dimensions",[](Json& j){j["session"]["dimensions"][0]=0;}}, {"density",[](Json& j){j["session"]["density"]="one";}},
        {"time",[](Json& j){j["session"]["seconds"]=-1;}}, {"order",[](Json& j){j["session"]["order"][0]="unknown";}},
        {"missing controls",[](Json& j){j["session"]["documents"][0]["controls"]=Json::array();}},
        {"invalid path",[](Json& j){j["session"]["documents"][0]["controls"][0]["at"]["path"]={99999};}},
        {"duplicate control",[](Json& j){auto& v=j["session"]["documents"][0]["controls"]; v.push_back(v[0]);}},
        {"bad style",[](Json& j){j["session"]["documents"][0]["styles"][0][1]="not-a-property";}},
        {"NUL text",[](Json& j){j["session"]["documents"][0]["texts"]["label"]=std::string("bad\0text",8);}},
        {"overflow progress",[](Json& j){j["session"]["documents"][0]["progress"][0]["value"]=2;}},
        {"focus",[](Json& j){j["session"]["focus"]["at"]["document"]="unknown";}},
        {"focus history identity",[](Json& j){j["session"]["focus_history"]={"unknown"};}},
        {"focus history duplicate",[](Json& j){j["session"]["focus_history"]={"a-front","a-front"};}},
        {"focus history type",[](Json& j){j["session"]["focus_history"]=1;}},
        {"selection",[](Json& j){j["session"]["focus"]["selection"]={0,65536};}},
        {"scroll",[](Json& j){j["session"]["documents"][0]["scroll"][0]["y"]=-1;}},
        {"pointer",[](Json& j){j["session"]["pointer"]["modifiers"]=256;}},
        {"queue kind",[](Json& j){j["session"]["events"][0]["type"]="unknown";}},
        {"queue generation",[](Json& j){j["session"]["events"][0]["generation"]=UINT64_MAX;}},
        {"queue overflow",[](Json& j){auto& q=j["session"]["events"]; const auto e=q[0]; q=Json::array(); for(int n=0;n<4097;++n) q.push_back(e);}}
    };
    for(const auto& [label,edit]:damage) {
        auto bad=state["checkpoint"]; edit(bad);
        Fails([&]{RestoreUiCheckpoint(c,c,bad,root,display.renderer.get(),display.window);});
        Check("Malformed "+label+" leaves the original live UI intact",c.ui==before && Capture(c)==state);
    }
    Check("Failed restoration preserves subsequent input and callbacks",Continue(c,0,display,root,"rollback")==Continue(other,0,display,root,"rollback-reference"));
    Ctx empty; LoadScene(empty,{{"version",1},{"entities",Json::array()},{"variables",Json::object()}}); PrepareUi(empty,root);
    const auto saved=UiCheckpoint(empty); RestoreUiCheckpoint(empty,empty,saved,root);
    Check("Scenes without UI templates roundtrip without font or session state",UiCheckpoint(empty)==saved);
    auto reentrant=Initial(root,display); bool guarded=false;
    BindUiEvent(reentrant,"guard","submit","","",[&](Ctx& c,const UiEvent&){Fails([&]{UiCheckpoint(c);}); Fails([&]{RestoreUiCheckpoint(c,c,state["checkpoint"],root);}); guarded=true;});
    DrainUiEvents(reentrant); Check("Checkpoint and restore reject reentrant UI dispatch",guarded);
    auto held=Initial(root,display); AdvanceUiInput(held,{{{"type","button"},{"button",0},{"down",true}}});
    Fails([&]{UiCheckpoint(held);}); ClearUiInput(held); Check("In-progress pointer gestures are rejected until released",!UiCheckpoint(held).is_null());
    const auto font=std::filesystem::path(SDL_GetBasePath())/"fonts/RobotoMono-Regular.ttf";
    UiSession source(font),restored(font); source.load("hud",markup); restored.load("hud",markup);
    source.update(20,640,480); source.focus("hud","text"); source.key_input(Rml::Input::KI_HOME,true);
    for(int n=0;n<3;++n) source.key_input(Rml::Input::KI_RIGHT,true,Rml::Input::KM_SHIFT);
    const auto selected=source.checkpoint(); restored.restore_checkpoint(selected);
    source.text_input("Việt"); restored.text_input("Việt");
    Check("Restored Unicode text replaces the saved selected range",source.text("hud","text")=="Việtdef" && restored.checkpoint()==source.checkpoint());
    auto exhausted=state; exhausted["checkpoint"]["session"]["serial"]=UINT64_MAX-1;
    auto full=Restore(exhausted,root,display); const auto full_state=Capture(full);
    Fails([&]{ShowWidget(full,"a-front",false);});
    Check("Exhausted generation rejects Hide before mutating the document",Capture(full)==full_state);
    Fails([&]{CreateWidget(full,"template","new");});
    Check("Exhausted generation rejects Create before adding a document",Capture(full)==full_state);
}
}
int main(int argc,char** argv) {
    try {
        Require(argc==3 || argc==4,"Usage: node_ui_checkpoint_probe --self-test|--write|--read directory [--gpu]");
        const std::string mode=argv[1]; const auto root=std::filesystem::absolute(argv[2]); std::filesystem::create_directories(root/"assets");
        Display display(argc==4 && std::string(argv[3])=="--gpu");
        if(mode=="--self-test") Invalid(root,display);
        else if(mode=="--write") {
            Json cuts=Json::array();
            for(int cut:{0,3,6}) {
                auto c=Initial(root,display); for(int frame=0;frame<cut;++frame) Step(c,frame);
                display.capture(c,root/("reference-"+std::to_string(cut)+"-at-save.bmp"));
                const auto state=Capture(c); cuts.push_back({{"cut",cut},{"state",state},{"trace",Continue(c,cut,display,root,"reference")}});
            }
            std::ofstream(root/"checkpoint.json")<<cuts.dump(2); Check("Saved three checkpoint cuts before writer process exits",true);
        } else if(mode=="--read") {
            std::ifstream input(root/"checkpoint.json"); Json cuts; input>>cuts;
            for(const auto& saved:cuts) {
                const int cut=saved.at("cut"); auto c=Restore(saved.at("state"),root,display);
                const auto state=Capture(c); std::ofstream(root/("restored-"+std::to_string(cut)+".json"))<<state.dump(2);
                Check("Fresh process restores complete UI checkpoint at cut "+std::to_string(cut),state==saved.at("state"));
                display.capture(c,root/("restored-"+std::to_string(cut)+"-at-save.bmp"));
                const auto trace=Continue(c,cut,display,root,"restored");
                std::ofstream(root/("trace-"+std::to_string(cut)+".json"))<<trace.dump(2);
                Check("Fresh-process input/events match uninterrupted continuation at cut "+std::to_string(cut),trace==saved.at("trace"));
            }
        } else throw std::runtime_error("Unknown probe command");
        std::cout<<Json({{"passed",true},{"checks",checks}}).dump()<<"\n"; return 0;
    } catch(const std::exception& e) { std::cout<<Json({{"passed",false},{"checks",checks},{"error",e.what()}}).dump()<<"\n"; return 1; }
}
