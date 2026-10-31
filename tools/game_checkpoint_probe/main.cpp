#include "runtime.hpp"
#include "ui_session.hpp"
#include <SDL3/SDL.h>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>

using namespace rt;
namespace {
Json checks=Json::array();
Json device=nullptr;
const Json program={{"fixture","combined game transaction"},{"version",1}};
constexpr int cuts[]={0,3,8,17,25,31},last_frame=36;
void Require(bool ok,const std::string& message) { if(!ok) throw std::runtime_error(message); }
void Check(const std::string& message,bool ok) { Require(ok,message); checks.push_back(message); }
template<class F> void Fails(F f) {
    bool failed=false; try { f(); } catch(const std::exception&) { failed=true; }
    Require(failed,"Expected rejection");
}
struct Window {
    SDL_Window* value=nullptr;
    Window() {
        Require(SDL_Init(SDL_INIT_VIDEO),SDL_GetError());
        value=SDL_CreateWindow("Game checkpoint transaction",640,480,SDL_WINDOW_HIDDEN); Require(value,SDL_GetError());
    }
    ~Window() { SDL_DestroyWindow(value); SDL_Quit(); }
};
Json Scene() {
    const auto rml=R"(<rml><head><style>body {font-family:node-ui;font-size:18px;} input {display:block;width:240px;height:30px;}</style></head>
<body><p id="label">Initial</p><input id="text" type="text" value="Player"/><input id="button" type="button" value="Click"/></body></rml>)";
    return {{"version",1},{"entities",{{{"id","player"},{"position",{0,0,0}},{"rotation",{0,0,0}},{"scale",{1,1,1}}}}},
        {"variables",{{"count",{{"type","int"},{"value",0}}}}},
        {"input",{{"version",1},{"actions",{{"move",{"D"}}}},{"axes",Json::object()}}},
        {"audio_assets",{{{"version",1},{"id","tone"},{"type","sound"},{"name","Tone"},{"file","assets/tone.wav"}}}},
        {"ui_assets",{{{"version",1},{"id","template"},{"type","ui"},{"name","HUD"},{"rml",rml}}}}};
}
void Bind(Ctx& c) {
    DeclareEvent(c,100001,{"string"});
    BindEvent(c,100001,"event",{},true,[](Ctx& c,EntityRef,EntityRef,const std::vector<Value>& a){SetWidgetText(c,"hud","label",std::get<std::string>(a[0]));});
    BindTimer(c,"timer",{},"",[](Ctx& c,const std::string&,EntityRef){
        SetVariableAs(c,"count",GetVariableAs<int64_t>(c,"count")+1); Translate(c,{"player"},Vec3(.1,0,0));
    });
    BindUiEvent(c,"ui","change","hud","text",[](Ctx& c,const UiEvent& e){SendEvent(c,100001,{}, {},{e.value});});
}
Ctx Initial(const std::filesystem::path& root,SDL_Window* window,bool playback=false) {
    Ctx c; LoadScene(c,Scene()); Bind(c); PrepareAudio(c,root,playback); PrepareUi(c,root,nullptr,window);
    c.physics=std::make_shared<PhysicsWorld>();
    PhysicsBody floor; floor.id="floor"; floor.motion="static"; floor.position={0,-.5,0}; floor.half_extents={5,.5,5}; c.physics->add(floor);
    PhysicsBody body; body.id="player"; body.position={0,.6,0}; body.mass=1.7; c.physics->add(body);
    PhysicsBody disabled; disabled.id="disabled"; disabled.position={3,3,0}; disabled.velocity={1,2,3}; c.physics->add(disabled); c.physics->enabled("disabled",false);
    CreateWidget(c,"template","hud"); SetWidgetFocus(c,"hud","text");
    AdvanceUiInput(c,{{{"type","text"},{"text"," Việt"}}});
    AdvanceInput(c,{{"D",true},{"D",false},{"D",true}});
    StartTimer(c,"clock",.019,true,{}); PlaySound(c,"tone","music",true,.2);
    c.saves.base=root/"saves"; Require(OpenSaveStorage(c,"transaction"),GetSaveError(c));
    c.logs={"host log before checkpoint"}; c.budget=4321; c.remaining=c.budget;
    UpdateUi(c,640,480); return c;
}
void Step(Ctx& c) {
    c.remaining=c.budget;
    if(c.frame>=15) {
        const double steps[]={1./44100,.013,1./60,.1,0};
        c.dt=steps[c.frame%5];
    }
    AdvanceInput(c,c.frame==4 ? std::vector<InputEvent>{{"D",false}} : std::vector<InputEvent>{});
    if(c.frame==2) PauseSound(c,"music");
    if(c.frame==5) { ResumeSound(c,"music"); SetVariableAs(c,"temporary",SpawnEntity(c,"temporary","",Vec3(0))); }
    if(c.frame==7) DestroyEntity(c,GetVariableAs<EntityRef>(c,"temporary"));
    if(c.frame==18) PlaySound(c,"tone","music",false,.3);
    if(c.frame==20) PlaySound(c,"tone","background",true,.1);
    if(c.frame==22) SetSoundVolume(c,"background",.15);
    if(c.frame==24) { PauseSound(c,"background"); SetMasterVolume(c,0); }
    if(c.frame==27) { ResumeSound(c,"background"); SetMasterVolume(c,.8); }
    if(c.frame==6 || c.frame==10) {
        SetWidgetFocus(c,"hud","text"); AdvanceUiInput(c,{{{"type","text"},{"text","!"}}});
    }
    if(ActionHeld(c,"move")) Translate(c,{"player"},Vec3(0,.25,0));
    DrainUiEvents(c); DrainEvents(c); AdvanceTimers(c); DrainEvents(c); AdvanceAudio(c);
    if(c.physics) {
        if(c.frame==2) c.physics->force("player",{1,2,3},{.1,.2,.3});
        if(c.frame==9) c.physics->enabled("disabled",true);
        if(c.frame==13) { c.physics->remove("disabled"); PhysicsBody b; b.id="replacement"; b.position={2,4,0}; c.physics->add(b); }
        if(c.dt>0) c.physics->step(c.dt);
    }
    c.time=rt::finite(c.time+c.dt); ++c.frame; UpdateUi(c,640,480);
}
Json Continue(Ctx& c,const std::filesystem::path& path) {
    BeginAudioCapture(c,path); Json trace=Json::array();
    while(c.frame<last_frame) { Step(c); trace.push_back(GameCheckpoint(c,program)); }
    FinishAudioCapture(c); return trace;
}
void SelfTest(const std::filesystem::path& root,SDL_Window* window) {
    auto c=Initial(root,window,true); PauseAudioOutput(c,false);
    BeginAudioCapture(c,root/"handoff-restored.wav");
    for(int n=0;n<3;++n) Step(c);
    const auto saved=GameCheckpoint(c,program); const auto world=c.world; const auto audio=c.audio; const auto ui=c.ui; const auto physics=c.physics;
    const auto output=AudioOutputStatus(c);
    device=output;
    Check("Source has a running output stream and active text input",output.at("connected")==true && output.at("paused")==false && SDL_TextInputActive(window));
    using Damage=std::function<void(Json&)>;
    const std::vector<std::pair<std::string,Damage>> damage={
        {"version",[](Json& j){j["version"]=3;}}, {"program",[](Json& j){j["program"]["fixture"]="different";}},
        {"extra field",[](Json& j){j["extra"]=0;}}, {"negative clock",[](Json& j){j["clock"]["time"]=-1;}},
        {"overflow frame",[](Json& j){j["clock"]["frame"]=UINT64_MAX;}},
        {"scene",[](Json& j){j["scene"]["entities"].push_back(j["scene"]["entities"][0]);}},
        {"input disagrees",[](Json& j){j["input"]["bindings"]["actions"]["another"]={"A"};}},
        {"events",[](Json& j){j["events"]["clock"]="invalid";}},
        {"physics",[](Json& j){j["physics"]["world"]["native"]="00";}},
        {"audio",[](Json& j){j["audio"]["voices"]["music"]["position_frames"]=999999;}},
        {"late UI",[](Json& j){j["ui"]["session"]["focus"]=nullptr;
            j["ui"]["session"]["documents"][0]["scroll"]={{{"at",{{"document","hud"},{"path",{9999}}}},{"x",0},{"y",1}}};}}
    };
    for(const auto& [label,edit]:damage) {
        auto bad=saved; edit(bad); Fails([&]{auto next=StageGameCheckpoint(c,program,bad,root,nullptr,window);});
        Check("Rejected "+label+" preserves every live subsystem, output and keyboard input",
            c.world==world && c.audio==audio && c.ui==ui && c.physics==physics && GameCheckpoint(c,program)==saved &&
            AudioOutputStatus(c).at("paused")==false && SDL_TextInputActive(window));
    }
    {
        auto candidate=StageGameCheckpoint(c,program,saved,root,nullptr,window);
        Check("Staging uses independent state without acquiring host audio output",candidate.world!=c.world && candidate.audio!=c.audio && candidate.ui!=c.ui && candidate.physics!=c.physics &&
            AudioOutputStatus(candidate).at("connected")==false && GameCheckpoint(candidate,program)==saved && SDL_TextInputActive(window));
    }
    Check("Abandoning a valid candidate preserves text input",SDL_TextInputActive(window) && GameCheckpoint(c,program)==saved);
    {
        ExecutionScope graph(c);
        Fails([&]{GameCheckpoint(c,program);}); Fails([&]{auto next=StageGameCheckpoint(c,program,saved,root);});
    }
    Check("Graph execution rejects checkpoint and restoration",c.execution_depth==0 && GameCheckpoint(c,program)==saved);
    c.logs.push_back("keep this later host diagnostic"); c.saves.error="host status"; c.saves.ok=false;
    for(int n=0;n<4;++n) Step(c);
    const auto old_logs=c.logs; const auto storage=c.saves.directory;
    auto next=StageGameCheckpoint(c,program,saved,root,nullptr,window);
    CommitGameCheckpoint(c,std::move(next));
    Check("Commit replaces all subsystems and restores the clock together",GameCheckpoint(c,program)==saved && c.world!=world && c.audio!=audio && c.ui!=ui && c.physics!=physics);
    Check("Commit preserves host diagnostics, storage identity and instruction budget",c.logs==old_logs && c.saves.directory==storage && c.saves.error=="host status" && !c.saves.ok && c.budget==4321 && c.remaining==4321);
    Check("Commit retains the running audio device and focused text input",AudioOutputStatus(c).at("connected")==true && AudioOutputStatus(c).at("paused")==false && SDL_TextInputActive(window));
    for(int n=0;n<4;++n) Step(c);
    FinishAudioCapture(c);
    auto reference=Initial(root,nullptr); BeginAudioCapture(reference,root/"handoff-reference.wav");
    for(int n=0;n<7;++n) Step(reference);
    auto repeat=Initial(root,nullptr); for(int n=0;n<3;++n) Step(repeat);
    TransferAudioOutput(reference,repeat); for(int n=0;n<4;++n) Step(repeat); FinishAudioCapture(repeat);
    Check("Capture continues across the context replacement",std::filesystem::file_size(root/"handoff-restored.wav")>44);
    // Repeated swaps must not lose the device or disable input when old sessions die.
    for(int n=0;n<3;++n) { auto candidate=StageGameCheckpoint(c,program,saved,root,nullptr,window); CommitGameCheckpoint(c,std::move(candidate)); }
    Check("Repeated commits retain live output and text input",AudioOutputStatus(c).at("connected")==true && SDL_TextInputActive(window));
    SetWidgetFocus(c,"hud","button"); UpdateUi(c,640,480);
    const auto no_text=GameCheckpoint(c,program);
    Check("Button focus releases the host text keyboard",!SDL_TextInputActive(window));
    SetWidgetFocus(c,"hud","text");
    auto without_text=StageGameCheckpoint(c,program,no_text,root,nullptr,window);
    Check("Staging an unfocused text field leaves the current keyboard active",SDL_TextInputActive(window));
    CommitGameCheckpoint(c,std::move(without_text));
    Check("Committing button focus deactivates the previous text keyboard",!SDL_TextInputActive(window));
    auto with_text=StageGameCheckpoint(c,program,saved,root,nullptr,window);
    Check("Staging text focus leaves the current keyboard inactive",!SDL_TextInputActive(window));
    CommitGameCheckpoint(c,std::move(with_text));
    Check("Committing text focus activates the new keyboard",SDL_TextInputActive(window));
    Ctx empty; LoadScene(empty,{{"version",1},{"entities",Json::array()},{"variables",Json::object()}});
    PrepareAudio(empty,root); PrepareUi(empty,root);
    const auto empty_saved=GameCheckpoint(empty,program);
    auto empty_candidate=StageGameCheckpoint(empty,program,empty_saved,root);
    CommitGameCheckpoint(empty,std::move(empty_candidate));
    Check("Empty scene commits without sound output or UI templates",GameCheckpoint(empty,program)==empty_saved && !AudioOutputStatus(empty).at("connected").get<bool>());
    Ctx unfocused; LoadScene(unfocused,Scene()); Bind(unfocused);
    PrepareAudio(unfocused,root); PrepareUi(unfocused,root,nullptr,window);
    CreateWidget(unfocused,"template","hud"); UpdateUi(unfocused,640,480);
    const auto unfocused_saved=GameCheckpoint(unfocused,program);
    Check("New UI document has no focused element",unfocused_saved.at("ui").at("session").at("focus").is_null());
    SetWidgetFocus(unfocused,"hud","text");
    auto unfocused_next=StageGameCheckpoint(unfocused,program,unfocused_saved,root,nullptr,window);
    CommitGameCheckpoint(unfocused,std::move(unfocused_next));
    Check("Unfocused UI restores exactly and releases the previous text keyboard",GameCheckpoint(unfocused,program)==unfocused_saved && !SDL_TextInputActive(window));
}
void PersistenceTest(const std::filesystem::path& root,SDL_Window* window) {
    auto c=Initial(root,window); Step(c);
    const Json ir={{"scene",Scene()},{"events",{{"start",{{{"op","action_result"},{"type",23016}}}}}}};
    ConfigureGamePersistence(c,ir,root); const auto id=GameProgramIdentity(ir,root);
    Require(OpenSaveStorage(c,"deferred-checkpoint-probe"),GetSaveError(c));
    if(SaveSlotExists(c,"test")) Require(DeleteSaveSlot(c,"test"),GetSaveError(c));
    const auto progress=GetVariableAs<int64_t>(c,"count");
    Require(SaveVariable(c,"test","count"),GetSaveError(c));
    Require(SaveJson(c,"test","settings","{\"sound\":true}"),GetSaveError(c));
    Check("Progress slot starts at version one",GetSaveVersion(c,"test")==1);
    {
        ExecutionScope execution(c);
        Check("Graph may queue Save Game without serializing live graph locals",SaveGame(c,"test") && GameSavePending(c) && !SaveOperationSucceeded(c));
        Check("Second request is rejected without replacing the first",!LoadGame(c,"missing") && GameSavePending(c));
        SetVariableAs(c,"count",int64_t(99));
    }
    Require(!ProcessGamePersistence(c) && SaveOperationSucceeded(c),GetSaveError(c));
    const auto saved=ReadGameCheckpoint(c,"test");
    Check("Boundary saves final graph state and upgrades the slot",!GameSavePending(c) && GetSaveVersion(c,"test")==2 && saved==GameCheckpoint(c,id));
    Check("Game save retains existing progress JSON",LoadJson(c,"test","settings")=="{\"sound\":true}");
    Require(LoadVariable(c,"test","count"),GetSaveError(c));
    Check("Game save retains independent saved variables",GetVariableAs<int64_t>(c,"count")==progress);
    Require(LoadGame(c,"test") && ProcessGamePersistence(c),GetSaveError(c));
    Check("Load restores all systems and the program remains configured",GameCheckpoint(c,id)==saved && !GameSavePending(c) && SaveOperationSucceeded(c));
    Step(c); const auto before=GameCheckpoint(c,id); const auto world=c.world; const auto audio=c.audio; const auto ui=c.ui;
    Require(LoadGame(c,"test"),GetSaveError(c));
    Check("Host preparation failure rolls back every subsystem",!ProcessGamePersistence(c,[](const Ctx&){throw std::runtime_error("GPU resources unavailable");}) &&
        !SaveOperationSucceeded(c) && GetSaveError(c)=="GPU resources unavailable" && c.world==world && c.audio==audio && c.ui==ui && GameCheckpoint(c,id)==before);
    auto extra_mesh=saved; extra_mesh["identity"]["meshes"].push_back("assets/unavailable.gltf");
    Require(WriteGameCheckpoint(c,"tampered",extra_mesh),GetSaveError(c)); Require(LoadGame(c,"tampered"),GetSaveError(c));
    Check("Headless and graphical hosts reject an altered preloaded mesh library",!ProcessGamePersistence(c) && !SaveOperationSucceeded(c) &&
        GetSaveError(c).find("resource library")!=std::string::npos && GameCheckpoint(c,id)==before);
    Require(SaveGame(c,"cancelled"),GetSaveError(c)); CancelGamePersistence(c);
    Check("Cancelled graph request is never executed",!GameSavePending(c) && !ProcessGamePersistence(c) && !SaveSlotExists(c,"cancelled"));
    Require(SaveGame(c,"wrong-storage"),GetSaveError(c)); Require(OpenSaveStorage(c,"another-checkpoint-probe"),GetSaveError(c));
    Check("Changing storage cannot redirect a queued request",!ProcessGamePersistence(c) && !SaveOperationSucceeded(c) && GetSaveError(c).find("storage changed")!=std::string::npos);
    Require(OpenSaveStorage(c,"deferred-checkpoint-probe"),GetSaveError(c));
    Require(SaveGame(c,""),GetSaveError(c));
    Check("Deferred invalid-slot error leaves the previous checkpoint intact",!ProcessGamePersistence(c) && !SaveOperationSucceeded(c) && ReadGameCheckpoint(c,"test")==saved);
    const auto changed=root/"assets/request-change.bin";
    std::ofstream(changed,std::ios::binary)<<"changed after program setup";
    Require(LoadGame(c,"test"),GetSaveError(c));
    const bool rejected=!ProcessGamePersistence(c) && !SaveOperationSucceeded(c) && GetSaveError(c).find("resources changed")!=std::string::npos;
    std::filesystem::remove(changed);
    Check("Changed on-disk assets reject loading before live state replacement",rejected && GameCheckpoint(c,id)==before);
    Require(LoadGame(c,"test"),GetSaveError(c));
    Check("Resource restoration allows retrying a failed load",ProcessGamePersistence(c) && SaveOperationSucceeded(c) && GameCheckpoint(c,id)==saved);
    auto legacy=saved;
    for(const auto field:{"physics","animation","random","flow"}) legacy.erase(field);
    for(const auto field:{"scale","real_time","unscaled_dt"}) legacy["clock"].erase(field);
    legacy["version"]=1;
    Require(WriteGameCheckpoint(c,"legacy",legacy),GetSaveError(c));
    Require(SaveJson(c,"legacy","progress","{\"level\":2}"),GetSaveError(c));
    Check("Progress writes preserve a legacy game checkpoint",ReadGameCheckpoint(c,"legacy")==legacy);
    Require(LoadGame(c,"legacy"),GetSaveError(c));
    Check("Loading an incompatible legacy checkpoint leaves the current game intact",!ProcessGamePersistence(c) && !SaveOperationSucceeded(c) && GameCheckpoint(c,id)==saved);
    Require(SaveGame(c,"legacy"),GetSaveError(c));
    Require(!ProcessGamePersistence(c) && SaveOperationSucceeded(c),GetSaveError(c));
    Check("New game save replaces the legacy checkpoint and retains progress",ReadGameCheckpoint(c,"legacy")==saved && LoadJson(c,"legacy","progress")=="{\"level\":2}");
    auto invalid=saved; invalid["physics"]=0;
    Check("Invalid physics envelope cannot overwrite an existing slot",!WriteGameCheckpoint(c,"legacy",invalid) && ReadGameCheckpoint(c,"legacy")==saved);
}
void PhysicsAuthoringTest(const std::filesystem::path& root) {
    std::ifstream input(root/"generated/game.ir.json"); Json ir; input>>ir;
    Ctx c; LoadScene(c,ir.at("scene"));
    BindTimer(c,"authoring_timer",{"player"},"",[](Ctx&,const std::string&,EntityRef){});
    StartTimer(c,"authoring_timer",1,true,{"player"});
    const auto state=[&] {return Json{{"snapshot",Snapshot(c)},{"physics",PhysicsStateCheckpoint(c)},
        {"identity",SceneIdentityCheckpoint(c)},{"events",EventCheckpoint(c)}};};
    const auto rejects=[&](auto operation,const std::string& reason) {
        bool rejected=false;
        try {operation();} catch(const std::exception& error) {
            Require(std::string(error.what()).find(reason)!=std::string::npos,"Unexpected rejection: "+std::string(error.what())); rejected=true;
        }
        Require(rejected,"Expected collider validation failure");
    };
    auto before=state(); const auto world=c.world; const auto original=c.physics;
    const auto player_handle=NativeEntity(c,"player");
    rejects([&]{InstantiatePrefab(c,"physics_robot",{"floor"},{0,4,0});},"uniform scale");
    Check("Failed collider instantiation preserves scene, ID allocation, physics and timer state",state()==before&&c.world==world&&c.physics==original);
    const auto spawned=InstantiatePrefab(c,"physics_robot",{},{4,4,0});
    Check("Valid prefab instantiation creates its body and preserves live Flecs handles",HasBody(c,spawned)&&NativeEntity(c,"player")==player_handle&&c.world==world);
    SetParent(c,spawned,{"floor"}); before=state(); const auto invalid_parent_world=c.physics;
    rejects([&]{ResetPrefabInstance(c,spawned,true);},"uniform scale");
    Check("Failed collider reset preserves pending transforms, timers and native body state",state()==before&&c.physics==invalid_parent_world);
    SetParent(c,spawned,{});
    SetScale(c,{"player"},{-1,1,1}); before=state();
    rejects([&]{ApplyPrefabOverrides(c,{"player"},true);},"positive entity");
    Check("Failed collider Apply leaves all instances and native physics unchanged",state()==before);
    SetScale(c,{"player"},{1,1,1}); SyncPhysics(c);
    SetBodyVelocity(c,spawned,{2,0,0}); RemoveBody(c,{"player"});
    const auto scene=Snapshot(c).at("scene"),saved=PhysicsStateCheckpoint(c);
    Ctx restored; LoadScene(restored,scene,SceneIdentityCheckpoint(c)); RestorePhysicsState(restored,saved);
    Check("Checkpoint restoration does not resurrect an authored body removed during gameplay",!HasBody(restored,{"player"})&&PhysicsStateCheckpoint(restored)==saved);
    ResetPrefabInstance(c,{"player"},true);
    Check("Prefab Reset restores its authored collider while preserving unrelated velocity",HasBody(c,{"player"})&&GetBodyVelocity(c,spawned)==Vec3(2,0,0));
    bool reset_from_contact=false;
    BindPhysicsEvent(c,1011,"reset_from_contact",{"player"},[&](Ctx& target,EntityRef,EntityRef,const std::vector<Value>&){
        if(!reset_from_contact) { ResetPrefabInstance(target,{"player"},true); reset_from_contact=true; }
    });
    c.dt=1./60.;
    for(int i=0;i<90&&!reset_from_contact;++i) AdvancePhysics(c);
    Check("Prefab physics transaction is valid inside a collision callback",reset_from_contact&&HasBody(c,{"player"})&&NativeEntity(c,"player")==player_handle);
}
}
#include <SDL3/SDL_main.h>
int main(int argc,char** argv) {
    try {
        Require(argc==3,"Usage: node_game_checkpoint_probe --self-test|--write|--read directory");
        Window window; const auto root=std::filesystem::absolute(std::filesystem::u8path(argv[2])); const std::string mode=argv[1];
        if(mode=="--self-test") SelfTest(root,window.value);
        else if(mode=="--persistence") PersistenceTest(root,window.value);
        else if(mode=="--physics-authoring") PhysicsAuthoringTest(root);
        else if(mode=="--identity") {
            std::ifstream input(root/"program.json"); Json ir; input>>ir;
            std::cout<<GameProgramIdentity(ir,root).dump()<<"\n"; return 0;
        }
        else if(mode=="--ui-restore") {
            std::ifstream input(root/"ui-checkpoint.json"); Json data; input>>data;
            UiSession session(std::filesystem::u8path(SDL_GetBasePath())/"fonts/RobotoMono-Regular.ttf",nullptr,nullptr,root/"assets");
            for(const auto& [name,id]:data.at("instances").items()) {
                for(const auto& asset:data.at("assets")) if(asset.at("id")==id)
                    session.load(name,asset.at("rml").get<std::string>(),"inline-ui.rml");
            }
            try { session.restore_checkpoint(data.at("session")); }
            catch(const std::exception& e) {
                std::cout<<Json({{"passed",false},{"error",e.what()},{"difference",Json::diff(data.at("session"),session.checkpoint())}}).dump()<<"\n"; return 1;
            }
            Check("UI fixture restores exactly",session.checkpoint()==data.at("session"));
        }
        else if(mode=="--write") {
            Json saves=Json::array();
            for(int cut:cuts) {
                auto c=Initial(root,window.value); while(c.frame<unsigned(cut)) Step(c);
                const auto saved=GameCheckpoint(c,program);
                saves.push_back({{"cut",cut},{"saved",saved},{"trace",Continue(c,root/("reference-"+std::to_string(cut)+".wav"))}});
            }
            std::ofstream(root/"checkpoint.json")<<saves.dump(2); Check("Writer persists six combined game checkpoints before process exit",true);
        } else if(mode=="--read") {
            std::ifstream input(root/"checkpoint.json"); Json saves; input>>saves;
            for(const auto& item:saves) {
                const auto cut=item.at("cut").get<int>(); auto c=Initial(root,window.value);
                auto next=StageGameCheckpoint(c,program,item.at("saved"),root,nullptr,window.value);
                CommitGameCheckpoint(c,std::move(next));
                Check("Fresh-process whole-context restoration at cut "+std::to_string(cut),GameCheckpoint(c,program)==item.at("saved"));
                const auto trace=Continue(c,root/("restored-"+std::to_string(cut)+".wav"));
                Check("Fresh-process continuation matches at cut "+std::to_string(cut),trace==item.at("trace"));
            }
        } else throw std::runtime_error("Unknown probe mode");
        std::cout<<Json({{"passed",true},{"checks",checks},{"device",device}}).dump()<<"\n"; return 0;
    } catch(const std::exception& e) { std::cout<<Json({{"passed",false},{"checks",checks},{"device",device},{"error",e.what()}}).dump()<<"\n"; return 1; }
}
