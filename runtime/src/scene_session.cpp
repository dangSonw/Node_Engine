#include "runtime.hpp"
#include <regex>
namespace rt {
struct SceneProject {
    Json program;
    std::filesystem::path root;
    bool playback;
    std::function<void(Ctx&)> bind,fixed;
};
struct SceneSession {
    struct Request { std::string scene,node; };
    std::shared_ptr<const SceneProject> project;
    std::optional<Request> pending;
    bool success=true;
    std::string error;
};
namespace {
void check(bool okay,const char* error) { if(!okay) throw std::runtime_error(error); }
bool has_scene(const SceneProject& p,const std::string& name) {
    return p.program.contains("scenes") ? p.program.at("scenes").contains(name) : name=="main";
}
const Json& program(const SceneProject& p,const std::string& name) {
    check(has_scene(p,name),"Unknown scene ID");
    return p.program.contains("scenes") ? p.program.at("scenes").at(name) : p.program;
}
void initialize(Ctx& c,std::shared_ptr<const SceneProject> project,const std::string& name) {
    const auto& ir=program(*project,name);
    LoadScene(c,ir.at("scene")); c.scene_name=name;
    InitializeProjectGlobals(c,project->program);
    c.scenes=std::make_shared<SceneSession>(); c.scenes->project=std::move(project);
    c.functions=ir.value("functions",Json::object()); ConfigureFlow(c,ir);
    if(c.scenes->project->bind) c.scenes->project->bind(c); else BindInterpretedEvents(c,ir);
    ConfigureFixedUpdate(c,ir,c.scenes->project->fixed);
    ConfigureGamePersistence(c,c.scenes->project->program,c.scenes->project->root);
}
}
void ConfigureSceneProject(Ctx& c,const Json& ir,const std::filesystem::path& root,bool playback,
                           std::function<void(Ctx&)> bind,std::function<void(Ctx&)> fixed) {
    check(ir.is_object() && ir.at("version").is_number_integer() && ir.at("version")==1,"Unsupported project IR version");
    std::string entry="main";
    if(ir.contains("scenes")) {
        check(ir.size()==3 && ir.contains("entry_scene") && ir.at("entry_scene").is_string() &&
              ir.at("scenes").is_object() && !ir.at("scenes").empty() && ir.at("scenes").size()<=64,"Invalid project scene library");
        entry=ir.at("entry_scene").get<std::string>();
        static const std::regex id("[A-Za-z][A-Za-z0-9_-]{0,63}");
        for(const auto& [name,p]:ir.at("scenes").items()) {
            check(std::regex_match(name,id) && p.is_object() && p.at("version").is_number_integer() && p.at("version")==1 && !p.contains("scenes"),"Invalid scene program");
            ValidateFrameEvents(p); check(p.contains("scene") && p.at("scene").is_object(),"Scene program has no scene");
        }
    } else ValidateFrameEvents(ir);
    auto project=std::make_shared<SceneProject>(SceneProject{ir,std::filesystem::canonical(root),playback,std::move(bind),std::move(fixed)});
    initialize(c,std::move(project),entry);
}
const Json& CurrentSceneProgram(const Ctx& c) {
    check(bool(c.scenes),"Host has not configured scene management"); return program(*c.scenes->project,c.scene_name);
}
bool ChangeScene(Ctx& c,std::string name) {
    check(bool(c.scenes),"Host has not configured scene management"); auto& s=*c.scenes;
    s.success=false; s.error.clear();
    try {
        check(!c.quit_requested,"Cannot change scenes during application shutdown");
        check(!s.pending,"A scene change is already pending this frame");
        check(!GameSavePending(c),"A game save or load is already pending this frame");
        check(has_scene(*s.project,name),"Unknown scene ID");
        s.pending=SceneSession::Request{std::move(name),c.current_node}; return true;
    } catch(const std::exception& e) {s.error=e.what(); return false;}
}
bool ReloadScene(Ctx& c) {return ChangeScene(c,c.scene_name);}
std::string GetActiveScene(Ctx& c) {return c.scene_name;}
Array<std::string> GetSceneNames(Ctx& c) {
    check(bool(c.scenes),"Host has not configured scene management"); Array<std::string> result;
    if(c.scenes->project->program.contains("scenes")) for(const auto& [name,_]:c.scenes->project->program.at("scenes").items()) result.push_back(name);
    else result.push_back("main"); return result;
}
bool SceneLoadSucceeded(Ctx& c) {return c.scenes && c.scenes->success;}
std::string GetSceneError(Ctx& c) {return c.scenes ? c.scenes->error : "Host has not configured scene management";}
bool SceneChangePending(const Ctx& c) {return c.scenes && c.scenes->pending.has_value();}
void CancelSceneChange(Ctx& c) noexcept {if(c.scenes) c.scenes->pending.reset();}
bool ProcessSceneChange(Ctx& c,const std::function<void(const Ctx&)>& prepare,const std::function<void()>& commit,
                        Rml::RenderInterface* renderer,SDL_Window* window) {
    if(!SceneChangePending(c)) return false;
    auto& s=*c.scenes; const auto request=std::move(*s.pending); s.pending.reset();
    try {
        check(!c.execution_depth && !c.call_depth && c.parameters.empty(),"Scene change requires a graph boundary");
        (void)EventCheckpoint(c); (void)UiCheckpoint(c); VerifyGameResources(c);
        Ctx next; initialize(next,s.project,request.scene); next.saves=c.saves;
        next.global_variables=c.global_variables;
        InitializeProjectGlobals(next,s.project->program);
        next.logs=c.logs; next.frame=c.frame; next.time=c.time; next.dt=c.dt;
        next.real_time=c.real_time; next.real_dt=c.real_dt; next.unscaled_dt=c.unscaled_dt;
        next.time_scale=c.time_scale; next.time_frozen=c.time_frozen; next.world_paused=c.world_paused;
        next.budget=c.budget; next.remaining=c.remaining;
        PrepareAudio(next,s.project->root); PrepareSceneAudioOutput(next,c);
        PrepareAnimations(next,s.project->root); PrepareUi(next,s.project->root,renderer,window,false);
        VerifyGameResources(next); if(prepare) prepare(next);
        CommitGameCheckpoint(c,std::move(next));
    } catch(const std::exception& e) {
        c.scenes->success=false; c.scenes->error=e.what(); c.current_node=request.node;
        QueueSceneLoadFailed(c,request.scene,c.scenes->error); return false;
    }
    if(commit) commit();
    return true;
}
Json SceneSessionSnapshot(const Ctx& c) {
    if(!c.scenes) return nullptr;
    return {{"active",c.scene_name},{"success",c.scenes->success},{"error",c.scenes->error},
            {"pending",c.scenes->pending ? c.scenes->pending->scene : ""}};
}
Ctx SceneCheckpointBindings(const Ctx& c,const Json& saved) {
    check(c.scenes && saved.is_object() && saved.size()==4 && saved.at("active").is_string() &&
          saved.at("success").is_boolean() && saved.at("error").is_string() && saved.at("pending")=="",
          "Invalid saved scene session");
    const auto error=saved.at("error").get<std::string>(); check(error.size()<=65536,"Saved scene error exceeds limit");
    Ctx next; next.saves=c.saves; initialize(next,c.scenes->project,saved.at("active").get<std::string>());
    next.scenes->success=saved.at("success").get<bool>(); next.scenes->error=error; return next;
}
void PrepareSceneAudioOutput(Ctx& next,const Ctx& current) {
    if(next.scenes && next.scenes->project->playback && !AudioOutputStatus(current).at("connected").get<bool>()) EnableAudioOutput(next);
}
}
