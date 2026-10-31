#include "runtime.hpp"
#include <type_traits>

namespace rt {
struct GamePersistence {
    struct Request { bool load; std::string slot,game; std::filesystem::path directory; };
    Json program,identity,sprites,audio,ui;
    std::set<std::string> meshes;
    std::filesystem::path root;
    std::optional<Request> pending;
};
namespace {
void check(bool valid,const char* message) { if(!valid) throw std::runtime_error(message); }
void boundary(const Ctx& c) {
    check(c.execution_depth==0 && c.call_depth==0 && c.parameters.empty(),"Game checkpoint requires a graph execution boundary");
}
void fields(const Json& data,std::initializer_list<const char*> keys) {
    check(data.is_object() && data.size()==keys.size(),"Invalid game checkpoint fields");
    for(const auto key:keys) check(data.contains(key),"Missing game checkpoint field");
}
void identity(const Json& value) {
    check(value.is_object() && !value.empty() && value.dump().size()<=8*1024*1024,"Invalid game checkpoint program identity");
}
bool uses_game_save(const Json& value) {
    if(value.is_object() && value.contains("op") && value["op"]=="action_result" && value.contains("type") &&
       (value["type"]==23016 || value["type"]==23017)) return true;
    if(value.is_structured()) for(const auto& child:value) if(uses_game_save(child)) return true;
    return false;
}
bool uses_autosave(const Json& value) {
    if(!value.is_object() || !value.contains("scene") || !value.at("scene").is_object()) return false;
    const auto& scene=value.at("scene");
    const auto features=scene.value("features",Json::object());
    const auto gameplay=features.is_object() ? features.value("gameplay",Json::object()) : Json::object();
    return gameplay.is_object() && gameplay.contains("autosave");
}
bool request(Ctx& c,std::string slot,bool load) {
    c.saves.ok=false; c.saves.error.clear();
    try {
        check(bool(c.game_persistence),"Host has not configured game persistence");
        check(!load || !c.quit_dispatched,"Cannot load a game during application shutdown");
        check(!SceneChangePending(c),"A scene change is already pending this frame");
        check(!c.game_persistence->pending,"A game save or load is already pending this frame");
        check(!c.saves.game.empty(),"Open Save Storage before saving or loading the game");
        c.game_persistence->pending=GamePersistence::Request{load,std::move(slot),c.saves.game,c.saves.directory}; return true;
    } catch(const std::exception& e) { c.saves.error=e.what(); return false; }
}
void resources(const Ctx& c,const GamePersistence& state) {
    check(SceneMeshes(c)==state.meshes && SpriteAssets(c)==state.sprites &&
          AudioAssets(c)==state.audio && UiAssets(c)==state.ui,
          "Game checkpoint resource library differs from this program");
}
}
void ConfigureGamePersistence(Ctx& c,const Json& program,const std::filesystem::path& root) {
    if(!uses_game_save(program) && !uses_autosave(program)) return;
    auto state=std::make_shared<GamePersistence>(); state->program=program;
    state->root=std::filesystem::canonical(root); state->identity=GameProgramIdentity(program,state->root);
    state->meshes=SceneMeshes(c); state->sprites=SpriteAssets(c); state->audio=AudioAssets(c); state->ui=UiAssets(c);
    c.game_persistence=std::move(state);
}
void VerifyGameResources(const Ctx& c) {
    if(c.game_persistence) check(GameProgramIdentity(c.game_persistence->program,c.game_persistence->root)==c.game_persistence->identity,
        "Program resources changed; reload the project before saving or loading the game");
}
bool SaveGame(Ctx& c,std::string slot) { return request(c,std::move(slot),false); }
bool LoadGame(Ctx& c,std::string slot) { return request(c,std::move(slot),true); }
bool GameSavePending(Ctx& c) { return c.game_persistence && c.game_persistence->pending.has_value(); }
void CancelGamePersistence(Ctx& c) noexcept { if(c.game_persistence) c.game_persistence->pending.reset(); }
bool ProcessGamePersistence(Ctx& c,const std::function<void(const Ctx&)>& prepare,Rml::RenderInterface* renderer,SDL_Window* window,const std::function<void()>& commit) {
    if(!GameSavePending(c)) return false;
    const auto state=c.game_persistence; const auto pending=std::move(*state->pending); state->pending.reset();
    c.saves.ok=false; c.saves.error.clear();
    bool loaded=false;
    try {
        boundary(c);
        SyncPhysics(c);
        check(c.saves.game==pending.game && c.saves.directory==pending.directory,"Save storage changed while a game request was pending");
        VerifyGameResources(c);
        resources(c,*state);
        if(!pending.load) WriteGameCheckpoint(c,pending.slot,GameCheckpoint(c,state->identity));
        else {
            const auto saved=ReadGameCheckpoint(c,pending.slot);
            if(c.saves.ok) {
                auto next=StageGameCheckpoint(c,state->identity,saved,state->root,renderer,window);
                resources(next,next.game_persistence ? *next.game_persistence : *state);
                if(prepare) prepare(next);
                VerifyGameResources(c);
                CommitGameCheckpoint(c,std::move(next)); c.saves.ok=true; c.saves.error.clear(); loaded=true;
            }
        }
    } catch(const std::exception& e) { c.saves.ok=false; c.saves.error=e.what(); }
    if(loaded && commit) commit();
    // Hosts drain after handling a committed load. Handler failures are graph
    // errors, never a claim that an already committed save/load was rolled back.
    QueueGameSaveEvent(c,pending.load,c.saves.ok,pending.slot,c.saves.error);
    return loaded;
}
Json GameCheckpoint(const Ctx& c,const Json& program) {
    boundary(c); identity(program);
    check(!SceneChangePending(c),"Cannot checkpoint a pending scene change");
    check(std::isfinite(c.time) && c.time>=0 && std::isfinite(c.dt) && c.dt>=0 && c.frame<UINT64_MAX,"Invalid game clock");
    check(std::isfinite(c.time_scale) && c.time_scale>=0 && std::isfinite(c.real_time) && c.real_time>=0 &&
          std::isfinite(c.unscaled_dt) && c.unscaled_dt>=0 && c.unscaled_dt<=60,"Invalid unscaled game clock");
    CheckValue(EntityRef{c.self});
    Json saved={{"version",2},{"program",program},{"scene",Snapshot(c).at("scene")},
        {"identity",SceneIdentityCheckpoint(c)},{"input",InputCheckpoint(c)},{"events",EventCheckpoint(c)},
        {"audio",AudioCheckpoint(c)},{"ui",UiCheckpoint(c)},{"physics",PhysicsStateCheckpoint(c)},{"animation",AnimationSnapshot(c)},
        {"random",RandomCheckpoint(c)},{"flow",FlowCheckpoint(c)},{"clock",{{"frame",c.frame},{"time",c.time},{"dt",c.dt},{"self",c.self},
            {"scale",c.time_scale},{"real_time",c.real_time},{"unscaled_dt",c.unscaled_dt},{"paused",c.world_paused}}}};
    if(c.continuations) saved["continuations"]=ContinuationCheckpoint(c);
    if(c.scenes) saved["scene_session"]=SceneSessionSnapshot(c);
    check(saved.dump().size()<=64*1024*1024,"Game checkpoint exceeds 64 MiB"); return saved;
}
Ctx StageGameCheckpoint(const Ctx& current,const Json& program,const Json& saved,
                       const std::filesystem::path& root,Rml::RenderInterface* renderer,SDL_Window* window) {
    boundary(current); identity(program);
    // These checks also reject timer/event/UI callback reentrancy before staging.
    (void)EventCheckpoint(current); (void)UiCheckpoint(current);
    check(saved.at("version").is_number_integer() && saved.at("version")==2 && saved.dump().size()<=64*1024*1024,
        "Unsupported game checkpoint version or size");
    check(saved.at("program")==program,"Game checkpoint belongs to a different program or resource identity");
    std::optional<Ctx> bindings;
    if(current.scenes) bindings.emplace(SceneCheckpointBindings(current,saved.at("scene_session")));
    else check(!saved.contains("scene_session"),"Checkpoint requires a configured scene project");
    const auto& source=bindings ? *bindings : current;
    Json shape=Json::object(); for(const auto& [key,_]:saved.items()) if(key!="scene_session") shape[key]=nullptr;
    if(source.continuations) fields(shape,{"version","program","scene","identity","input","events","audio","ui","physics","animation","random","flow","continuations","clock"});
    else fields(shape,{"version","program","scene","identity","input","events","audio","ui","physics","animation","random","flow","clock"});
    const auto& clock=saved.at("clock");
    if(clock.contains("paused")) fields(clock,{"frame","time","dt","self","scale","real_time","unscaled_dt","paused"});
    else fields(clock,{"frame","time","dt","self","scale","real_time","unscaled_dt"});
    const bool paused=clock.contains("paused") ? FromJson<bool>(clock.at("paused")) : false;
    const auto& frame=clock.at("frame");
    check(frame.is_number_integer() && (frame.is_number_unsigned() || frame.get<int64_t>()>=0) && frame.get<uint64_t>()<UINT64_MAX,
        "Invalid game checkpoint frame");
    const auto time=FromJson<double>(clock.at("time")),dt=FromJson<double>(clock.at("dt"));
    check(time>=0 && dt>=0,"Invalid game checkpoint clock");
    const auto scale=FromJson<double>(clock.at("scale")),real=FromJson<double>(clock.at("real_time")),unscaled=FromJson<double>(clock.at("unscaled_dt"));
    check(scale>=0 && real>=0 && unscaled>=0 && unscaled<=60,"Invalid game checkpoint unscaled clock");
    const auto self=FromJson<EntityRef>(clock.at("self"));
    Ctx next; LoadScene(next,saved.at("scene"),saved.at("identity"));
    check(next.user_types==source.user_types,"Game checkpoint user type definitions mismatch");
    if(source.scenes) InitializeProjectGlobals(next,source.game_persistence ? source.game_persistence->program : CurrentSceneProgram(source));
    next.time=time; next.dt=dt; next.frame=frame.get<uint64_t>(); next.self=self.id;
    next.time_scale=scale; next.real_time=real; next.unscaled_dt=unscaled;
    next.world_paused=paused;
    next.functions=source.functions; next.budget=current.budget; next.remaining=next.budget;
    next.flow_nodes=source.flow_nodes;
    next.fixed_update=source.fixed_update;
    next.scenes=source.scenes; next.scene_name=source.scene_name;
    next.saves=current.saves; next.logs=current.logs; next.game_persistence=source.game_persistence;
    RestorePhysicsState(next,saved.at("physics"));
    RestoreAnimations(next,saved.at("animation"),root);
    RestoreRandom(next,saved.at("random"));
    RestoreFlow(next,saved.at("flow"));
    RestoreContinuations(next,source,saved.value("continuations",Json()));
    RestoreInputCheckpoint(next,saved.at("input"));
    check(next.input.bindings==saved.at("scene").value("input",Json()),"Game checkpoint input bindings disagree with scene");
    RestoreEventCheckpoint(next,source,saved.at("events"));
    RestoreAudioCheckpoint(next,saved.at("audio"),root,false);
    PrepareSceneAudioOutput(next,current);
    RestoreUiCheckpoint(next,source,saved.at("ui"),root,renderer,window,true);
    auto restored=GameCheckpoint(next,program);
    // Version-2 saves predating Pause World had no pause field and were unpaused.
    if(!clock.contains("paused")) restored["clock"].erase("paused");
    check(restored==saved,"Game checkpoint cannot be restored exactly");
    return next;
}
void CommitGameCheckpoint(Ctx& current,Ctx&& candidate) {
    boundary(current); boundary(candidate);
    (void)EventCheckpoint(current); (void)UiCheckpoint(current);
    check(current.world && candidate.world && current.world!=candidate.world,"Game checkpoint commit requires an independent world");
    check(!current.physics || current.physics!=candidate.physics,"Game checkpoint commit requires independent physics");
    // All resource preparation has finished. The only fallible host operation is
    // clearing old queued PCM; after the handoff, context replacement is noexcept.
    TransferAudioOutput(current,candidate);
    SuspendUiPlatform(current);
    candidate.quit_requested=current.quit_requested;
    candidate.quit_dispatched=current.quit_dispatched;
    static_assert(std::is_nothrow_move_assignable_v<Ctx>);
    current=std::move(candidate);
    ActivateUiPlatform(current);
}
}
