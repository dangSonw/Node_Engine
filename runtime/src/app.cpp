#define SDL_MAIN_USE_CALLBACKS 1
#include "display.hpp"
#include "channel.hpp"
#include "input_devices.hpp"
#include <SDL3/SDL_main.h>
#include <fstream>
#include <iostream>
#include <memory>
#include <optional>
#ifdef NODE_ENGINE_NODE_CODE
void RegisterEmbeddedNodeCode();
#endif
#ifdef NODE_ENGINE_COMPILED
void OnStart(rt::Ctx&);
void OnUpdate(rt::Ctx&);
void OnLateUpdate(rt::Ctx&);
void OnFixedUpdate(rt::Ctx&);
void OnQuit(rt::Ctx&);
void OnSceneLoaded(rt::Ctx&);
void BindEvents(rt::Ctx&);
rt::Json CompiledScene();
rt::Json CompiledProgram();
#endif
struct App {
    rt::Ctx ctx;
    rt::Json ir;
    std::unique_ptr<rt::Display> display;
    std::unique_ptr<rt::GamepadDevices> gamepads;
    std::unique_ptr<rt::Channel> channel;
    std::filesystem::path root, save_root;
    bool running=false, started=false, quit=false;
    uint64_t previous=0, rendered=0, limit=0;
    size_t log_offset=0;
    std::string output, capture, audio_capture;
    std::vector<rt::InputEvent> pending_input;
    std::map<unsigned long long,std::vector<rt::InputEvent>> replay;
    std::map<unsigned long long,std::vector<rt::Json>> ui_replay;
    bool ui_replay_enabled=false;
    bool replay_enabled=false;
    bool cursor_released=false;
    ~App() { release_cursor(); ctx.ui.reset(); ctx.audio.reset(); }
    bool input_focus() const {
#ifdef _WIN32
        auto hwnd=static_cast<HWND>(SDL_GetPointerProperty(SDL_GetWindowProperties(display->window),SDL_PROP_WINDOW_WIN32_HWND_POINTER,nullptr));
        return GetFocus()==hwnd && GetForegroundWindow()==GetAncestor(hwnd,GA_ROOT);
#else
        return SDL_GetKeyboardFocus()==display->window;
#endif
    }
    bool mouse_inside() const {
#ifdef _WIN32
        POINT point{}; if(!GetCursorPos(&point)) return false;
        auto hwnd=static_cast<HWND>(SDL_GetPointerProperty(SDL_GetWindowProperties(display->window),SDL_PROP_WINDOW_WIN32_HWND_POINTER,nullptr));
        return WindowFromPoint(point)==hwnd;
#else
        return SDL_GetMouseFocus()==display->window;
#endif
    }
    void release_cursor() noexcept {
        if(display && display->window) { SDL_SetWindowRelativeMouseMode(display->window,false); SDL_ShowCursor(); }
    }
    void sync_cursor() {
        const bool active=running && !replay_enabled && !ui_replay_enabled && !cursor_released && input_focus();
        const bool locked=active && ctx.input.cursor_locked;
        const bool visible=!locked && (!active || !mouse_inside() || ctx.input.cursor_visible);
        auto fail=[&](const char* operation) {
            const std::string error=SDL_GetError(); ctx.current_node=ctx.input.cursor_node;
            release_cursor(); throw std::runtime_error(std::string(operation)+": "+error);
        };
        if(SDL_GetWindowRelativeMouseMode(display->window)!=locked) {
            if(!SDL_SetWindowRelativeMouseMode(display->window,locked)) fail("Cannot change cursor lock");
            if(locked) rt::ClearUiInput(ctx);
        }
        if(SDL_CursorVisible()!=visible && !(visible ? SDL_ShowCursor() : SDL_HideCursor())) fail("Cannot change cursor visibility");
    }
    void event(rt::Json message) {
        if(message.value("event",std::string{})=="node_error") message["scene"]=ctx.scene_name;
        if(channel) channel->send(message);
        else std::cout<<message.dump()<<"\n"<<std::flush;
    }
    void state() { event({{"event","state"},{"state",running?"running":started?"paused":"stopped"}}); }
    void neutral_input() {
        rt::ClearInput(ctx);
        if(gamepads) gamepads->reset(ctx,input_focus());
        if(!replay_enabled) {
            float x=0,y=0; SDL_GetMouseState(&x,&y);
            ctx.input.mouse_position={x,y,0};
        }
    }
    std::map<std::string,rt::MeshData> scene_meshes(const rt::Ctx& target) {
        std::map<std::string,rt::MeshData> data;
        for(const auto& key:rt::SceneMeshes(target)) {
            if(key.starts_with("@tilemap:")) continue;
            data.emplace(key,rt::LoadGltf(std::filesystem::weakly_canonical(root/std::filesystem::u8path(key))));
        }
        size_t sprite_bytes=0;
        const auto sprite_assets=rt::SpriteAssets(target);
        std::map<std::string,rt::Json> sprite_by_id;
        for(const auto& asset:sprite_assets) {
            sprite_by_id.emplace(asset.at("id").get<std::string>(),asset);
            auto mesh=rt::LoadSprite(root,asset); sprite_bytes+=mesh.images[0].rgba.size();
            if(sprite_bytes>256*1024*1024) throw std::runtime_error("Scene sprite texture budget exceeds 256 MiB");
            data.emplace("@sprite:"+asset.at("id").get<std::string>(),std::move(mesh));
        }
        for(const auto& tilemap:rt::TilemapAssets(target)) {
            const auto id=tilemap.at("id").get<std::string>();
            const auto sprite=sprite_by_id.find(tilemap.at("sprite").get<std::string>());
            if(sprite==sprite_by_id.end()) throw std::runtime_error("Tilemap references an unknown sprite asset");
            data.emplace("@tilemap:"+id,rt::LoadTilemap(root,tilemap,sprite->second));
        }
        const auto features=rt::FeatureMetadata(target);
        std::vector<std::string> runtime_textures;
        if(features.contains("2d") && features.at("2d").is_object()) {
            const auto& two_d=features.at("2d");
            if(two_d.contains("runtime_textures") && two_d.at("runtime_textures").is_array())
                for(const auto& path:two_d.at("runtime_textures")) runtime_textures.push_back(path.get<std::string>());
            if(two_d.contains("tilemap") && two_d.at("tilemap").is_object() &&
               two_d.at("tilemap").contains("runtime_textures") && two_d.at("tilemap").at("runtime_textures").is_array())
                for(const auto& path:two_d.at("tilemap").at("runtime_textures")) runtime_textures.push_back(path.get<std::string>());
        }
        std::string feature_normal_map;
        if(features.contains("3d") && features.at("3d").is_object()) {
            const auto& three_d=features.at("3d");
            if(three_d.contains("pbr") && three_d.at("pbr").is_object() && three_d.at("pbr").contains("normal_map") && three_d.at("pbr").at("normal_map").is_string()) {
                feature_normal_map=three_d.at("pbr").at("normal_map").get<std::string>();
                runtime_textures.push_back(feature_normal_map);
            }
        }
        std::sort(runtime_textures.begin(),runtime_textures.end()); runtime_textures.erase(std::unique(runtime_textures.begin(),runtime_textures.end()),runtime_textures.end());
        for(const auto& path:runtime_textures)
            data.emplace("@runtime_texture:"+path,rt::LoadRuntimeTexture(root,path,"linear"));
        if(!feature_normal_map.empty())
            data.emplace("@pbr_normal:"+feature_normal_map,rt::LoadRuntimeTexture(root,feature_normal_map,"linear"));
        return data;
    }
    void reset(const rt::Json* replacement=nullptr) {
#ifdef NODE_ENGINE_COMPILED
        const auto program=CompiledProgram();
#else
        const auto& program=replacement ? *replacement : ir;
#endif
        rt::Ctx next;
        next.saves.base=save_root;
#ifdef NODE_ENGINE_COMPILED
        rt::ConfigureSceneProject(next,program,root,limit==0,BindEvents,OnFixedUpdate);
#else
        rt::ConfigureSceneProject(next,program,root,limit==0);
#endif
        auto uses_ui=[](const rt::Json& p) {return !p.at("scene").value("ui_assets",rt::Json::array()).empty();};
        if(program.contains("scenes")) {for(const auto& p:program.at("scenes")) if(uses_ui(p)) display->ensure_ui_renderer();}
        else if(uses_ui(program)) display->ensure_ui_renderer();
        rt::PrepareAudio(next,root,limit==0);
        rt::PrepareAnimations(next,root);
        rt::PrepareUi(next,root,display->ui_renderer.get(),display->window,false); display->update_ui(next);
        const auto next_meshes=scene_meshes(next);
        rt::VerifyGameResources(next);
        auto prepared=display->prepare_upload(next_meshes);
        rt::SuspendUiPlatform(ctx); display->commit_upload(std::move(prepared));
        ctx=std::move(next); log_offset=0; running=false; started=false;
        rt::ActivateUiPlatform(ctx);
        cursor_released=false; release_cursor();
        pending_input.clear();
        if(replacement) ir=*replacement;
        for(const auto& [path,mesh]:next_meshes)
            event({{"event","asset_loaded"},{"path",path},{"vertices",mesh.vertices.size()},{"triangles",mesh.indices.size()/3}});
        event({{"event","scene_loaded"},{"scene",ctx.scene_name},{"mesh_instances",rt::RenderEntities(ctx).size()},{"unique_meshes",next_meshes.size()}});
    }
    void loaded() {
        rt::StartEntityLifecycle(ctx); rt::DrainEvents(ctx);
#ifdef NODE_ENGINE_COMPILED
        OnSceneLoaded(ctx);
#else
        const auto& events=rt::CurrentSceneProgram(ctx).at("events");
        if(events.contains("scene_loaded")) rt::Execute(ctx,events.at("scene_loaded"));
#endif
        rt::DrainEvents(ctx);
    }
    void process_scene_change() {
        if(ctx.quit_requested) {rt::CancelSceneChange(ctx); return;}
        if(!rt::SceneChangePending(ctx)) return;
        std::optional<std::map<std::string,std::shared_ptr<rt::GpuMesh>>> prepared;
        if(rt::ProcessSceneChange(ctx,[&](const rt::Ctx& next) {prepared=display->prepare_upload(scene_meshes(next));},
            [&] {display->commit_upload(std::move(*prepared));},display->ui_renderer.get(),display->window)) {
            pending_input.clear(); if(!replay_enabled) neutral_input();
            rt::PauseAudioOutput(ctx,!running);
            event({{"event","scene_changed"},{"scene",ctx.scene_name}});
            loaded(); display->update_ui(ctx); rt::DrainUiEvents(ctx);
        }
        rt::DrainEvents(ctx);
    }
    void process_game_persistence() {
        if(!rt::GameSavePending(ctx)) return;
        std::optional<std::map<std::string,std::shared_ptr<rt::GpuMesh>>> prepared;
        if(rt::ProcessGamePersistence(ctx,[&](const rt::Ctx& next) {
            if(next.scene_name!=ctx.scene_name) prepared=display->prepare_upload(scene_meshes(next));
            else display->validate_checkpoint_resources(next);
        },display->ui_renderer.get(),display->window,[&] {if(prepared) display->commit_upload(std::move(*prepared));})) {
            pending_input.clear();
            // Physical buttons belong to this session, not the saved keyboard state.
            // Replay keeps the checkpoint state for exact deterministic continuation.
            if(!replay_enabled) neutral_input();
            rt::PauseAudioOutput(ctx,!running);
            event({{"event","scene_restored"},{"scene",ctx.scene_name}});
        }
        rt::DrainEvents(ctx);
    }
    void start() {
        cursor_released=false;
        if(!running) { neutral_input(); rt::ClearUiInput(ctx); pending_input.clear(); }
        if(!started) {
            ctx.remaining=ctx.budget;
            loaded();
#ifdef NODE_ENGINE_COMPILED
            OnStart(ctx);
#else
            rt::Execute(ctx,rt::CurrentSceneProgram(ctx).at("events").at("start"));
#endif
            rt::DrainEvents(ctx);
            display->update_ui(ctx);
            rt::DrainUiEvents(ctx);
            started=true;
            process_scene_change();
            process_game_persistence();
        }
        rt::PauseAudioOutput(ctx,false);
        running=true; previous=SDL_GetTicksNS(); state();
        sync_cursor();
    }
    void update(double elapsed) {
        rt::BeginGameFrame(ctx,elapsed,std::min(.1,elapsed));
        if(replay_enabled) {
            auto input=replay.find(ctx.frame);
            rt::AdvanceInput(ctx,input==replay.end() ? std::vector<rt::InputEvent>{} : input->second);
        } else rt::AdvanceInput(ctx,pending_input);
        pending_input.clear();
        ctx.remaining=ctx.budget;
        rt::AdvanceContinuations(ctx); rt::DrainEvents(ctx);
        if(auto input=ui_replay.find(ctx.frame); input!=ui_replay.end()) rt::AdvanceUiInput(ctx,input->second);
        rt::DrainUiEvents(ctx);
#ifdef NODE_ENGINE_COMPILED
        OnUpdate(ctx);
#else
        rt::Execute(ctx,rt::CurrentSceneProgram(ctx).at("events").at("update"));
#endif
        rt::DrainEvents(ctx);
        rt::AdvanceTimers(ctx);
        rt::DrainEvents(ctx);
        if(!ctx.time_frozen) rt::AdvancePhysics(ctx);
        rt::AdvanceAudio(ctx,ctx.unscaled_dt);
        rt::AdvanceAnimations(ctx);
        rt::AdvanceSpriteStates(ctx);
        rt::DrainEvents(ctx);
#ifdef NODE_ENGINE_COMPILED
        OnLateUpdate(ctx);
#else
        if(rt::CurrentSceneProgram(ctx).at("events").contains("late_update")) rt::Execute(ctx,rt::CurrentSceneProgram(ctx).at("events").at("late_update"));
#endif
        rt::DrainEvents(ctx);
        rt::EndGameFrame(ctx);
        display->update_ui(ctx);
        rt::DrainUiEvents(ctx);
        process_scene_change();
        process_game_persistence();
        sync_cursor();
    }
    SDL_AppResult finish() {
        quit=true; running=false; release_cursor();
        bool okay=true;
        try {
            if(started) rt::FinishApplication(ctx,[&]() {
#ifdef NODE_ENGINE_COMPILED
                OnQuit(ctx);
#else
                if(rt::CurrentSceneProgram(ctx).at("events").contains("quit")) rt::Execute(ctx,rt::CurrentSceneProgram(ctx).at("events").at("quit"));
#endif
            },[&]() { display->update_ui(ctx); },[&]() { process_game_persistence(); });
        } catch(const std::exception& e) {
            okay=false; rt::CancelGamePersistence(ctx); rt::CancelSceneChange(ctx);
            event({{"event","node_error"},{"node",ctx.current_node},{"message",e.what()}});
        }
        while(log_offset<ctx.logs.size()) event({{"event","log"},{"message",ctx.logs[log_offset++]}});
        rt::FinishAudioCapture(ctx);
        if(!capture.empty()) {
            display->screenshot(std::filesystem::u8path(capture));
            display->render(ctx);
            if(display->completed_capture.empty()) throw std::runtime_error("Cannot capture the closing game window");
            event({{"event","capture_done"},{"path",capture},{"width",display->width},{"height",display->height}});
        }
        if(!output.empty()) {
            std::ofstream out(std::filesystem::u8path(output));
            if(!out || !(out<<rt::Snapshot(ctx).dump(2))) throw std::runtime_error("Cannot write final game state");
        }
        event({{"event","application_quit"},{"started",started},{"success",okay},{"frame",ctx.frame}});
        return okay ? SDL_APP_SUCCESS : SDL_APP_FAILURE;
    }
    void command(const rt::Json& m) {
        ctx.current_node.clear();
        auto cmd=m.at("command").get<std::string>();
        if(cmd=="play") start();
        else if(cmd=="pause") { rt::PauseAudioOutput(ctx,true); running=false; release_cursor(); rt::ClearInput(ctx); rt::ClearUiInput(ctx); pending_input.clear(); state(); }
        else if(cmd=="release_input") {
            cursor_released=true; release_cursor();
            // Foreign-window focus changes do not always reach SDL as focus events.
            if(running && !replay_enabled) {
                if(pending_input.empty() || !pending_input.back().releases_all()) pending_input.push_back({});
                if(pending_input.size()>100000) throw std::runtime_error("Input event queue exceeded 100000 events");
                rt::ClearUiInput(ctx);
            }
        }
        else if(cmd=="stop") { reset(); state(); }
        else if(cmd=="quit") { quit=true; release_cursor(); }
        else if(cmd=="load_ir") {
#ifdef NODE_ENGINE_COMPILED
            throw std::runtime_error("Compiled game cannot replace its graph at runtime");
#else
            if(m.at("ir").at("version")!=1) throw std::runtime_error("Unsupported IR");
            const auto& replacement=m.at("ir");
            reset(&replacement); state();
#endif
        } else if(cmd=="set_property") {
            rt::EntityRef entity{m.at("entity").get<std::string>()};
            auto value=rt::vec_from_json(m.at("value"));
            const auto prop=m.at("property").get<std::string>();
            if(prop=="position") rt::SetPosition(ctx,entity,value);
            else if(prop=="rotation") rt::SetRotation(ctx,entity,value);
            else if(prop=="scale") rt::SetScale(ctx,entity,value);
            else throw std::runtime_error("Unknown entity property");
            event({{"event","property_changed"},{"entity",m.at("entity")},{"property",prop},{"value",m.at("value")}});
        } else if(cmd=="snapshot") event({{"event","snapshot"},{"state",rt::Snapshot(ctx)}});
        else if(cmd=="cursor_status") {
            sync_cursor();
            event({{"event","cursor_status"},{"requested_visible",ctx.input.cursor_visible},{"requested_locked",ctx.input.cursor_locked},
                {"relative",SDL_GetWindowRelativeMouseMode(display->window)},{"visible",SDL_CursorVisible()},
                {"focused",input_focus()},{"sdl_focused",SDL_GetKeyboardFocus()==display->window},
                {"window_focus_flag",bool(SDL_GetWindowFlags(display->window)&SDL_WINDOW_INPUT_FOCUS)},{"released",cursor_released}});
        }
        else if(cmd=="begin_audio_capture") rt::BeginAudioCapture(ctx,std::filesystem::u8path(m.at("path").get<std::string>()));
        else if(cmd=="end_audio_capture") rt::FinishAudioCapture(ctx);
        else if(cmd=="audio_output_status") event({{"event","audio_output_status"},{"status",rt::AudioOutputStatus(ctx)}});
        else if(cmd=="frame_scene") display->frame_scene(ctx);
        else if(cmd=="view_camera") display->game_camera=m.at("game").get<bool>();
        else if(cmd=="camera") {
            display->yaw=m.value("yaw",display->yaw);
            display->pitch=std::clamp(m.value("pitch",display->pitch),-85.0,85.0);
            display->distance=std::max(.1,m.value("distance",display->distance));
            if(m.contains("distance")) display->auto_frame=false;
        } else if(cmd=="capture") display->screenshot(std::filesystem::u8path(m.at("path").get<std::string>()));
        else throw std::runtime_error("Unknown runtime command: "+cmd);
        event({{"event","ack"},{"id",m.value("id",0)},{"command",cmd}});
    }
};
SDL_AppResult SDL_AppInit(void** state,int argc,char** argv) {
    auto* app=new App; *state=app;
    try {
#ifdef NODE_ENGINE_NODE_CODE
        RegisterEmbeddedNodeCode();
#endif
        std::string socket,ir_path;
        app->root=std::filesystem::current_path();
        for(int i=1;i<argc;++i) {
            std::string a=argv[i];
            auto next=[&]() { if(++i>=argc) throw std::runtime_error("Missing argument: "+a); return std::string(argv[i]); };
            if(a=="--socket") socket=next();
            else if(a=="--ir") ir_path=next();
            else if(a=="--project-root") app->root=std::filesystem::u8path(next());
            else if(a=="--frames") app->limit=std::stoull(next());
            else if(a=="--save-root") app->save_root=std::filesystem::u8path(next());
            else if(a=="--capture") app->capture=next();
            else if(a=="--audio-output") app->audio_capture=next();
            else if(a=="--output") app->output=next();
            else if(a=="--ui-replay") {
                std::ifstream file(std::filesystem::u8path(next()));
                if(!file) throw std::runtime_error("Cannot open UI replay");
                rt::Json data; file>>data; app->ui_replay=rt::LoadUiReplay(data); app->ui_replay_enabled=true;
            }
            else if(a=="--input-replay") {
                auto path=std::filesystem::u8path(next());
                std::ifstream file(path);
                if(!file) throw std::runtime_error("Cannot open input replay");
                rt::Json data; file>>data;
                app->replay=rt::LoadInputReplay(data); app->replay_enabled=true;
            }
            else throw std::runtime_error("Unknown argument: "+a);
        }
#ifndef NODE_ENGINE_COMPILED
        std::ifstream file(std::filesystem::u8path(ir_path));
        if(!file) throw std::runtime_error("Cannot open IR: "+ir_path);
        file>>app->ir;
        if(app->ir.at("version")!=1) throw std::runtime_error("Unsupported IR");
#endif
        if(!socket.empty()) { app->channel=std::make_unique<rt::Channel>(); app->channel->connect(socket); }
        app->display=std::make_unique<rt::Display>();
        if(!app->replay_enabled && !app->ui_replay_enabled) app->gamepads=std::make_unique<rt::GamepadDevices>();
        app->event({{"event","hello"},{"protocol_version",1},{"renderer",SDL_GetGPUDeviceDriver(app->display->gpu)}});
#ifdef _WIN32
        auto hwnd=SDL_GetPointerProperty(SDL_GetWindowProperties(app->display->window),SDL_PROP_WINDOW_WIN32_HWND_POINTER,nullptr);
        app->event({{"event","window_handle"},{"handle",reinterpret_cast<uintptr_t>(hwnd)}});
#endif
        app->reset();
        if(!app->audio_capture.empty()) rt::BeginAudioCapture(app->ctx,std::filesystem::u8path(app->audio_capture));
        if(!app->channel) app->start(); else app->state();
        app->previous=SDL_GetTicksNS();
        return SDL_APP_CONTINUE;
    } catch(const std::exception& e) { std::cerr<<e.what()<<"\n"; return SDL_APP_FAILURE; }
}
SDL_AppResult SDL_AppEvent(void* state,SDL_Event* event) {
    auto& a=*static_cast<App*>(state);
    try {
        if(event->type==SDL_EVENT_QUIT || (event->type==SDL_EVENT_WINDOW_CLOSE_REQUESTED &&
            event->window.windowID==SDL_GetWindowID(a.display->window))) {
            a.quit=true; a.release_cursor(); return SDL_APP_CONTINUE;
        }
        if(a.quit || a.ctx.quit_requested) return SDL_APP_CONTINUE;
        if(a.gamepads) {
            a.gamepads->sync(a.running && !a.cursor_released && a.input_focus(),a.pending_input);
            a.gamepads->event(*event,a.running,a.pending_input);
        }
        if(event->type==SDL_EVENT_MOUSE_BUTTON_DOWN && a.channel) {
#ifdef _WIN32
            // Qt embeds a foreign child HWND; SDL's top-level activation cannot focus it.
            auto hwnd=static_cast<HWND>(SDL_GetPointerProperty(SDL_GetWindowProperties(a.display->window),SDL_PROP_WINDOW_WIN32_HWND_POINTER,nullptr));
            SetFocus(hwnd);
#else
            SDL_RaiseWindow(a.display->window);
#endif
        }
        if(event->type==SDL_EVENT_MOUSE_BUTTON_DOWN) { a.cursor_released=false; a.sync_cursor(); }
        if(event->type==SDL_EVENT_KEY_DOWN && event->key.key==SDLK_ESCAPE && a.channel) {
            a.cursor_released=true; a.release_cursor();
            rt::ClearUiInput(a.ctx);
            a.pending_input.push_back({});
            a.event({{"event","release_focus"}});
            return SDL_APP_CONTINUE;
        }
        if(event->type==SDL_EVENT_WINDOW_FOCUS_LOST) { a.release_cursor(); rt::ClearUiInput(a.ctx); }
        const bool relative=SDL_GetWindowRelativeMouseMode(a.display->window);
        const bool pointer=event->type==SDL_EVENT_MOUSE_MOTION || event->type==SDL_EVENT_MOUSE_WHEEL ||
            event->type==SDL_EVENT_MOUSE_BUTTON_DOWN || event->type==SDL_EVENT_MOUSE_BUTTON_UP;
        const bool ui_propagate=(!a.running || a.ui_replay_enabled || (relative && pointer)) ? true : rt::ProcessUiInput(a.ctx,*event);
        if(!a.replay_enabled && a.running && (!a.ctx.input.cursor_locked || (relative && a.input_focus()))) {
            // Position remains readable over UI; consumed gestures do not move gameplay.
            if(event->type==SDL_EVENT_MOUSE_MOTION) {
                const auto& m=event->motion;
                a.pending_input.push_back(ui_propagate ? rt::InputEvent::Motion(m.x,m.y,m.xrel,m.yrel) : rt::InputEvent::Position(m.x,m.y));
            } else if(event->type==SDL_EVENT_MOUSE_BUTTON_DOWN || event->type==SDL_EVENT_MOUSE_BUTTON_UP)
                a.pending_input.push_back(rt::InputEvent::Position(event->button.x,event->button.y));
            else if(event->type==SDL_EVENT_MOUSE_WHEEL) {
                a.pending_input.push_back(rt::InputEvent::Position(event->wheel.mouse_x,event->wheel.mouse_y));
                if(ui_propagate) {
                    const double direction=event->wheel.direction==SDL_MOUSEWHEEL_FLIPPED ? -1 : 1;
                    a.pending_input.push_back(rt::InputEvent::Wheel(event->wheel.x*direction,event->wheel.y*direction));
                }
            }
            if(a.pending_input.size()>100000) throw std::runtime_error("Input event queue exceeded 100000 events");
        }
        if(!ui_propagate && (event->type==SDL_EVENT_KEY_DOWN || event->type==SDL_EVENT_MOUSE_BUTTON_DOWN)) {
            a.pending_input.push_back({});
        }
        const bool release=event->type==SDL_EVENT_KEY_UP || event->type==SDL_EVENT_MOUSE_BUTTON_UP;
        if(!a.replay_enabled && a.running && (ui_propagate || release)) {
            if(event->type==SDL_EVENT_WINDOW_FOCUS_LOST) a.pending_input.push_back({});
            else if((event->type==SDL_EVENT_KEY_DOWN || event->type==SDL_EVENT_KEY_UP) && !event->key.repeat) {
                auto key=SDL_GetKeyName(SDL_GetKeyFromScancode(event->key.scancode,SDL_KMOD_NONE,false));
                a.pending_input.push_back({key,event->type==SDL_EVENT_KEY_DOWN});
            } else if(event->type==SDL_EVENT_MOUSE_BUTTON_DOWN || event->type==SDL_EVENT_MOUSE_BUTTON_UP) {
                const std::map<Uint8,std::string> names={{SDL_BUTTON_LEFT,"MouseLeft"},{SDL_BUTTON_RIGHT,"MouseRight"},
                    {SDL_BUTTON_MIDDLE,"MouseMiddle"},{SDL_BUTTON_X1,"MouseX1"},{SDL_BUTTON_X2,"MouseX2"}};
                auto it=names.find(event->button.button);
                if(it!=names.end()) a.pending_input.push_back({it->second,event->type==SDL_EVENT_MOUSE_BUTTON_DOWN});
            }
            if(a.pending_input.size()>100000) throw std::runtime_error("Input event queue exceeded 100000 events");
        }
        if(ui_propagate && !a.replay_enabled && !a.display->uses_game_camera(a.ctx) && event->type==SDL_EVENT_MOUSE_MOTION && (event->motion.state&SDL_BUTTON_RMASK)) {
            a.display->yaw+=event->motion.xrel*.3;
            a.display->pitch=std::clamp(a.display->pitch+event->motion.yrel*.3,-85.0,85.0);
        }
        if(ui_propagate && !a.replay_enabled && !a.display->uses_game_camera(a.ctx) && event->type==SDL_EVENT_MOUSE_WHEEL) {
            a.display->distance=std::max(.1,a.display->distance*std::pow(.9,event->wheel.y));
            a.display->auto_frame=false;
        }
        return SDL_APP_CONTINUE;
    } catch(const std::exception& e) { std::cerr<<e.what()<<"\n"; return SDL_APP_FAILURE; }
}
SDL_AppResult SDL_AppIterate(void* state) {
    auto& a=*static_cast<App*>(state);
    try {
        if(a.channel) for(auto& message:a.channel->receive()) {
            try { a.command(message); }
            catch(const std::exception& e) { rt::CancelGamePersistence(a.ctx); rt::CancelSceneChange(a.ctx); a.event({{"event","node_error"},{"node",a.ctx.current_node},
                {"message",e.what()},{"id",message.value("id",0)},{"command",message.value("command",std::string())}}); }
            if(a.quit || a.ctx.quit_requested) break;
        }
        if(a.quit || a.ctx.quit_requested) return a.finish();
        uint64_t now=SDL_GetTicksNS();
        const double elapsed=a.limit ? 1.0/60 : double(now-a.previous)/1e9;
        a.previous=now;
        if(a.running) {
            try {
                if(a.gamepads) a.gamepads->sync(!a.cursor_released && a.input_focus(),a.pending_input);
                a.sync_cursor(); a.update(elapsed);
            }
            catch(const std::exception& e) {
                rt::CancelGamePersistence(a.ctx); rt::CancelSceneChange(a.ctx);
                a.running=false; a.release_cursor(); rt::PauseAudioOutput(a.ctx,true);
                a.event({{"event","node_error"},{"node",a.ctx.current_node},{"message",e.what()}}); a.state();
            }
        }
        if(a.ctx.quit_requested || (a.limit && a.rendered+1>=a.limit)) return a.finish();
        while(a.log_offset<a.ctx.logs.size()) a.event({{"event","log"},{"message",a.ctx.logs[a.log_offset++]}});
        a.display->render(a.ctx); ++a.rendered;
        if(!a.display->completed_capture.empty()) {
            auto path=a.display->completed_capture.u8string();
            a.event({{"event","capture_done"},{"path",std::string(path.begin(),path.end())},
                     {"width",a.display->width},{"height",a.display->height}});
            a.display->completed_capture.clear();
        }
        if(a.channel && a.rendered%15==0)
            a.event({{"event","metrics"},{"frame",a.ctx.frame},{"frame_ms",elapsed*1000},{"entities",rt::EntityCount(a.ctx)}});
        return SDL_APP_CONTINUE;
    } catch(const std::exception& e) { std::cerr<<e.what()<<"\n"; return SDL_APP_FAILURE; }
}
void SDL_AppQuit(void* state,SDL_AppResult) { delete static_cast<App*>(state); }
