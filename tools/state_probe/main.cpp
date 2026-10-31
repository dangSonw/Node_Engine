// Fresh-process continuation of scene, input, events and sound checkpoint state.
#include "runtime.hpp"
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>

using namespace rt;
namespace {
Json checks=Json::array();
void Require(bool ok,const std::string& message) { if(!ok) throw std::runtime_error(message); }
void Check(const std::string& message,bool ok) { Require(ok,message); checks.push_back(message); }
template<class F> void Fails(F f) {
    bool failed=false; try { f(); } catch(const std::exception&) { failed=true; }
    Require(failed,"Expected invalid checkpoint to fail");
}
Json EntityData(std::string id) {
    return {{"id",id},{"position",{0,0,0}},{"rotation",{0,0,0}},{"scale",{1,1,1}}};
}
Json Scene() {
    auto player=EntityData("player"),deleted=EntityData("deleted"),root=EntityData("root"),child=EntityData("child");
    deleted["mesh"]="assets/deleted.glb"; child["parent"]="root";
    root["components"]={{"1",{{"properties",{{"1",INT64_MAX},{"2",{"child","root"}}}}}}};
    Json asset={{"id","test"},{"name","Test"},{"type","prefab"},{"version",1},{"root","root"},{"entities",{root,child}}};
    return {{"version",1},{"entities",{player,deleted}},{"variables",Json::object()},
        {"component_definitions",{{{"id",1},{"name","Links"},{"properties",{
            {{"id",1},{"name","count"},{"type","int"},{"default",0}},
            {{"id",2},{"name","refs"},{"type","array<entity>"},{"default",Json::array()}}
        }}}}}, {"prefab_assets",{asset}},{"prefab_templates",{asset}},
        {"input",{{"version",1},{"actions",{{"fire",{"Space","MouseLeft"}}}},
            {"axes",{{"move",{{"negative",{"A"}},{"positive",{"D"}}}}}}}},
        {"audio_assets",{
            {{"version",1},{"id","tone"},{"type","sound"},{"name","Tone"},{"file","assets/tone.wav"}},
            {{"version",1},{"id","resample"},{"type","sound"},{"name","Resample"},{"file","assets/resample.wav"}},
            {{"version",1},{"id","short"},{"type","sound"},{"name","Short"},{"file","assets/short.wav"}},
            {{"version",1},{"id","music"},{"type","sound"},{"name","Music"},{"file","assets/music.mp3"}},
            {{"version",1},{"id","low"},{"type","sound"},{"name","Low"},{"file","assets/low.wav"}},
            {{"version",1},{"id","high"},{"type","sound"},{"name","High"},{"file","assets/high.wav"}}
        }}};
}
void Bind(Ctx& c) {
    DeclareEvent(c,100001,{"entity"});
    BindEvent(c,100001,"event",{},true,[](Ctx& c,EntityRef,EntityRef,const std::vector<Value>& args){
        SetVariableAs(c,"received",std::get<EntityRef>(args.at(0)));
    });
    BindTimer(c,"timer",{},"",[](Ctx& c,const std::string&,EntityRef){
        Translate(c,{"player"},Vec3(.25,0,0));
    });
}
Ctx Initial(const std::filesystem::path& root) {
    Ctx c; LoadScene(c,Scene()); Bind(c); PrepareAudio(c,root);
    auto instance=InstantiatePrefab(c,"test",{},Vec3(2,3,4));
    const auto member=GetPrefabEntity(c,instance,"child");
    SetVariableAs(c,"instance",instance); SetVariableAs(c,"member",member);
    SetVariableAs(c,"count",std::int64_t(INT64_MIN)); SetVariableAs(c,"text",std::string("Việt\0😀",12));
    SetComponentProperty(c,instance,1,1,std::int64_t(INT64_MIN)); SetComponentEnabled(c,instance,1,false);
    SetComponentProperty(c,instance,1,2,Array<EntityRef>{member,{"deleted"}});
    SetEntityActive(c,instance,false); SetEntityLayer(c,instance,23); AddEntityTag(c,instance,"enemy");
    auto camera=CreateCamera(c,"view",Vec3(4,5,6)); SetParent(c,camera,{"player"});
    SetCameraOrthographic(c,camera,12,.1,100); SetActiveCamera(c,camera);
    auto clone=CloneEntity(c,instance,"copy"); SetParent(c,clone,{"player"});
    SendEvent(c,100001,{},{"deleted"},{member});
    DestroyEntity(c,member); DestroyEntity(c,{"deleted"});
    auto last=SpawnEntity(c,"last","assets/deleted.glb",Vec3(0)); DestroyEntity(c,last);
    AdvanceInput(c,{{"Space",true},{"Space",false},{"Space",true},{"MouseLeft",true},{"A",true}});
    StartTimer(c,"repeat",.017,true,{});
    PlaySound(c,"tone","z-loop",true,.15); PlaySound(c,"resample","a-paused",true,.1);
    PlaySound(c,"music","m-music",true,.1); PlaySound(c,"short","ended",false,.2);
    PlaySound(c,"tone","stopped",true,.1);
    PlaySound(c,"low","low",true,.03); PlaySound(c,"high","high",true,.03);
    c.dt=2000.375/48000; AdvanceAudio(c); PauseSound(c,"a-paused"); StopSound(c,"stopped");
    SetMasterVolume(c,.75); c.dt=1./60;
    return c;
}
Json Capture(const Ctx& c) {
    return {{"snapshot",Snapshot(c)},{"identity",SceneIdentityCheckpoint(c)},
        {"input",InputCheckpoint(c)},{"events",EventCheckpoint(c)},{"audio",AudioCheckpoint(c)}};
}
Ctx Restore(const Json& state,const std::filesystem::path& root) {
    Ctx program; LoadScene(program,Scene()); Bind(program);
    Ctx c; LoadScene(c,state.at("snapshot").at("scene"),state.at("identity"));
    RestoreInputCheckpoint(c,state.at("input")); RestoreEventCheckpoint(c,program,state.at("events"));
    RestoreAudioCheckpoint(c,state.at("audio"),root);
    return c;
}
Json Continue(Ctx& c,const std::filesystem::path& pcm,int first=0,int end=90) {
    Json trace=Json::array(); BeginAudioCapture(c,pcm);
    const auto instance=GetVariableAs<EntityRef>(c,"instance"),member=GetVariableAs<EntityRef>(c,"member");
    if(first==0) Require(ActionHeld(c,"fire") && ActionPressed(c,"fire") && ActionReleased(c,"fire") &&
        KeyPressed(c,"Space") && KeyReleased(c,"Space") && InputAxis(c,"move")==-1,"Same-frame input edges and held axis");
    for(int frame=first;frame<end;++frame) {
        c.remaining=c.budget;
        if(frame==0) AdvanceInput(c,{{"Space",false}});
        else if(frame==1) AdvanceInput(c,{{"MouseLeft",false},{"D",true}});
        else if(frame==2) AdvanceInput(c,{{}});
        else if(frame==4) AdvanceInput(c,{{"Space",true},{"D",true}});
        else AdvanceInput(c,{});
        if(frame==3) {
            ResetPrefabInstance(c,instance,true);
            Require(GetPrefabEntity(c,instance,"child")==member,"Deleted prefab child reuses its stable ID");
            ResumeSound(c,"a-paused");
        }
        if(frame==7) {
            auto entity=SpawnEntity(c,"restored asset","assets/deleted.glb",Vec3(3));
            SetParent(c,entity,{"player"}); SetVariableAs(c,"new_entity",entity);
        }
        if(frame==10) ApplyPrefabOverrides(c,instance,true);
        if(frame==14) { SetSoundVolume(c,"z-loop",.3); PauseSound(c,"m-music"); }
        if(frame==17) ResumeSound(c,"m-music");
        if(frame==31) PlaySound(c,"resample","z-loop",false,.3);
        if(frame==40) { SetEntityActive(c,instance,true); SetMasterVolume(c,.5); }
        if(frame==60) DestroyEntity(c,GetVariableAs<EntityRef>(c,"new_entity"));
        if(frame==70) StopAllSounds(c);
        if(ActionHeld(c,"fire")) Translate(c,{"player"},Vec3(InputAxis(c,"move"),0,0));
        c.dt=frame%4==0 ? 0 : frame%4==1 ? 1./44100 : frame%4==2 ? .013 : 1./60;
        DrainEvents(c); AdvanceTimers(c); DrainEvents(c); AdvanceAudio(c);
        trace.push_back(Capture(c));
    }
    FinishAudioCapture(c); return trace;
}
void Invalid(const std::filesystem::path& root) {
    auto c=Initial(root); const auto before=Capture(c);
    std::ofstream(root/"initial-state.json") << before.dump(2);
    auto other=Restore(before,root);
    Check("distinct-world roundtrip preserves scene hierarchy, components, prefab inheritance, camera, variables and input",Capture(other)==before && NativeWorld(other)!=NativeWorld(c));
    Check("deleted mesh remains preloaded",SceneMeshes(other).contains("assets/deleted.glb"));
    Check("deleted authored entity ID remains reserved",SceneIdentityCheckpoint(other)["reserved_ids"].get<std::set<std::string>>().contains("deleted"));
    using Damage=std::function<void(Json&)>;
    const std::vector<std::pair<std::string,Damage>> input={
        {"version",[](Json& j){j["version"]=1.0;}}, {"extra",[](Json& j){j["unknown"]=true;}},
        {"missing",[](Json& j){j.erase("held");}}, {"binding",[](Json& j){j["bindings"]["actions"]["fire"]={"invalid"};}},
        {"array",[](Json& j){j["pressed"]="Space";}}, {"key",[](Json& j){j["held"]={"invalid"};}},
        {"duplicate",[](Json& j){j["released"]={"Space","Space"};}}, {"typed key",[](Json& j){j["held"]={true};}},
        {"action",[](Json& j){j["actions_pressed"]={"unknown"};}}, {"null bindings",[](Json& j){j["bindings"]=nullptr;}}
    };
    for(const auto& [name,damage]:input) {
        auto bad=before.at("input"); damage(bad); Fails([&]{RestoreInputCheckpoint(c,bad);});
        Check("invalid input "+name+" leaves held keys, bindings and edges unchanged",Capture(c)==before);
    }
    const auto world=c.world;
    const std::vector<std::pair<std::string,Damage>> identity={
        {"version",[](Json& j){j["version"]=true;}}, {"missing",[](Json& j){j.erase("meshes");}},
        {"extra",[](Json& j){j["unknown"]=0;}}, {"array",[](Json& j){j["reserved_ids"]=false;}},
        {"duplicate",[](Json& j){j["reserved_ids"].push_back(j["reserved_ids"][0]);}},
        {"ID",[](Json& j){j["reserved_ids"].push_back("bad\nID");}},
        {"live ID",[](Json& j){j["reserved_ids"]=Json::array();}},
        {"deleted prefab ID",[](Json& j){auto& ids=j["reserved_ids"];ids.erase(std::find(ids.begin(),ids.end(),Json("spawned_2")));}},
        {"mesh type",[](Json& j){j["meshes"]={7};}},
        {"mesh duplicate",[](Json& j){j["meshes"].push_back(j["meshes"][0]);}}
    };
    for(const auto& [name,damage]:identity) {
        auto bad=before.at("identity"); damage(bad);
        Fails([&]{c.world=CreateSceneWorld(before.at("snapshot").at("scene"),bad);});
        Check("invalid scene identity "+name+" leaves original world unchanged",c.world==world && Capture(c)==before);
    }
    const auto audio=c.audio;
    const std::vector<std::pair<std::string,Damage>> sound={
        {"version",[](Json& j){j["version"]=1;}}, {"missing",[](Json& j){j.erase("fraction");}},
        {"extra",[](Json& j){j["unknown"]=0;}}, {"library",[](Json& j){j["assets"]=Json::array();}},
        {"counter",[](Json& j){j["sample_frames"]=-1;}}, {"fraction",[](Json& j){j["fraction"]=1.;}},
        {"gain",[](Json& j){j["master_volume"]=1.1;}}, {"voice gain",[](Json& j){j["voices"]["ended"]["volume"]=-1.;}},
        {"playing paused",[](Json& j){j["voices"]["ended"]["playing"]=true;j["voices"]["ended"]["paused"]=true;}},
        {"duplicate serial",[](Json& j){j["voices"]["ended"]["serial"]=j["voices"]["z-loop"]["serial"];}},
        {"future serial",[](Json& j){j["voices"]["ended"]["serial"]=1000;}},
        {"unknown sound",[](Json& j){j["voices"]["stopped"]["sound"]="missing";}},
        {"position",[](Json& j){j["voices"]["stopped"]["position_frames"]=1000000000;}},
        {"position type",[](Json& j){j["voices"]["stopped"]["position_frames"]=3.25;}},
        {"elapsed samples",[](Json& j){j["voices"]["stopped"]["mixed_frames"]=1000000;}},
        {"decoder position mismatch",[](Json& j){j["voices"]["stopped"]["position_frames"]=10;}},
        {"exhausted voice resumes",[](Json& j){j["voices"]["ended"]["playing"]=true;}},
        {"history type",[](Json& j){j["history"]=Json::object();}},
        {"history size",[](Json& j){j["history"]=std::vector<Json>(65537,Json::array({"mix",1,1}));}},
        {"history opcode",[](Json& j){j["history"][0][0]="unknown";}},
        {"history play fields",[](Json& j){j["history"][0].push_back(0);}},
        {"history loop type",[](Json& j){j["history"][0][3]=0;}},
        {"history unknown asset",[](Json& j){j["history"][0][1]="unknown";}},
        {"history unknown voice",[](Json& j){j["history"].push_back({"pause","unknown"});}},
        {"history control fields",[](Json& j){j["history"].push_back({"stop","z-loop",0});}},
        {"history gain",[](Json& j){j["history"].push_back({"gain","z-loop",-1});}},
        {"history mix fields",[](Json& j){j["history"].push_back({"mix",1});}},
        {"history mix type",[](Json& j){j["history"].push_back({"mix",true,1});}},
        {"history zero frames",[](Json& j){j["history"].push_back({"mix",0,1});}},
        {"history large chunk",[](Json& j){j["history"].push_back({"mix",2049,1});}},
        {"history zero repeats",[](Json& j){j["history"].push_back({"mix",1,0});}},
        {"history work overflow",[](Json& j){j["history"].push_back({"mix",2048,UINT64_MAX});}},
        {"history call budget",[](Json& j){j["history"].push_back({"mix",1,1080001});}},
        {"history clock mismatch",[](Json& j){j["sample_frames"]=10000000;}},
        {"history serial mismatch",[](Json& j){j["serial"]=1000;}}
    };
    for(const auto& [name,damage]:sound) {
        auto bad=before.at("audio"); damage(bad); Fails([&]{RestoreAudioCheckpoint(c,bad,root);});
        Check("invalid audio "+name+" preserves current mixer and voices",c.audio==audio && Capture(c)==before);
    }
    for(int i=0;i<8;++i) RestoreAudioCheckpoint(c,before.at("audio"),root);
    Check("repeated audio restore preserves checkpoint",Capture(c)==before);
    Ctx empty; LoadScene(empty,{{"version",1},{"entities",Json::array()},{"variables",Json::object()}});
    const auto empty_input=InputCheckpoint(empty),empty_audio=AudioCheckpoint(empty);
    RestoreInputCheckpoint(empty,empty_input); RestoreAudioCheckpoint(empty,empty_audio,root);
    Check("empty scene accepts empty input and audio checkpoints",InputCheckpoint(empty)==empty_input && AudioCheckpoint(empty)==empty_audio);
    auto limited=Initial(root);
    for(int i=0;i<65536;++i) SetSoundVolume(limited,"z-loop",.2);
    Fails([&]{AudioCheckpoint(limited);});
    limited.dt=1./60; AdvanceAudio(limited); PauseSound(limited,"z-loop"); ResumeSound(limited,"z-loop");
    Check("History exhaustion rejects checkpoint while normal playback and controls continue",IsSoundPlaying(limited,"z-loop"));
}
}
int main(int argc,char** argv) {
    try {
        Require(argc==3,"Usage: node_state_probe --self-test|--write|--read DIRECTORY");
        const auto root=std::filesystem::u8path(argv[2]); const std::string command=argv[1];
        if(command=="--self-test") Invalid(root);
        else if(command=="--write") {
            Json file=Json::array();
            for(int cut:{0,4,16,33,68,90}) {
                auto c=Initial(root); if(cut) Continue(c,root/"prefix.wav",0,cut);
                Json item={{"cut",cut},{"state",Capture(c)}};
                item["trace"]=Continue(c,root/("reference-"+std::to_string(cut)+".wav"),cut,100);
                file.push_back(item);
            }
            std::ofstream out(root/"checkpoint.json",std::ios::binary); out << file.dump(); out.close();
            Check("write six checkpoints and uninterrupted continuation traces",bool(out));
        } else if(command=="--read") {
            std::ifstream input(root/"checkpoint.json",std::ios::binary); Json file; input >> file;
            for(const auto& item:file) {
                const auto cut=item.at("cut").get<int>(); const auto label=std::to_string(cut);
                auto c=Restore(item.at("state"),root);
                Check("fresh-process roundtrip at cut "+label,Capture(c)==item.at("state"));
                const auto trace=Continue(c,root/("restored-"+label+".wav"),cut,100);
                std::ofstream(root/("restored-trace-"+label+".json")) << trace.dump();
                Check("fresh-process scene/input/event/audio continuation at cut "+label,trace==item.at("trace"));
            }
        } else throw std::runtime_error("Unknown probe command");
        std::cout << Json({{"passed",true},{"checks",checks}}).dump() << '\n'; return 0;
    } catch(const std::exception& e) {
        std::cerr << e.what() << '\n'; std::cout << Json({{"passed",false},{"checks",checks},{"error",e.what()}}).dump() << '\n'; return 1;
    }
}
