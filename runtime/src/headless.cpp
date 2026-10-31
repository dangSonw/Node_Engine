#include "runtime.hpp"
#include <SDL3/SDL_main.h>
#include <fstream>
#include <iostream>
#include <filesystem>
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
int main(int argc, char** argv) {
    rt::Ctx ctx;
    try {
#ifdef NODE_ENGINE_NODE_CODE
        RegisterEmbeddedNodeCode();
#endif
        int frames=60; std::string path, output, replay_path, audio_output, ui_replay_path;
        auto project_root=std::filesystem::current_path();
        std::map<unsigned long long,std::vector<rt::InputEvent>> replay;
        std::map<unsigned long long,std::vector<rt::Json>> ui_replay;
        for(int i=1;i<argc;++i) {
            std::string a=argv[i];
            auto next=[&]() -> std::string { if(++i>=argc) throw std::runtime_error("Missing argument for "+a); return argv[i]; };
            if(a=="--ir") path=next();
            else if(a=="--frames") frames=std::stoi(next());
            else if(a=="--dt") ctx.dt=std::stod(next());
            else if(a=="--budget") ctx.budget=std::stoi(next());
            else if(a=="--key") ctx.keys.insert(next());
            else if(a=="--input-replay") replay_path=next();
            else if(a=="--ui-replay") ui_replay_path=next();
            else if(a=="--output") output=next();
            else if(a=="--project-root") project_root=std::filesystem::u8path(next());
            else if(a=="--audio-output") audio_output=next();
            else if(a=="--save-root") ctx.saves.base=std::filesystem::u8path(next());
            else throw std::runtime_error("Unknown option: "+a);
        }
        if(frames<0 || frames>1000000 || ctx.dt<0 || !std::isfinite(ctx.dt) || ctx.budget<1)
            throw std::runtime_error("Invalid simulation limits");
        const double host_dt=ctx.dt; ctx.unscaled_dt=host_dt;
        if(!replay_path.empty()) {
            if(!ctx.keys.empty()) throw std::runtime_error("Use either --key or --input-replay");
            std::ifstream file(std::filesystem::u8path(replay_path));
            if(!file) throw std::runtime_error("Cannot open input replay");
            rt::Json data; file>>data; replay=rt::LoadInputReplay(data);
        }
        if(!ui_replay_path.empty()) {
            std::ifstream file(std::filesystem::u8path(ui_replay_path));
            if(!file) throw std::runtime_error("Cannot open UI replay");
            rt::Json data; file>>data; ui_replay=rt::LoadUiReplay(data);
        }
#ifdef NODE_ENGINE_COMPILED
        const auto ir=CompiledProgram();
        rt::ConfigureSceneProject(ctx,ir,project_root,false,BindEvents,OnFixedUpdate);
#else
        if(path.empty()) throw std::runtime_error("--ir is required");
        std::ifstream file(std::filesystem::u8path(path));
        if(!file) throw std::runtime_error("Cannot read IR: "+path);
        rt::Json ir; file>>ir;
        if(ir.at("version")!=1) throw std::runtime_error("Unsupported IR version");
        rt::ConfigureSceneProject(ctx,ir,project_root);
#endif
        rt::PrepareAudio(ctx,project_root);
        rt::PrepareAnimations(ctx,project_root);
        rt::PrepareUi(ctx,project_root);
        rt::VerifyGameResources(ctx);
        if(!audio_output.empty()) rt::BeginAudioCapture(ctx,std::filesystem::u8path(audio_output));
        auto loaded=[&]() {
            rt::StartEntityLifecycle(ctx); rt::DrainEvents(ctx);
#ifdef NODE_ENGINE_COMPILED
            OnSceneLoaded(ctx);
#else
            const auto& events=rt::CurrentSceneProgram(ctx).at("events");
            if(events.contains("scene_loaded")) rt::Execute(ctx,events.at("scene_loaded"));
#endif
            rt::DrainEvents(ctx);
        };
        auto scene_change=[&]() {
            if(ctx.quit_requested) {rt::CancelSceneChange(ctx); return;}
            if(rt::ProcessSceneChange(ctx)) {loaded(); rt::UpdateUi(ctx); rt::DrainUiEvents(ctx);}
            rt::DrainEvents(ctx);
        };
        ctx.remaining=ctx.budget;
        loaded();
#ifdef NODE_ENGINE_COMPILED
        OnStart(ctx);
#else
        rt::Execute(ctx,rt::CurrentSceneProgram(ctx).at("events").at("start"));
#endif
        rt::DrainEvents(ctx);
        rt::UpdateUi(ctx); rt::DrainUiEvents(ctx);
        scene_change();
        if(rt::GameSavePending(ctx)) { rt::ProcessGamePersistence(ctx); rt::DrainEvents(ctx); }
        for(int i=0;i<frames && !ctx.quit_requested;++i) {
            rt::BeginGameFrame(ctx,host_dt);
            auto input=replay.find(ctx.frame);
            rt::AdvanceInput(ctx,input==replay.end() ? std::vector<rt::InputEvent>{} : input->second);
            ctx.remaining=ctx.budget;
            rt::AdvanceContinuations(ctx); rt::DrainEvents(ctx);
            if(auto ui_input=ui_replay.find(ctx.frame); ui_input!=ui_replay.end()) rt::AdvanceUiInput(ctx,ui_input->second);
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
            rt::UpdateUi(ctx); rt::DrainUiEvents(ctx);
            scene_change();
            if(rt::GameSavePending(ctx)) { rt::ProcessGamePersistence(ctx); rt::DrainEvents(ctx); }
        }
        rt::FinishApplication(ctx,[&]() {
#ifdef NODE_ENGINE_COMPILED
            OnQuit(ctx);
#else
            if(rt::CurrentSceneProgram(ctx).at("events").contains("quit")) rt::Execute(ctx,rt::CurrentSceneProgram(ctx).at("events").at("quit"));
#endif
        },[&]() { rt::UpdateUi(ctx); },[&]() { rt::ProcessGamePersistence(ctx); rt::DrainEvents(ctx); });
        rt::FinishAudioCapture(ctx);
        auto result=rt::Snapshot(ctx).dump(2);
        if(output.empty()) std::cout<<result<<"\n";
        else {
            std::ofstream out(std::filesystem::u8path(output));
            if(!out) throw std::runtime_error("Cannot write output: "+output);
            out<<result<<"\n";
        }
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<rt::Json{{"event","node_error"},{"scene",ctx.scene_name},{"node",ctx.current_node},{"message",e.what()}}.dump()<<"\n";
        return 1;
    }
}
